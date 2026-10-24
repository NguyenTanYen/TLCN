"""Plugin pytest: ghi lại mọi endpoint API được gọi trong lúc kiểm thử (đường dẫn mẫu, phương thức, mã trả về, ca kiểm thử).

Dùng: python -m pytest -p ghi_api tests   (thư mục chứa tệp này phải có trong PYTHONPATH)
Kết quả ghi vào tệp chỉ định bởi biến môi trường GHI_API_OUT (mặc định ghi_api.json).
"""
import json
import os

HIT = []


def pytest_configure(config):
    from app.main import app

    @app.middleware("http")
    async def _ghi(request, call_next):
        resp = await call_next(request)
        r = request.scope.get("route")
        if r is not None and getattr(r, "path", "").startswith("/api"):
            test = (os.environ.get("PYTEST_CURRENT_TEST") or "").split("::")[-1].split(" ")[0]
            HIT.append([request.method, r.path, resp.status_code, test])
        return resp


def pytest_unconfigure(config):
    with open(os.environ.get("GHI_API_OUT", "ghi_api.json"), "w", encoding="utf-8") as f:
        json.dump(HIT, f, ensure_ascii=False)
