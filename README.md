# 桌面猫咪挂件（Desktop Cat Pet）

一个用 Python + Tkinter 编写的可爱猫咪桌面挂件：

- 无边框、置顶、透明背景窗口；
- 鼠标左键按住拖拽移动，单击触发"被撸"动画；
- 猫咪自己发呆、眨眼、在桌面自动游走、碰壁转向、累了会睡觉；
- 鼠标右键菜单：暂停/继续走动、睡觉/唤醒、退出。

## 一、运行

```bash
cd 项目目录
python -m pip install -r requirements.txt
python main.py
```

依赖只有一个：`Pillow`（Tkinter 是 Python 自带）。

## 二、素材命名规范（重要）

所有素材放在 `assets/cat/` 目录，文件名必须按下面的规则：

| 动画状态 | 文件名 | 默认帧数 | 说明 |
| --- | --- | --- | --- |
| 发呆 | `idle_1.png` ~ `idle_8.png` | 8 | 基础待机动画（视频连续帧） |
| 眨眼 | `blink_1.png` ~ `blink_4.png` | 4 | 睁-闭-睁-闭 |
| 走路 | `walk_1.png` ~ `walk_8.png` | 8 | 视频真实走路帧（一个猫步），统一朝右，程序自动水平翻转成朝左 |
| 被撸 | `pet_1.png` ~ `pet_8.png` | 8 | 点击时播放（视频连续帧） |
| 睡觉 | `sleep_1.png` ~ `sleep_10.png` | 10 | 睡觉动画（视频连续帧） |

硬性要求：

1. PNG 格式，建议带透明通道（RGBA），背景透明；
2. 同一状态的所有帧尺寸必须一致（不同状态之间可以不同，但建议统一，如 128x128）；
3. 序号从 1 开始连续编号，中间不能跳号；
4. 帧数要和 `main.py` 顶部 `ANIM_CONFIG` 里写的数字一致（想加帧改那里即可）；
5. `walk_*.png` 请制作"脸朝右"的走路动作，朝左时程序自动镜像。

> 小技巧：某状态帧缺失也不会崩溃，程序会回退到 `idle` 帧并打印提示，
> 所以可以先只做发呆/走路/睡觉，再慢慢补眨眼/被撸。

## 三、替换成你自己的猫咪

### 方式 A：直接用照片自动生成（推荐，已完成一次）

项目已经内置了"照片 → 五态帧"管线，你家猫的素材已经用它生成好了：

1. 把猫的照片（正脸 + 侧面/站立各一张最好）放进 `input_photos/`；
2. 用 rembg 抠图成透明底 PNG（项目虚拟环境 `.venv` 已装好工具）；
3. 运行：

```bash
python scripts/generate_frames.py \
    --front 正面猫.png \
    --side 侧面猫.png \
    --size 256
```

   脚本会直接刷新 `assets/cat/` 下的 22 帧。

### 方式 B：手工准备帧

按第二节的命名规范，把做好的透明 PNG 直接放进 `assets/cat/` 即可。

4. 想调动画快慢/走路速度，改 `main.py` 顶部的 `ANIM_CONFIG` 和 `WALK_SPEED`。

## 四、打包成 Windows exe

PyInstaller 不支持跨平台打包，**在 Mac 上无法直接生成 Windows exe**。
以下是三种可行方案，按推荐顺序：

### 方案 A：GitHub Actions 云端打包（推荐，Mac 上零安装）

项目已内置工作流 `.github/workflows/build-windows.yml`：

1. 在 GitHub 新建仓库，把项目推送上去；
2. 打开仓库 **Actions** 页面 → 手动运行 "构建 Windows exe"；
3. 跑完在 **Artifacts** 里下载 `CatPet-windows.zip`，解压即得 `CatPet.exe`。

### 方案 B：本机 Wine（在 Mac 上模拟 Windows）

```bash
brew install --cask wine-stable
bash scripts/build_windows_wine.sh   # 自动下载 Windows Python 并打包
```

产物在 `dist/CatPet.exe`，建议拿到真实 Windows 上双击验证。

### 方案 C：Windows 电脑 / 虚拟机（最稳妥）

把项目拷到 Windows（或 Mac 上的 Parallels/UTM 虚拟机），双击 `build.bat`：

```bash
python -m pip install pyinstaller pillow
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name CatPet ^
  --add-data "assets;assets" ^
  main.py
```

## 五、常见问题

- **窗口是个粉色方块？** 透明色只在 Windows 上生效（macOS/Linux 的 Tk 不支持）。
  最终目标平台是 Windows，正常打包后不会有这个问题。
- **猫不在桌面边缘转向？** 用的是主屏逻辑分辨率，多显示器下行为以主屏为准。
- **图片模糊？** `FRAME_SCALE` 改大一点；像素画用最近邻缩放，不会糊。

## 六、素材来源与许可

- 占位素材来自 [1ilit/Desktop-Cat](https://github.com/1ilit/Desktop-Cat)（MIT License，作者 day），
  `blink` / `pet` 占位帧由 `scripts/make_placeholder_frames.py` 基于其 idle 帧生成。
- 详见 `ASSET-NOTICE.md`。替换成你自己的猫后，这些占位素材就不需要了。
