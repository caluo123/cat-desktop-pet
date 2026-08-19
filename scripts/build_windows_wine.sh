#!/bin/bash
#
# 在 macOS 上用 Wine 打包 Windows exe（本地方案，不依赖 GitHub/VM）
#
# 前提：
#   1. 已安装 wine-stable：brew install --cask wine-stable
#   2. 本脚本会自动下载 Windows 版 Python 到 /private/tmp/wine_python/
#   3. 首次运行会下载 PyInstaller 依赖，请耐心等待
#
# 用法：bash scripts/build_windows_wine.sh
#
# 产物：dist/CatPet.exe
set -e

PY_VER="3.11.9"
PY_URL="https://www.python.org/ftp/python/${PY_VER}/python-${PY_VER}-amd64.exe"
WORK="/private/tmp/wine_python"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/4] 下载 Windows 版 Python ${PY_VER}（约 25MB）..."
mkdir -p "$WORK"
if [ ! -f "$WORK/python-setup.exe" ]; then
  aria2c -x16 -s16 -d "$WORK" -o python-setup.exe "$PY_URL"
fi

echo "[2/4] 在 Wine 里静默安装 Python..."
wine "$WORK/python-setup.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_tcltk=1 \
  >/dev/null 2>&1 || true
# 等安装进程结束
while pgrep -f "python-setup.exe" >/dev/null 2>&1; do sleep 2; done

echo "[3/4] 安装 Pillow + PyInstaller（走清华镜像加速）..."
wine python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  pillow pyinstaller

echo "[4/4] 打包..."
cd "$ROOT"
wine python -m PyInstaller --noconfirm --onefile --windowed \
  --name CatPet \
  --add-data "assets;assets" \
  main.py

echo "完成！产物：dist/CatPet.exe"
echo "建议在真实 Windows 上双击验证（Wine 打包的 exe 以真机测试为准）"
