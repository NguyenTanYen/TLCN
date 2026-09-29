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


def get_exam_for(db: Session, user: User, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy bài kiểm tra")
    check_section_access(db, user, exam.class_section_id)
    return exam
