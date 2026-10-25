# Hướng dẫn triển khai lên VPS (Ubuntu 22.04 + Docker + Nginx)

Kiến trúc: **Nginx** (web server, cổng 80/443, HTTPS Let's Encrypt) → *hệ thống phân tích CĐR* (FastAPI, cổng 8000 nội bộ) và *Moodle 4.5* (Apache/PHP nội bộ) → *MySQL 8*. Tất cả chạy bằng `docker compose`.
Địa chỉ dùng dịch vụ sslip.io nên **không cần mua tên miền**: `https://app.<IP>.sslip.io` (hệ thống) và `https://lms.<IP>.sslip.io` (Moodle).

> Đã chạy thử trên máy ảo Google Cloud (gói miễn phí/dùng thử). Máy ảo dùng thử sẽ ngừng khi hết tín dụng: xóa VM sau khi demo để tránh phát sinh phí.

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

## 5. Cài plugin, giao diện UTE, tiếng Việt và nối hai hệ thống (một lần)
```
sudo bash sau_cai_dat.sh
```
Script gộp các bước đã chạy thật từng phần trên Google Cloud (bản gộp một lệnh chưa được chạy nguyên khối) và tự: dựng Moodle + app, nâng cấp plugin `local_clo` (v1.6.0) và theme `ute`, lấy token Web Service + khóa SSO ghi vào `docker-compose.override.yml`, bật giao diện UTE, cài gói tiếng Việt, xóa cache. Chạy lại an toàn sau mỗi lần cập nhật mã nguồn.
Lưu ý khi tự làm tay: Moodle chạy trong Docker cần biến `APACHE_DOCUMENT_ROOT=/var/www/html` (đã có trong compose); gói tiếng Việt phải tải về `moodledata/lang/vi`; app chỉ gọi được Moodle khi có `MOODLE_WS_TOKEN` và `MOODLE_SSO_SECRET`.
Đăng nhập Moodle (`admin` / mật khẩu `MOODLE_ADMIN_PASS` trong `.env`; quên mật khẩu: `php admin/cli/reset_password.php --username=admin --password=...` trong container moodle).

### Tạo lớp học phần ⇄ khóa học Moodle
Khi Bộ môn tạo lớp (hoặc đổi giảng viên) trong hệ thống, hệ thống tự gọi plugin để **tạo khóa học Moodle mang mã lớp, tạo tài khoản và ghi danh giảng viên + sinh viên**. Sinh viên thêm vào lớp sau đó: bấm **Đồng bộ GV/SV lên Moodle** ở trang lớp. Tài khoản Moodle mới có mật khẩu ban đầu `MOODLE_NEW_USER_PASSWORD` (mặc định `Sv@123456` – đổi khi triển khai thật).

## 6. Nạp dữ liệu demo
- Hệ thống: tự có dữ liệu minh họa ngay lần đầu (`DEMO_DATA=1`).
- Moodle (khóa DBMS330284_01, 40 sinh viên, Quiz có bài làm, Offline Quiz):
```
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml --env-file .env --profile demo run --rm --build demo
```
Tài khoản: gv.son / Gv@123456 · admin / Admin@123 (hệ thống) · sinh viên 22130001… / Sv@123456 (Moodle).

## 7. Vận hành
- Xem lỗi: `docker compose -f docker-compose.prod.yml logs --tail=100 app` (hoặc `moodle`, `nginx`, `db`).
- Khởi động lại: `docker compose -f docker-compose.prod.yml restart app`. Dịch vụ tự bật lại khi máy khởi động (`restart: unless-stopped`).
- Gia hạn chứng chỉ (3 tháng/lần): `bash bat_https.sh email`.
- Sao lưu: `docker compose -f docker-compose.prod.yml exec db mysqldump -uroot -p<DB_ROOT_PASS> --all-databases > sao_luu.sql`.
- Gỡ: `docker compose -f docker-compose.prod.yml down` (thêm `-v` để xóa cả dữ liệu).
