@echo off
echo ============================================
echo   StockMaster - Windows EXE Build
echo ============================================
echo.

REM Install dependencies
pip install -r requirements.txt

REM Build EXE
pyinstaller stock_master.spec --noconfirm

echo.
echo Build complete! Output: dist\StockMaster\
echo Run: dist\StockMaster\StockMaster.exe
pause
