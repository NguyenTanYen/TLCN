"""Xác thực: đăng nhập tài khoản của hệ thống và đăng nhập một lần (SSO) từ nút "Phân tích CĐR" trên Moodle.

Hệ thống chỉ dành cho giảng viên / bộ môn. Sinh viên làm bài và xem kết quả phân tích trên Moodle.
"""
import html
import json
import os
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import ClassSection, Lecturer, User
from ..schemas import LoginIn
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])
STUDENT_MSG = "Sinh viên làm bài và xem kết quả phân tích trên Moodle – hệ thống này dành cho giảng viên"


def user_info(u: User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "lecturer_id": u.lecturer.id if u.lecturer else None,
            "student_id": u.student.id if u.student else None}


def _token(u: User) -> dict:
    return {"access_token": create_token(u.id, u.role), "token_type": "bearer", "user": user_info(u)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=body.username.strip()).first()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    if u.role == "student":
        raise HTTPException(403, STUDENT_MSG)
    return _token(u)


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_info(u)


# ---------------------------------------------------------------- SSO từ Moodle
_used_jti: dict[str, int] = {}   # chống dùng lại vé (vé chỉ sống 120 giây)


class SSOError(Exception):
    pass


def verify_moodle_ticket(token: str) -> dict:
    """Kiểm tra vé JWT HS256 do plugin local_clo ký bằng khóa dùng chung."""
    if len(settings.moodle_sso_secret) < 32:
        raise SSOError("Hệ thống chưa cấu hình MOODLE_SSO_SECRET")
    try:
        claims = jwt.decode(token, settings.moodle_sso_secret, algorithms=["HS256"], audience="clo-analytics",
                            options={"require": ["exp", "iat", "sub", "jti", "role"]}, leeway=30)
    except jwt.ExpiredSignatureError:
        raise SSOError("Vé đăng nhập đã hết hạn – hãy bấm lại nút trên Moodle")
    except jwt.PyJWTError:
        raise SSOError("Vé đăng nhập không hợp lệ")
    if settings.moodle_url and claims.get("iss", "").rstrip("/") != settings.moodle_url.rstrip("/"):
        raise SSOError("Vé đăng nhập không phải do Moodle đã cấu hình phát hành")
    now = int(time.time())
    for k in [k for k, exp in _used_jti.items() if exp < now - 60]:
        del _used_jti[k]
    if claims["jti"] in _used_jti:
        raise SSOError("Vé đăng nhập đã được sử dụng")
    _used_jti[claims["jti"]] = int(claims["exp"])
    if claims["role"] not in ("teacher", "admin"):
        raise SSOError(STUDENT_MSG)
    return claims


def sso_user(db: Session, claims: dict) -> User:
    """Tìm/khởi tạo tài khoản ứng với người dùng Moodle. Không bao giờ cấp quyền cao hơn vai trò Moodle xác nhận."""
    u = db.query(User).filter_by(username=claims["sub"]).first()
    if u:
        if not u.is_active:
            raise SSOError("Tài khoản đã bị khóa")
        if u.role == "student":
            raise SSOError(STUDENT_MSG)
        if u.role == "admin" and claims["role"] != "admin":
            raise SSOError("Tài khoản quản trị chỉ đăng nhập được từ tài khoản quản trị Moodle")
        return u
    codes = [c for c in (claims.get("idnumber"), claims["sub"]) if c]
    lec = db.query(Lecturer).filter(Lecturer.lecturer_code.in_(codes), Lecturer.user_id.is_(None)).first()
    if not lec:
        raise SSOError(f"Tài khoản Moodle “{claims['sub']}” chưa được bộ môn khai báo là giảng viên trong hệ thống "
                       "(mã giảng viên phải trùng tên đăng nhập hoặc mã số trên Moodle)")
    u = User(username=claims["sub"], password_hash=hash_password(os.urandom(24).hex()), full_name=lec.full_name,
             email=claims.get("email") or None, role="lecturer")
    db.add(u); db.flush()
    lec.user_id = u.id
    db.commit(); db.refresh(u)
    return u


def _page(title: str, body: str, script: str = "") -> HTMLResponse:
    back = f'<a href="{html.escape(settings.moodle_url or "/")}">← Quay lại Moodle</a>' if settings.moodle_url else ""
    return HTMLResponse(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:Segoe UI,Roboto,Arial,sans-serif;background:#f4f6fb;display:grid;place-items:center;min-height:100vh;margin:0}}
.box{{background:#fff;border-radius:14px;padding:28px 32px;max-width:520px;box-shadow:0 10px 30px rgba(16,24,40,.08)}}
h1{{font-size:20px;color:#0b3d91;margin:0 0 10px}}p{{color:#475467;line-height:1.5}}a{{color:#0b3d91}}</style></head>
<body><div class="box"><h1>{html.escape(title)}</h1><p>{html.escape(body)}</p>{back}</div>{script}</body></html>""",
                        status_code=200 if script else 403)


@router.get("/moodle-sso", response_class=HTMLResponse, include_in_schema=True)
def moodle_sso(token: str, db: Session = Depends(get_db)):
    """Đích của nút "Phân tích CĐR" trên Moodle: kiểm tra vé, cấp phiên đăng nhập rồi vào thẳng lớp học phần tương ứng."""
    try:
        claims = verify_moodle_ticket(token)
        u = sso_user(db, claims)
    except SSOError as ex:
        return _page("Không thể đăng nhập từ Moodle", str(ex))
    t = _token(u)
    target = "/"
    if claims.get("courseid"):
        q = db.query(ClassSection).filter_by(moodle_course_id=int(claims["courseid"]))
        if u.role == "lecturer" and u.lecturer:
            q = q.filter_by(lecturer_id=u.lecturer.id)
        cs = q.first()
        if cs:
            target = f"/sections/{cs.id}"
    js = lambda v: json.dumps(v).replace("</", "<\\/")  # noqa: E731 – an toàn khi nhúng vào <script>
    script = ("<script>localStorage.setItem('tlcn_token'," + json.dumps(t["access_token"]) + ");"
              "localStorage.setItem('tlcn_user'," + js(json.dumps(t["user"], ensure_ascii=False)) + ");"
              "location.replace(" + js(target) + ");</script>")
    return _page("Đang chuyển tới hệ thống phân tích CĐR…", f"Xin chào {u.full_name}.", script)
