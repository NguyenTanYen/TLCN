"""Phụ thuộc dùng chung: người dùng hiện tại, phân quyền theo vai trò, kiểm tra quyền trên lớp HP."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import ClassSection, Exam, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    try:
        data = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tài khoản không tồn tại hoặc bị khóa")
    return user


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Không có quyền thực hiện chức năng này")
        return user
    return dep


def check_section_access(db: Session, user: User, cs_id: int) -> ClassSection:
    cs = db.get(ClassSection, cs_id)
    if not cs:
        raise HTTPException(404, "Không tìm thấy lớp học phần")
    if user.role == "lecturer" and (not user.lecturer or cs.lecturer_id != user.lecturer.id):
        raise HTTPException(403, "Bạn không phụ trách lớp học phần này")
    return cs


def check_course_access(db: Session, user: User, course_id: int) -> None:
    """Quản trị: mọi môn. Giảng viên: chỉ môn mình đang/đã dạy (có lớp HP) hoặc được phân công ra đề."""
    from sqlalchemy import text
    if not db.execute(text("SELECT 1 FROM courses WHERE id=:c"), {"c": course_id}).scalar():
        raise HTTPException(404, "Không tìm thấy môn học")
    if user.role == "admin":
        return
    lid = user.lecturer.id if user.lecturer else None
    ok = lid and db.execute(text("""SELECT 1 FROM class_sections WHERE course_id=:c AND lecturer_id=:l
                                    UNION SELECT 1 FROM assessment_assignments WHERE course_id=:c AND lecturer_id=:l LIMIT 1"""),
                            {"c": course_id, "l": lid}).scalar()
    if not ok:
        raise HTTPException(403, "Bạn không phụ trách môn học này")


def get_exam_for(db: Session, user: User, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy bài kiểm tra")
    check_section_access(db, user, exam.class_section_id)
    return exam


def check_moodle_course(db: Session, user: User, cs: ClassSection, course_id: int) -> None:
    """Khóa học Moodle gắn với lớp HP phải: tồn tại; chưa gắn lớp HP khác; trùng khóa học lớp đã gắn (nếu có);
    và (với giảng viên) người dùng là giảng viên của khóa học đó trên Moodle."""
    from sqlalchemy import text
    from .services import moodle
    if cs.moodle_course_id and int(cs.moodle_course_id) != int(course_id):
        raise HTTPException(409, f"Lớp học phần đã gắn với khóa học Moodle {cs.moodle_course_id}")
    if not moodle.moodle_available():
        raise HTTPException(502, "Lỗi kết nối LMS: không đọc được CSDL Moodle")
    if not moodle.course_exists(db, course_id):
        raise HTTPException(404, f"Không có khóa học Moodle id = {course_id}")
    other = db.execute(text("SELECT section_code FROM class_sections WHERE moodle_course_id=:m AND id<>:cs"),
                       {"m": course_id, "cs": cs.id}).scalar()
    if other:
        raise HTTPException(409, f"Khóa học Moodle {course_id} đã gắn với lớp học phần {other}")
    if user.role != "admin" and not moodle.is_course_teacher(db, user.username, course_id):
        raise HTTPException(403, f"Tài khoản {user.username} không phải giảng viên của khóa học Moodle {course_id}")
