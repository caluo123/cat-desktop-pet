# AGENTS.md — 项目说明与用户偏好（长期记忆）

## 用户偏好（必须默认遵守）

- **所有涉及下载的操作，默认使用多线程/并行下载**：
  - 优先 `aria2c -x16 -s16` 下载单个大文件；
  - Python 依赖安装优先用 `uv pip install`（自带并行下载），不要用普通单线程 `pip install`；
  - 需要下载多个独立文件时，并行发起下载。
- **国内网络环境下默认使用加速源**（本机位于中国，直连国外源很慢）：
  - PyPI 用清华/阿里镜像：`https://pypi.tuna.tsinghua.edu.cn/simple` 或 `https://mirrors.aliyun.com/pypi/simple`；
  - GitHub Releases 用镜像代理（如 `https://mirror.ghproxy.com/` 前缀）加速；
  - HuggingFace 模型用 `https://hf-mirror.com` 加速。
- 除非用户明确要求，下载前不再询问"用哪种方式"，直接多线程执行。

## 项目：桌面猫咪挂件（Desktop Cat Pet）

- 主程序：`main.py`（Python + Tkinter + Pillow）。
- 素材目录：`assets/cat/`，命名规范 `状态_序号.png`：
  - `idle_*.png` 发呆 / `blink_*.png` 眨眼 / `walk_*.png` 走路（朝右）/ `pet_*.png` 被撸 / `sleep_*.png` 睡觉；
  - 帧数与 `main.py` 顶部 `ANIM_CONFIG` 一致；透明底、同状态同尺寸。
- 用户猫咪照片：`input_photos/`（iPhone 12 拍摄的 HEIC 原片）。
- 照片处理管线：HEIC 用 ffmpeg 转 PNG → rembg AI 抠图 → 生成五态规范帧 → 替换 `assets/cat/`。
- 用户目标：最终打包成 Windows 可运行 exe（`build.bat` / PyInstaller）。

## 本机运行环境（macOS）

- 运行桌宠必须用 `.venv314/bin/python main.py`（Python 3.14 + Tk 9.0 + Pillow 12）。
  系统自带 `/usr/bin/python3` 的 Tk 8.5 已废弃，PIL 图片显示不出来，不要用它跑主程序。
- 图像处理（抠图/生成帧）用 `.venv/bin/python`（Python 3.9 + rembg + onnxruntime）。
- 下载一律走国内镜像 + aria2c/uv 多线程（见上方用户偏好）。
- 视频类素材处理：一律按原始帧率**全帧处理**（24fps 全抽，不抽稀），
  全部帧交给 AI 模型逐帧验收后，再对最终动画组合做二次确认。
