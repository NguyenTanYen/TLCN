#!/usr/bin/env bash
# Triển khai giai đoạn 1 (HTTP) rồi tự bật HTTPS.   Cách dùng:  bash trien_khai.sh email_cua_ban@gmail.com
set -euo pipefail
cd "$(dirname "$0")"
EMAIL="${1:?Dùng: bash trien_khai.sh <email_cua_ban>}"
[ -f .env ] || { echo "Chưa có .env: cp .env.example .env rồi sửa"; exit 1; }
set -a; . ./.env; set +a
sed "s/IP_CONG_KHAI/${IP_CONG_KHAI}/g" nginx/http.conf > nginx/active.conf
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
echo "Chờ Moodle cài lần đầu (vài phút)…"; sleep 90
bash bat_https.sh "$EMAIL"
