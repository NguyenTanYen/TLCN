#!/usr/bin/env bash
# Lấy chứng chỉ HTTPS miễn phí (Let's Encrypt) cho 2 địa chỉ sslip.io rồi chuyển Nginx sang HTTPS.
# Chạy MỘT LẦN sau khi `docker compose up -d` đã chạy ở giai đoạn HTTP:   bash bat_https.sh you@email.com
set -euo pipefail
cd "$(dirname "$0")"
EMAIL="${1:?Dùng: bash bat_https.sh <email_cua_ban>}"
set -a; . ./.env; set +a
C="docker compose -f docker-compose.prod.yml --env-file .env"
for H in app lms; do
  $C --profile tools run --rm certbot certonly --webroot -w /var/www/certbot \
     -d "$H.${IP_CONG_KHAI}.sslip.io" --email "$EMAIL" --agree-tos --no-eff-email -n
done
sed "s/IP_CONG_KHAI/${IP_CONG_KHAI}/g" nginx/https.conf > nginx/active.conf
$C exec nginx nginx -s reload
echo "Xong. Hệ thống: https://app.${IP_CONG_KHAI}.sslip.io   Moodle: https://lms.${IP_CONG_KHAI}.sslip.io"
