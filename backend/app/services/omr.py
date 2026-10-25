"""Chấm phiếu trả lời trắc nghiệm bằng ảnh quét / ảnh chụp điện thoại (OpenCV) – không cần Moodle.

Quy trình mỗi trang ảnh:
1. Tìm 4 ô vuông đen định vị ở 4 góc phiếu (đường viền 4 cạnh, gần vuông, tô đặc), mỗi ô gần một góc ảnh.
2. Phép biến đổi phối cảnh (homography) từ tâm 4 ô về tọa độ chuẩn của phiếu (sheet_layout) → ảnh phiếu "phẳng"
   dù chụp nghiêng/xoay; sau đó nhị phân hóa thích nghi (chịu được bóng, ánh sáng không đều).
3. Mỗi ô tròn: độ đậm trung bình (sau khi chuẩn hóa nền) trong vòng tròn bán kính 0,7 r. Ô được tô khi tỷ lệ ≥ ngưỡng tuyệt đối và vượt rõ
   mức nền của chính hàng đó (ô trống in sẵn viền + chữ). Hàng có 2 ô tô trở lên → "nhiều lựa chọn" (cần GV xem lại).
4. Trả về MSSV, mã đề, đáp án từng câu, độ tin cậy và ảnh phiếu đã nắn thẳng có đánh dấu để GV soát/sửa trước khi lưu.
"""
from __future__ import annotations

import base64

import numpy as np

from .paper import FID, FID_POS, ORIENT_BAR, PAGE_H, PAGE_W, SheetOptions, sheet_layout

PX = 6.0                       # độ phân giải ảnh chuẩn hóa: 6 px/mm (~152 dpi)
FILL_MIN = 0.30                # độ đậm trung bình tối thiểu của ô được tô (0 = trắng, 1 = đen kín)
FILL_GAP = 0.18                # chênh lệch tối thiểu so với ô nền của hàng


class OMRError(ValueError):
    pass


def load_pages(data: bytes, filename: str = "") -> list[np.ndarray]:
    """Ảnh (jpg/png/…) hoặc PDF nhiều trang -> danh sách ảnh xám."""
    import cv2
    if data[:4] == b"%PDF" or filename.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        out = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), colorspace=fitz.csGRAY)
            out.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy())
        return out
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise OMRError(f"Không đọc được ảnh {filename or ''}")
    return [img]


