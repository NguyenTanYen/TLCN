#!/usr/bin/env bash
# Dựng toàn bộ hệ thống (Nginx + Moodle + hệ thống CĐR + MySQL) trên 1 máy Debian/Ubuntu mới (VD: Google Cloud e2-medium).
# Cách dùng:  sudo bash trien_khai_gcp.sh <IP_công_khai> <email_cho_Lets_Encrypt>
set -uo pipefail
IP="${1:?Dùng: sudo bash trien_khai_gcp.sh <IP_cong_khai> <email>}"; EMAIL="${2:?thiếu email}"
export DEBIAN_FRONTEND=noninteractive
echo "=== BAT DAU $(date)"
if ! swapon --show | grep -q swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
apt-get update -y && apt-get install -y git curl ca-certificates openssl
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
if [ -d /opt/tlcn/.git ]; then git -C /opt/tlcn fetch --depth 1 origin Tanyen && git -C /opt/tlcn reset --hard origin/Tanyen
else git clone --branch Tanyen --depth 1 https://github.com/NguyenTanYen/TLCN.git /opt/tlcn; fi
cd /opt/tlcn/deploy
if [ ! -f .env ]; then
  printf 'IP_CONG_KHAI=%s\nDB_ROOT_PASS=%s\nMOODLE_ADMIN_PASS=%s\nJWT_SECRET=%s\n' "$IP" "$(openssl rand -hex 12)" "Tlcn_$(openssl rand -hex 6)!" "$(openssl rand -hex 24)" > .env
  chmod 600 .env
fi
echo "Moodle admin: admin / $(grep MOODLE_ADMIN_PASS .env | cut -d= -f2-)"
bash trien_khai.sh "$EMAIL"
docker compose -f docker-compose.prod.yml ps
echo "=== XONG $(date)  App: https://app.${IP}.sslip.io   Moodle: https://lms.${IP}.sslip.io"
