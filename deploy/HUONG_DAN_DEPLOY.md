# Hướng dẫn triển khai lên VPS (Ubuntu 22.04 + Docker + Nginx)

Kiến trúc: **Nginx** (web server, cổng 80/443, HTTPS Let's Encrypt) → *hệ thống phân tích CĐR* (FastAPI, cổng 8000 nội bộ) và *Moodle 4.5* (Apache/PHP nội bộ) → *MySQL 8*. Tất cả chạy bằng `docker compose`.
Địa chỉ dùng dịch vụ sslip.io nên **không cần mua tên miền**: `https://app.<IP>.sslip.io` (hệ thống) và `https://lms.<IP>.sslip.io` (Moodle).

> Chưa được chạy thử trên VPS thật trong môi trường của nhóm; hãy dựng thử trước ngày bảo vệ.

## 1. Yêu cầu máy chủ
VPS Ubuntu 22.04, tối thiểu **2 vCPU, 4 GB RAM, 40 GB SSD**, có IP công khai và **mở cổng 80, 443, 22**.

## 2. Cài Docker (SSH vào máy: `ssh root@<IP>`)
```
curl -fsSL https://get.docker.com | sh
apt-get install -y unzip
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 3. Đưa mã nguồn lên
Từ máy Windows (PowerShell): `scp "D:\3. TLCN\NopBai\MaNguon\HeThong_TLCN_Nhom01.zip" root@<IP>:~`
Trên VPS:
```
unzip -q HeThong_TLCN_Nhom01.zip && cd HeThong/deploy
cp .env.example .env && nano .env      # IP_CONG_KHAI, mật khẩu CSDL, mật khẩu admin Moodle, JWT_SECRET
```

## 4. Chạy (HTTP rồi tự bật HTTPS)
```
bash trien_khai.sh email_cua_ban@gmail.com
```
Script dựng 4 dịch vụ (db, moodle, app, nginx), đợi Moodle cài lần đầu, lấy chứng chỉ Let's Encrypt cho hai địa chỉ rồi chuyển Nginx sang HTTPS. Nếu bước lấy chứng chỉ lỗi (Moodle chưa cài xong), chờ vài phút rồi chạy lại `bash bat_https.sh email_cua_ban@gmail.com`.

## 5. Cài plugin và theme Moodle (một lần)
```
C="docker compose -f docker-compose.prod.yml"
$C cp ../moodle/local/clo moodle:/var/www/html/local/clo
$C cp ../moodle/theme/ute moodle:/var/www/html/theme/ute
$C exec moodle chown -R www-data:www-data /var/www/html/local/clo /var/www/html/theme/ute
$C exec -u www-data moodle php admin/cli/upgrade.php --non-interactive
$C exec -u www-data moodle php local/clo/cli/setup.php
```
Đăng nhập Moodle (`admin` / mật khẩu trong `.env`) → Quản trị trang → Plugin → Local plugins → CLO → **App URL** = `https://app.<IP>.sslip.io`.

## 6. Nạp dữ liệu demo
- Hệ thống: tự có dữ liệu minh họa ngay lần đầu (`DEMO_DATA=1`).
- Moodle (khóa DBMS330284_01, 40 sinh viên, Quiz có bài làm, Offline Quiz):
```
docker compose -f docker-compose.prod.yml --env-file .env --profile demo run --rm demo
```
Tài khoản: gv.son / Gv@123456 · admin / Admin@123 (hệ thống) · sinh viên 22130001… / Sv@123456 (Moodle).

## 7. Vận hành
- Xem lỗi: `docker compose -f docker-compose.prod.yml logs --tail=100 app` (hoặc `moodle`, `nginx`, `db`).
- Khởi động lại: `docker compose -f docker-compose.prod.yml restart app`. Dịch vụ tự bật lại khi máy khởi động (`restart: unless-stopped`).
- Gia hạn chứng chỉ (3 tháng/lần): `bash bat_https.sh email`.
- Sao lưu: `docker compose -f docker-compose.prod.yml exec db mysqldump -uroot -p<DB_ROOT_PASS> --all-databases > sao_luu.sql`.
- Gỡ: `docker compose -f docker-compose.prod.yml down` (thêm `-v` để xóa cả dữ liệu).
