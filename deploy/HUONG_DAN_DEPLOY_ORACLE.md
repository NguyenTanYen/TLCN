# Deploy miễn phí 24/7 (Oracle Cloud Always Free) – Hệ thống + Moodle

> Bộ cấu hình này **chưa được chạy thử trên máy chủ thật**; hãy dựng thử trước buổi bảo vệ ít nhất 1–2 ngày.

## 1. Tạo máy chủ
1. Đăng ký https://www.oracle.com/cloud/free/ (cần thẻ quốc tế để xác minh).
2. Compute → Create instance: image **Ubuntu 22.04**, shape **Ampere (VM.Standard.A1.Flex)** 2–4 OCPU, 12–24 GB RAM; tải khóa SSH về.
3. Networking → Subnet → Security List: mở **Ingress TCP 80 và 443** (nguồn 0.0.0.0/0).
4. Ghi lại **IP công khai** của máy.

## 2. Cài Docker (SSH vào máy)
```
ssh -i khoa.key ubuntu@<IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT && sudo netfilter-persistent save
```

## 3. Đưa mã nguồn lên và chạy
```
scp -i khoa.key HeThong_TLCN_Nhom01.zip ubuntu@<IP>:~
ssh -i khoa.key ubuntu@<IP>
sudo apt-get install -y unzip && unzip HeThong_TLCN_Nhom01.zip && cd HeThong/deploy
cp .env.example .env && nano .env        # sửa IP_CONG_KHAI và các mật khẩu
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml logs -f app moodle   # xem tiến trình (Moodle cài lần đầu vài phút)
```

## 4. Địa chỉ sau khi chạy
- Hệ thống: `https://app.<IP>.sslip.io`  (gv.son / Gv@123456, admin / Admin@123)
- Moodle: `https://lms.<IP>.sslip.io`  (admin / mật khẩu bạn đặt ở MOODLE_ADMIN_PASS)
- HTTPS do Caddy tự lấy chứng chỉ Let's Encrypt (dùng dịch vụ sslip.io nên không cần mua tên miền).

## 5. Cài plugin Moodle (một lần)
Chép plugin và theme vào volume mã nguồn Moodle rồi nâng cấp:
```
docker compose -f docker-compose.prod.yml cp ../moodle/local/clo moodle:/var/www/html/local/clo
docker compose -f docker-compose.prod.yml cp ../moodle/theme/ute moodle:/var/www/html/theme/ute
docker compose -f docker-compose.prod.yml exec moodle chown -R www-data:www-data /var/www/html/local/clo /var/www/html/theme/ute
docker compose -f docker-compose.prod.yml exec -u www-data moodle php admin/cli/upgrade.php --non-interactive
docker compose -f docker-compose.prod.yml exec -u www-data moodle php local/clo/cli/setup.php
```
Sau đó vào Moodle → Quản trị → Plugin → Local plugins → CLO: đặt **App URL** = `https://app.<IP>.sslip.io`.

## 6. Nạp dữ liệu demo (để có sẵn môn học, 40 sinh viên, bài làm)
- **Hệ thống phân tích**: tự có dữ liệu minh họa ngay lần chạy đầu (DEMO_DATA=1: môn DBMS330284, CLO, ngân hàng câu hỏi, lớp…).
- **Moodle** (khóa học DBMS330284_01, 40 tài khoản SV mật khẩu `Sv@123456`, GV `gv.son`/`Gv@123456`, Quiz + bài làm, Offline Quiz): sau khi xong mục 5 chạy một lần
```
docker compose -f docker-compose.prod.yml --env-file .env --profile demo run --rm demo
```
Lệnh này dựng lại CSDL hệ thống + dữ liệu demo rồi tạo dữ liệu thật trên Moodle (mất vài phút) – giống bước `4_TAO_DU_LIEU_DEMO_TREN_MOODLE.bat` trên máy bạn. Chưa chạy thử trong Docker: nếu lỗi, gửi dòng báo lỗi cuối cùng để chỉnh.
- Nếu cần chỉ dữ liệu của hệ thống mà không có Moodle demo: bỏ qua lệnh trên.

## 7. Vận hành
- Tự bật lại khi máy khởi động (`restart: unless-stopped`).
- Sao lưu: `docker compose exec db mysqldump -uroot -p<DB_ROOT_PASS> --all-databases > sao_luu.sql`.
- Xem lỗi: `docker compose logs --tail=100 app`.
