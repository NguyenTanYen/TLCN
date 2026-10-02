"""Sinh đề theo ma trận đề thi (UC-02).

Ma trận đề là bảng **chương × mức Bloom** ghi số câu cần lấy ở mỗi ô; kèm theo yêu cầu **phủ CLO**
(mỗi CLO trong phạm vi bài có tối thiểu một số câu). Có hai cách dùng:

* **Tự động:** giảng viên chỉ nhập số câu (và tùy chọn phạm vi chương, phân bố mức độ). Hệ thống tự lập ma trận:
  chia số câu cho các chương theo lượng câu sẵn có (mỗi chương ít nhất 1 câu khi đủ số câu), chia theo mức Bloom
  theo tỷ lệ mong muốn, rồi lấp từng ô trong giới hạn số câu sẵn có của ô đó.
* **Theo ma trận của giảng viên:** giảng viên nhập số câu từng ô; ô nào ngân hàng không đủ câu thì báo thiếu cụ thể.

Trong mỗi ô, câu được chọn để **phủ đều CLO** (ưu tiên CLO còn thiếu), tránh câu có DI âm/thấp, ưu tiên câu ít được dùng;
yếu tố ngẫu nhiên (có `seed`) giúp sinh nhiều đề khác nhau từ cùng một ma trận.
Kiểm tra chương: chỉ lấy câu trong các chương được chọn; CLO không có câu nào trong các chương đó được báo là
"không đo trong bài này" (thông tin), không tính là thiếu.
Hàm `generate` là hàm thuần (không truy cập CSDL) để kiểm thử độc lập.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# Tỷ lệ % mặc định theo mức Bloom (1 Nhớ … 6 Sáng tạo) – "cân bằng"
PRESETS = {
    "balanced": {1: 20, 2: 30, 3: 30, 4: 15, 5: 5, 6: 0},
    "basic": {1: 35, 2: 40, 3: 20, 4: 5, 5: 0, 6: 0},
    "advanced": {1: 10, 2: 20, 3: 35, 4: 25, 5: 10, 6: 0},
}


@dataclass
class Q:
    id: int
    outline_id: int | None
    bloom: int
    clos: dict[int, float]          # clo_id -> trọng số
    avg_p: float | None = None
    avg_di: float | None = None
    n_exams: int = 0


@dataclass
class Result:
    items: list[int] = field(default_factory=list)
    target: dict[tuple, int] = field(default_factory=dict)     # (outline_id, bloom) -> số câu
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def largest_remainder(total: int, weights: dict, caps: dict | None = None) -> dict:
    """Chia `total` thành các phần nguyên theo tỷ lệ `weights` bằng phương pháp phần dư lớn nhất (Hamilton):
    lấy phần nguyên của phần lý tưởng, phần còn lại cấp cho khóa có phần lẻ lớn nhất (hòa thì khóa có trọng số lớn hơn).
    Khóa chạm trần `caps` thì phần thừa được chia lại cho các khóa còn chỗ."""
    out = {k: 0 for k in weights}
    cap = lambda k: caps.get(k, 0) if caps is not None else 10 ** 9
    remaining = max(total, 0)
    while remaining > 0:
        active = [k for k, w in weights.items() if w > 0 and out[k] < cap(k)]
        if not active:
            break
        sw = sum(weights[k] for k in active)
        ideal = {k: remaining * weights[k] / sw for k in active}
        given = 0
        for k in active:
            add = min(math.floor(ideal[k] + 1e-9), cap(k) - out[k])
            out[k] += add; given += add
        left = remaining - given
        for k in sorted(active, key=lambda k: (round(ideal[k] - math.floor(ideal[k] + 1e-9), 9), weights[k]), reverse=True):
            if left == 0:
                break
            if out[k] < cap(k):
                out[k] += 1; left -= 1; given += 1
        remaining -= given
        if given == 0:
            break
    return out


def _quality(q: Q, prefer_unused: bool) -> float:
    s = 0.0
    if q.avg_di is not None:
        s += -3 if q.avg_di < 0 else (-1 if q.avg_di < 0.2 else (0.5 if q.avg_di >= 0.3 else 0))
    if q.avg_p is not None and (q.avg_p > 0.9 or q.avg_p < 0.2):
        s -= 0.5
    if prefer_unused:
        s -= 0.3 * q.n_exams
    return s


def auto_matrix(pool: list[Q], n: int, bloom_mix: dict[int, float]) -> dict[tuple, int]:
    """Lập ma trận chương × Bloom tự động cho `n` câu từ các câu sẵn có."""
    avail: dict[tuple, int] = {}
    for q in pool:
        avail[(q.outline_id, q.bloom)] = avail.get((q.outline_id, q.bloom), 0) + 1
    chapters = sorted({k[0] for k in avail}, key=lambda x: (x is None, x))
    ch_avail = {c: sum(v for k, v in avail.items() if k[0] == c) for c in chapters}
    bl_avail = {b: sum(v for k, v in avail.items() if k[1] == b) for b in range(1, 7)}
    # Chương: mỗi chương ít nhất 1 câu (nếu đủ số câu), phần còn lại theo lượng câu sẵn có
    ch_q = {c: 0 for c in chapters}
    if n >= len(chapters):
        for c in chapters:
            ch_q[c] = 1
        rest = largest_remainder(n - len(chapters), ch_avail, {c: ch_avail[c] - 1 for c in chapters})
        for c in chapters:
            ch_q[c] += rest[c]
    else:
        ch_q = largest_remainder(n, ch_avail, ch_avail)
    # Mức Bloom: theo tỷ lệ mong muốn, giới hạn bởi số câu sẵn có; nếu thiếu thì lấy bù từ mức khác
    w = {b: bloom_mix.get(b, 0) for b in range(1, 7)}
    bl_q = largest_remainder(n, w, bl_avail)
    short = n - sum(bl_q.values())
    if short > 0:
        extra = largest_remainder(short, {b: 1 for b in range(1, 7)}, {b: bl_avail[b] - bl_q[b] for b in range(1, 7)})
        for b in extra:
            bl_q[b] += extra[b]
    # Lấp ô: mỗi lần thêm 1 câu vào ô có (thiếu hụt chương + thiếu hụt mức) lớn nhất còn câu
    target = {k: 0 for k in avail}
    for _ in range(n):
        best, key = None, None
        for k, a in avail.items():
            if target[k] >= a:
                continue
            c, b = k
            score = (ch_q[c] - sum(v for kk, v in target.items() if kk[0] == c)) * 2 + \
                    (bl_q[b] - sum(v for kk, v in target.items() if kk[1] == b))
            if best is None or score > best:
                best, key = score, k
        if key is None:
            break
        target[key] += 1
    return {k: v for k, v in target.items() if v}


def generate(pool: list[Q], n: int | None = None, matrix: dict[tuple, int] | None = None, scope_clos: list[int] | None = None,
             bloom_mix: dict[int, float] | None = None, min_per_clo: int | None = None, fixed: list[int] | None = None,
             prefer_unused: bool = True, seed: int | None = None, names: dict | None = None) -> Result:
    """Chọn câu theo ma trận. `matrix` (nếu có) là ma trận của giảng viên; nếu không, lập tự động cho `n` câu."""
    names = names or {}
    ch_name = names.get("chapter", lambda c: f"chương {c}")
    bl_name = names.get("bloom", lambda b: f"mức {b}")
    clo_name = names.get("clo", lambda c: f"CLO {c}")
    rnd = random.Random(seed)
    res = Result()
    fixed = [qid for qid in (fixed or []) if any(q.id == qid for q in pool)]
    by_id = {q.id: q for q in pool}
    if matrix:
        n = sum(matrix.values())
    if not n or n <= 0:
        res.errors.append("Số câu của đề phải lớn hơn 0")
        return res
    if n > len(pool):
        res.errors.append(f"Ngân hàng chỉ có {len(pool)} câu hợp lệ (đã gán CLO và Bloom, chưa Hủy) trong phạm vi đã chọn, "
                          f"không đủ {n} câu – hãy giảm số câu, mở rộng phạm vi chương hoặc bổ sung câu hỏi")
    avail: dict[tuple, list[Q]] = {}
    for q in pool:
        avail.setdefault((q.outline_id, q.bloom), []).append(q)
    if matrix:
        target = {}
        for k, want in matrix.items():
            if want <= 0:
                continue
            have = len(avail.get(k, []))
            if have < want:
                res.errors.append(f"{ch_name(k[0]).capitalize()} – {bl_name(k[1])}: cần {want} câu, ngân hàng chỉ có {have} câu")
            target[k] = min(want, have)
    else:
        mix = bloom_mix or PRESETS["balanced"]
        target = auto_matrix(pool, n, mix)
        got_bl = {}
        for (c, b), v in target.items():
            got_bl[b] = got_bl.get(b, 0) + v
        want_bl = largest_remainder(n, {b: mix.get(b, 0) for b in range(1, 7)})
        for b in range(1, 7):
            if want_bl[b] > got_bl.get(b, 0):
                res.warnings.append(f"Mức {bl_name(b)} cần khoảng {want_bl[b]} câu theo tỷ lệ đã chọn nhưng ngân hàng chỉ có "
                                    f"{len([q for q in pool if q.bloom == b])} câu – đã lấy bù ở mức khác")
    res.target = target

    # Phạm vi CLO và yêu cầu phủ tối thiểu
    pool_clos = sorted({c for q in pool for c in q.clos})
    clos = [c for c in (scope_clos or pool_clos) if c in pool_clos]
    if scope_clos:
        for c in scope_clos:
            if c not in pool_clos:
                res.info.append(f"{clo_name(c)} không có câu nào trong phạm vi chương đã chọn – bài này không đo {clo_name(c)}")
    k_min = min_per_clo if min_per_clo is not None else (1 if n < 2 * max(len(clos), 1) else 2)
    cover = {c: 0 for c in clos}

    chosen: list[int] = []
    for qid in fixed:
        chosen.append(qid)
        for c in by_id[qid].clos:
            if c in cover:
                cover[c] += 1
    # Lấp từng ô: ô ít lựa chọn trước để không "tiêu" mất câu hiếm
    fixed_in = {}
    for qid in fixed:
        k = (by_id[qid].outline_id, by_id[qid].bloom)
        fixed_in[k] = fixed_in.get(k, 0) + 1
    order = sorted(target, key=lambda k: len(avail.get(k, [])) - target[k])
    for k in order:
        need = target[k] - fixed_in.get(k, 0)
        cand = [q for q in avail.get(k, []) if q.id not in chosen]
        for _ in range(max(need, 0)):
            if not cand:
                break
            def score(q):
                gain = sum(w * (3 if cover.get(c, k_min) < k_min else 0.5) for c, w in q.clos.items() if c in cover)
                return gain + _quality(q, prefer_unused) + rnd.random() * 0.4
            q = max(cand, key=score)
            cand.remove(q); chosen.append(q.id)
            for c in q.clos:
                if c in cover:
                    cover[c] += 1

    # Sửa phủ CLO: đổi câu cùng ô (giữ nguyên ma trận) nếu còn CLO thiếu
    for c in [c for c in clos if cover[c] < k_min]:
        for _ in range(k_min - cover[c]):
            swapped = False
            for qid in list(chosen):
                if qid in fixed:
                    continue
                old = by_id[qid]
                if c in old.clos:
                    continue
                if any(cover[x] - 1 < k_min for x in old.clos if x in cover):
                    continue
                alt = [q for q in avail.get((old.outline_id, old.bloom), []) if q.id not in chosen and c in q.clos]
                if alt:
                    new = max(alt, key=lambda q: _quality(q, prefer_unused))
                    chosen[chosen.index(qid)] = new.id
                    for x in old.clos:
                        if x in cover:
                            cover[x] -= 1
                    for x in new.clos:
                        if x in cover:
                            cover[x] += 1
                    swapped = True
                    break
            if not swapped:
                break
    for c in clos:
        have = len([q for q in pool if c in q.clos])
        if cover[c] < k_min:
            why = (f"ngân hàng chỉ có {have} câu đo {clo_name(c)}" if have < k_min
                   else "các câu đo CLO này không nằm trong ô nào của ma trận")
            res.warnings.append(f"{clo_name(c)} chỉ có {cover[c]} câu trong đề (yêu cầu tối thiểu {k_min}) – {why}; "
                                "kết luận đạt/không đạt CLO này sẽ kém tin cậy")
    if len(chosen) < n and not res.errors:
        res.errors.append(f"Chỉ chọn được {len(chosen)}/{n} câu theo ma trận")
    res.items = chosen
    return res
