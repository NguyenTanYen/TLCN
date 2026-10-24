@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
echo [%date% %time%] > logs\tien_trinh.log
tasklist /v /fi "imagename eq python.exe" >> logs\tien_trinh.log 2>&1
tasklist /v /fi "imagename eq php.exe" >> logs\tien_trinh.log 2>&1
tasklist /v /fi "imagename eq php-cgi.exe" >> logs\tien_trinh.log 2>&1
echo --- cuoi log demo >> logs\tien_trinh.log
powershell -NoProfile -Command "Get-Content -Tail 5 -Encoding UTF8 'logs\demo_day_du.log'" >> logs\tien_trinh.log 2>&1
