@echo off
echo Membuka Edge secara manual untuk Login ke akun Google Anda...
echo Silakan login seperti biasa. Setelah selesai, TUTUP jendela Edge ini.
echo.
start msedge.exe --user-data-dir="%~dp0edge_profile" "https://accounts.google.com/"
pause
