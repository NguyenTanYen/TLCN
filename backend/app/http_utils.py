import re
import unicodedata
from urllib.parse import quote


def attachment(filename: str) -> dict:
    ascii_name = unicodedata.normalize("NFKD", filename.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._") or "tai_lieu"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}
