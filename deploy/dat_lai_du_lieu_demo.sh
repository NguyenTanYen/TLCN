#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a
C="docker compose -f docker-compose.prod.yml --env-file .env"
[ -f docker-compose.override.yml ] && C="docker compose -f docker-compose.prod.yml -f docker-compose.override.yml --env-file .env"

SAO_LUU="$HOME/sao_luu_truoc_dat_lai_$(date +%Y%m%d_%H%M%S).sql"
echo "== Sao lưu toàn bộ CSDL vào $SAO_LUU"
if ! $C exec -T db mysqldump -uroot -p"${DB_ROOT_PASS}" --all-databases > "$SAO_LUU"; then
  echo "Sao lưu thất bại, dừng lại, chưa thay đổi gì."; exit 1
fi
[ -s "$SAO_LUU" ] || { echo "Tệp sao lưu rỗng, dừng lại, chưa thay đổi gì."; exit 1; }

echo "== Cập nhật plugin local_clo trên Moodle (trang kết quả của sinh viên)"
tar -C ../moodle/local -cf - clo | $C exec -T moodle tar -C /var/www/html/local -xf -
$C exec -T moodle chown -R www-data:www-data /var/www/html/local/clo
$C exec -T moodle php admin/cli/upgrade.php --non-interactive
$C exec -T moodle php admin/cli/purge_caches.php

TOKEN=$(sed -n 's/^ *MOODLE_WS_TOKEN: *"\(.*\)" *$/\1/p' docker-compose.override.yml 2>/dev/null | head -1)
[ -n "$TOKEN" ] || echo "Không đọc được MOODLE_WS_TOKEN, bước học liệu sẽ bị bỏ qua."

echo "== Đặt lại dữ liệu demo (hệ thống + khóa học Moodle DBMS330284_01)"
$C --profile demo run --rm --build -e MOODLE_WS_TOKEN="$TOKEN" demo || { echo "Nạp dữ liệu demo lỗi."; exit 1; }

echo "== Khởi động lại app"
$C restart app
for i in $(seq 1 30); do $C exec -T app python -c 'print(1)' >/dev/null 2>&1 && break; sleep 3; done
sleep 10

echo "== Đồng bộ học liệu từ Moodle vào hệ thống"
$C exec -T app python -m app.cli dong-bo-hoc-lieu
echo "== Kiểm tra và đẩy kết quả đã công bố sang Moodle"
$C exec -T app python -m app.cli kiem-tra-ket-qua
$C exec -T app python -m app.cli day-ket-qua
echo "== Dữ liệu kết quả phía Moodle"
$C exec -T -u www-data moodle php local/clo/cli/kiem_tra_ket_qua.php
echo "XONG. Bản sao lưu cũ: $SAO_LUU"