def _exif_free_resize(g: np.ndarray, target: int = 2200) -> np.ndarray:
    import cv2
    h, w = g.shape
    s = target / max(h, w)
    return cv2.resize(g, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else g


def find_fiducials(g: np.ndarray) -> np.ndarray:
    """Tâm 4 ô định vị theo thứ tự trên-trái, trên-phải, dưới-phải, dưới-trái."""
    import cv2
    h, w = g.shape
    blur = cv2.GaussianBlur(g, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # phép mở hình thái: xóa nét bút, chữ, đường kẻ mảnh (kể cả nét vẽ chạm vào ô định vị), giữ lại các ô tô đặc lớn
    k = max(3, int(min(h, w) * 0.006))
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    cnts, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area = h * w
    cand = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (area * 0.00012 < a < area * 0.01):
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        if not (0.6 < cw / ch < 1.6):
            continue
        hull = cv2.convexHull(c)
        solidity = a / max(cv2.contourArea(hull), 1)
        rect = cv2.minAreaRect(c)
        rect_fill = a / max(rect[1][0] * rect[1][1], 1)     # vuông tô đặc ≈ 1; tròn ≈ 0,785
        if solidity > 0.9 and rect_fill > 0.86:
            m = cv2.moments(c)
            cand.append((m["m10"] / m["m00"], m["m01"] / m["m00"], a))
    if len(cand) < 4:
        raise OMRError("Không thấy đủ 4 ô vuông định vị ở 4 góc phiếu (chụp đủ cả tờ phiếu, không che góc, đủ sáng)")
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    big = max(c[2] for c in cand)
    cand = [c for c in cand if c[2] >= 0.3 * big]
    pts = []
    for cx, cy in corners:
        best = min(cand, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        pts.append(best[:2])
    pts = np.array(pts, dtype=np.float32)
    if len({tuple(p) for p in pts.tolist()}) < 4:
        raise OMRError("Không xác định được 4 góc phiếu")
    # 4 điểm phải tạo tứ giác lồi, chiếm phần lớn ảnh – nếu không, thà báo lỗi để GV xem lại còn hơn đọc sai mà không biết
    def _z(a, b):
        return float(a[0] * b[1] - a[1] * b[0])
    cross = [_z(pts[(i + 1) % 4] - pts[i], pts[(i + 2) % 4] - pts[(i + 1) % 4]) for i in range(4)]
    if not (all(c > 0 for c in cross) or all(c < 0 for c in cross)) or cv2.contourArea(pts) < 0.2 * area:
        raise OMRError("Không xác định được 4 góc phiếu (ô định vị bị che hoặc bị vẽ đè)")
    return pts


def warp(g: np.ndarray) -> np.ndarray:
    import cv2
    g = _exif_free_resize(g)
    src = find_fiducials(g)
    qw = np.linalg.norm(src[1] - src[0]) + np.linalg.norm(src[2] - src[3])
    qh = np.linalg.norm(src[3] - src[0]) + np.linalg.norm(src[2] - src[1])
    if qw > qh * 1.1:                             # ảnh chụp ngang: xoay về dọc rồi tìm lại 4 góc
        g = cv2.rotate(g, cv2.ROTATE_90_CLOCKWISE)
        src = find_fiducials(g)
    dst = np.array([(x * PX, y * PX) for x, y in
                    [(10 + FID / 2, 10 + FID / 2), (PAGE_W - 10 - FID / 2, 10 + FID / 2),
                     (PAGE_W - 10 - FID / 2, PAGE_H - 10 - FID / 2), (10 + FID / 2, PAGE_H - 10 - FID / 2)]], dtype=np.float32)
    ratio = min(qw, qh) / max(qw, qh)
    if not 0.55 < ratio < 0.82:                   # tỷ lệ khoảng cách 4 ô định vị của phiếu A4 ≈ 183/270 = 0,68
        raise OMRError("4 góc tìm được không khớp khổ phiếu A4 (ô định vị bị che hoặc ảnh không phải phiếu của hệ thống)")
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(g, M, (int(PAGE_W * PX), int(PAGE_H * PX)), flags=cv2.INTER_LINEAR, borderValue=255)
    for (x, y) in FID_POS:                         # kiểm tra lại: sau khi nắn, cả 4 ô định vị phải nằm đúng chỗ và đậm
        cell = out[int((y + 1.5) * PX):int((y + FID - 1.5) * PX), int((x + 1.5) * PX):int((x + FID - 1.5) * PX)]
        if cell.size == 0 or cell.mean() > 110:
            raise OMRError("Nắn phiếu không khớp ô định vị – chụp lại phiếu thẳng hơn, đủ 4 góc")
    # ảnh chụp lật ngược (xoay 180°): vạch đen nhận chiều chỉ có ở giữa mép TRÊN phiếu
    bx, by, bw_, bh = ORIENT_BAR
    def bar(img):
        return img[int((by + 0.6) * PX):int((by + bh - 0.6) * PX), int((bx + 2) * PX):int((bx + bw_ - 2) * PX)].mean()
    flipped = cv2.rotate(out, cv2.ROTATE_180)
    if bar(flipped) < bar(out):
        out = flipped
    return out


def _fill(bw: np.ndarray, x: float, y: float, r: float) -> float:
    cx, cy, rr = int(round(x * PX)), int(round(y * PX)), max(2, int(r * PX * 0.70))
    y0, y1, x0, x1 = max(cy - rr, 0), cy + rr + 1, max(cx - rr, 0), cx + rr + 1
    patch = bw[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0 - cy:y1 - cy, x0 - cx:x1 - cx]
    mask = xx * xx + yy * yy <= rr * rr
    if not mask.any():
        return 0.0
    return float(patch[mask[:patch.shape[0], :patch.shape[1]]].mean() / 255)


def _cover(bw: np.ndarray, x: float, y: float, r: float) -> float:
    """Tỷ lệ điểm ảnh có mực trong ô: ô tô kín ≈ 1, ô bị gạch chéo (dấu X) chỉ ≈ 0,4 dù độ đậm trung bình tương đương bút chì nhạt."""
    cx, cy, rr = int(round(x * PX)), int(round(y * PX)), max(2, int(r * PX * 0.70))
    y0, y1, x0, x1 = max(cy - rr, 0), cy + rr + 1, max(cx - rr, 0), cx + rr + 1
    patch = bw[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0 - cy:y1 - cy, x0 - cx:x1 - cx]
    mask = (xx * xx + yy * yy <= rr * rr)[:patch.shape[0], :patch.shape[1]]
    return float((patch[mask] > 0.3 * 255).mean()) if mask.any() else 0.0


SOLID = 0.45                   # độ phủ mực (trừ phần chữ in sẵn của ô trống cùng hàng) dưới ngưỡng này là ô gạch bỏ / tô không kín


def _pick(fills: dict) -> tuple[list, float]:
    """fills: {nhãn: tỷ lệ mực} của một hàng -> (các nhãn được tô, độ tin cậy 0..1)."""
    vals = sorted(fills.values())
    base = vals[0] if len(vals) > 1 else 0.1
    marked = [k for k, v in fills.items() if v >= FILL_MIN and v - base >= FILL_GAP]
    top = max(vals)
    if not marked:
        conf = 1 - min(1, top / FILL_MIN)          # càng gần ngưỡng càng kém chắc chắn
        return [], round(max(0.0, min(1.0, 0.5 + conf / 2)), 2)
    second = max([v for k, v in fills.items() if k not in marked], default=base)
    return marked, round(max(0.0, min(1.0, (min(fills[k] for k in marked) - second) / 0.5)), 2)


def read_sheet(g: np.ndarray, o: SheetOptions) -> dict:
    import cv2
    L = sheet_layout(o)
    wimg = warp(g)
    # chuẩn hóa nền (bóng đổ, ánh sáng không đều): chia cho nền ước lượng bằng phép đóng hình thái + làm mờ
    bg = cv2.GaussianBlur(cv2.morphologyEx(wimg, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))), (31, 31), 0)
    norm = np.clip(wimg.astype(np.float32) / np.maximum(bg.astype(np.float32), 1) * 255, 0, 255)
    bw = (255 - norm)                              # độ đậm mực 0..255 (vết tẩy/bút chì nhạt cho giá trị thấp)
    r = L["r"]
    issues = []
    marks = []                                    # (x, y, trạng thái) để vẽ ảnh soát

    def digits(cells, ncol, what):
        out = ""
        for col in range(ncol):
            fills = {b["value"]: _fill(bw, b["x"], b["y"], r) for b in cells if b["col"] == col}
            m, conf = _pick(fills)
            for b in cells:
                if b["col"] == col and b["value"] in m:
                    marks.append((b["x"], b["y"], "ok" if len(m) == 1 else "multi"))
            if len(m) == 1:
                out += str(m[0])
            else:
                out += "?"
                if len(m) > 1:
                    issues.append(f"{what}: cột {col + 1} tô nhiều ô")
        if "?" in out and out.strip("?"):
            issues.append(f"{what} chưa tô đủ: {out}")
        return out.strip("?") if set(out) == {"?"} else out
    student = digits(L["student"], o.student_digits, "MSSV")
    # mã đề: một hàng ô tô, mỗi ô là một mã đề (phiếu theo mẫu trường)
    version = ""
    if L["version"]:
        m, _conf = _pick({b["code"]: _fill(bw, b["x"], b["y"], r) for b in L["version"]})
        for b in L["version"]:
            if b["code"] in m:
                marks.append((b["x"], b["y"], "ok" if len(m) == 1 else "multi"))
        if len(m) == 1:
            version = m[0]
        elif len(m) > 1:
            issues.append(f"Mã đề: tô nhiều ô ({', '.join(m)})")
    answers, conf_min = {}, 1.0
    by_q = {}
    for b in L["answers"]:
        by_q.setdefault(b["q"], []).append(b)
    for q, bs in by_q.items():
        fills = {b["label"]: _fill(bw, b["x"], b["y"], r) for b in bs}
        m, conf = _pick(fills)
        weak = []
        if m:
            # độ phủ so với ô trống nhạt nhất cùng hàng: bỏ phần mực của chữ cái in sẵn trong ô (phiếu theo mẫu in chữ đậm)
            cover_all = {b["label"]: _cover(bw, b["x"], b["y"], r) for b in bs}
            base = min(v for k, v in cover_all.items() if k not in m) if len(m) < len(bs) else 0.0
            cover = {k: cover_all[k] - base for k in m}
            solid = [k for k in m if cover[k] >= SOLID]
            weak = [k for k in m if cover[k] < SOLID]
            if solid and weak:                    # đổi đáp án bằng cách gạch chéo ô cũ: lấy ô tô kín, bỏ ô bị gạch
                m = solid
                weak = []
        conf_min = min(conf_min, conf)
        answers[q] = "".join(sorted(m))
        for b in bs:
            if b["label"] in m:
                marks.append((b["x"], b["y"], "ok" if len(m) == 1 else "multi"))
        if len(m) > 1:
            issues.append(f"Câu {q}: tô {len(m)} ô ({', '.join(sorted(m))})")
        elif weak:
            issues.append(f"Câu {q}: ô {', '.join(weak)} có vết gạch hoặc tô không kín, cần xem lại")
        elif conf < 0.35:
            issues.append(f"Câu {q}: vết tô mờ, cần xem lại")
    return {"student_code": student, "version_code": version, "answers": answers, "issues": issues,
            "confidence": round(conf_min, 2), "image": _review_image(wimg, marks, r)}


def _review_image(wimg: np.ndarray, marks: list, r: float) -> str:
    import cv2
    col = cv2.cvtColor(wimg, cv2.COLOR_GRAY2BGR)
    for x, y, st in marks:
        color = (40, 170, 40) if st == "ok" else (30, 30, 220)
        cv2.circle(col, (int(x * PX), int(y * PX)), int(r * PX + 3), color, 2)
    small = cv2.resize(col, (int(col.shape[1] * 0.62), int(col.shape[0] * 0.62)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
