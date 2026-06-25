@echo off
pip install -r requirements.txt pyinstaller
pyinstaller build.spec
echo.
echo Готово: dist\RentDays.exe
pause
