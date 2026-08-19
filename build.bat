@echo off
chcp 65001 >nul
REM ============================================================
REM  桌面猫咪挂件 - Windows 打包脚本
REM  在 Windows 上双击本文件即可生成 dist\CatPet.exe
REM ============================================================

echo [1/3] 检查/安装依赖...
python -m pip install --upgrade pip
python -m pip install pillow pyinstaller
if errorlevel 1 goto :fail

echo [2/3] 开始打包...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name CatPet ^
  --add-data "assets;assets" ^
  --add-data "config.json;." ^
  main.py
if errorlevel 1 goto :fail

echo [3/3] 完成！
echo.
echo 打包产物：dist\CatPet.exe
echo 使用方法：双击 CatPet.exe 即可（无需安装 Python）。
pause
exit /b 0

:fail
echo.
echo 打包失败，请检查上面的报错信息。
pause
exit /b 1
