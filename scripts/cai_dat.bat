@echo off
chcp 65001 >nul
set PYTHONUTF8=1
call "%~dp0cau_hinh.bat"
cd /d "%ROOT%"
set "PY=.venv\Scripts\python.exe"

echo [1/5] Tao moi truong Python va cai thu vien
if not exist "%PY%" (
  where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
)
if not exist "%PY%" (echo Khong thay Python 3.10+. & goto :loi)
"%PY%" -m pip install -q --upgrade pip
"%PY%" -m pip install -q -r backend\requirements.txt || goto :loi

echo [2/5] Khoi tao co so du lieu (can bat MySQL/MariaDB)
pushd backend
"..\%PY%" -m app.cli init-db || (popd & goto :loi)
"..\%PY%" -m app.cli seed-demo || (popd & goto :loi)
"..\%PY%" -m app.cli install-bridge || (popd & goto :loi)
popd

if not defined MOODLE_DIR goto :thieu_moodle
if not defined PHP_BIN goto :thieu_moodle
echo [3/5] Chep giao dien va plugin vao Moodle
xcopy /E /I /Y "moodle\theme\ute" "%MOODLE_DIR%\theme\ute" >nul || goto :loi
xcopy /E /I /Y "moodle\local\clo" "%MOODLE_DIR%\local\clo" >nul || goto :loi
if not exist "moodle\mod\offlinequiz\version.php" powershell -NoProfile -Command "Expand-Archive -Force 'moodle\mod\offlinequiz_v4.5.4.zip' 'moodle\mod'" || goto :loi
xcopy /E /I /Y "moodle\mod\offlinequiz" "%MOODLE_DIR%\mod\offlinequiz" >nul || goto :loi

echo [4/5] Nang cap Moodle va cau hinh ket noi
"%PHP_BIN%" -d max_input_vars=5000 "%MOODLE_DIR%\admin\cli\upgrade.php" --non-interactive || goto :loi
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\cfg.php" --name=theme --set=ute || goto :loi
"%PHP_BIN%" "%MOODLE_DIR%\local\clo\cli\setup.php" --appurl=http://localhost:%APP_PORT% --envfile="%ROOT%\backend\cau_hinh.env" || goto :loi

echo [5/5] Tao tai khoan CSDL chi doc cho he thong
"%PY%" tools\tao_tai_khoan_csdl.py backend\cau_hinh.env || goto :loi
"%PHP_BIN%" "%MOODLE_DIR%\admin\cli\purge_caches.php"
echo.
echo Xong. Chay scripts\chay.bat de khoi dong he thong.
pause
exit /b 0

:thieu_moodle
echo Khong xac dinh duoc Moodle 4.5 / php.exe - bo qua buoc Moodle. Khai bao trong scripts\cau_hinh_may.bat roi chay lai.
pause
exit /b 1

:loi
echo *** Loi o buoc tren. Kiem tra MySQL, mat khau trong backend\cau_hinh.env, duong dan Moodle/PHP.
pause
exit /b 1
