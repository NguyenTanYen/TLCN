@echo off
chcp 65001 >nul
title CHIA SE HE THONG RA INTERNET (Cloudflare Tunnel) - KHONG DONG CUA SO NAY
cd /d "%~dp0"
if not exist tools\cloudflared.exe (
  echo Dang tai cloudflared tu GitHub cua Cloudflare ^(mien phi, khoang 60 MB^)...
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'tools\cloudflared.exe'"
  if errorlevel 1 ( echo Tai that bai. Kiem tra mang roi chay lai. & pause & exit /b 1 )
)
echo.
echo Hay dam bao he thong dang chay tai http://localhost:8000 ^(5_CHAY_HE_THONG.bat hoac 9_BAT_TU_KHOI_DONG...^)
echo Doi vai giay, dong chu "https://....trycloudflare.com" hien ben duoi la LINK CONG KHAI - gui cho nguoi can xem.
echo Link doi moi lan chay lai. Dong cua so nay = tat chia se.
echo ================================================================
tools\cloudflared.exe tunnel --url http://localhost:8000
pause
