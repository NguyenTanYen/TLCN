#!/usr/bin/env bash
# Chạy MỘT LẦN sau trien_khai.sh (và chạy lại an toàn sau mỗi lần cập nhật mã nguồn):
#   nâng cấp plugin local_clo, bật giao diện UTE + tiếng Việt, nối hệ thống với Moodle (token Web Service + khóa SSO).
# Cách dùng:  cd /opt/tlcn/deploy && sudo bash sau_cai_dat.sh
set -uo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a
C="docker compose -f docker-compose.prod.yml -f docker-compose.override.yml --env-file .env"
[ -f docker-compose.override.yml ] || printf 'services:\n  moodle:\n    environment:\n      APACHE_DOCUMENT_ROOT: /var/www/html\n' > docker-compose.override.yml

echo "== Dựng lại Moodle + app theo mã nguồn mới"; $C up -d --build moodle app
echo "== Chờ Moodle sẵn sàng"; for i in $(seq 1 40); do $C exec -T moodle php -r 'echo 1;' >/dev/null 2>&1 && break; sleep 5; done
sleep 20
echo "== Chép plugin local_clo + theme ute vào Moodle (mã Moodle nằm trong volume nên phải chép lại sau mỗi lần cập nhật)"
tar -C ../moodle/local -cf - clo | $C exec -T moodle tar -C /var/www/html/local -xf -
tar -C ../moodle/theme -cf - ute | $C exec -T moodle tar -C /var/www/html/theme -xf -
$C exec -T moodle chown -R www-data:www-data /var/www/html/local/clo /var/www/html/theme/ute
echo "== Nâng cấp plugin / theme"; $C exec -T moodle php admin/cli/upgrade.php --non-interactive
echo "== Cấu hình plugin, lấy token Web Service + khóa SSO"
$C exec -T -u www-data moodle php local/clo/cli/setup.php --appurl="https://app.${IP_CONG_KHAI}.sslip.io" --envfile=/tmp/clo.env
TOKEN=$($C exec -T moodle sh -c 'grep ^MOODLE_WS_TOKEN= /tmp/clo.env | cut -d= -f2-' | tr -d '\r')
SECRET=$($C exec -T moodle sh -c 'grep ^MOODLE_SSO_SECRET= /tmp/clo.env | cut -d= -f2-' | tr -d '\r')
$C exec -T moodle rm -f /tmp/clo.env
if [ -n "$TOKEN" ] && [ -n "$SECRET" ]; then
  cat > docker-compose.override.yml <<YML
services:
  moodle:
    environment:
      APACHE_DOCUMENT_ROOT: /var/www/html
  app:
    environment:
      MOODLE_WS_TOKEN: "${TOKEN}"
      MOODLE_SSO_SECRET: "${SECRET}"
YML
  chmod 600 docker-compose.override.yml
fi
echo "== Giao diện UTE + tiếng Việt"
$C exec -T moodle php admin/cli/cfg.php --name=theme --set=ute
$C exec -T -u www-data moodle bash -c 'mkdir -p /var/www/moodledata/lang && cd /var/www/moodledata/lang && [ -d vi ] || (curl -fsSL https://download.moodle.org/download.php/direct/langpack/4.5/vi.zip -o vi.zip && unzip -oq vi.zip && rm vi.zip)'
$C exec -T moodle php admin/cli/cfg.php --name=lang --set=vi
$C exec -T moodle php admin/cli/purge_caches.php
echo "== Áp token vào app"; $C up -d app
$C ps
echo "XONG. Moodle: https://lms.${IP_CONG_KHAI}.sslip.io   App: https://app.${IP_CONG_KHAI}.sslip.io"
