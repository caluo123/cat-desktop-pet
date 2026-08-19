# -*- coding: utf-8 -*-
"""
桌面猫咪挂件（Desktop Cat Pet）
================================

一个用 Python + Tkinter 编写的可爱猫咪桌面挂件：
    - 无边框、置顶、透明背景窗口；
    - 鼠标左键按住可拖拽移动位置，单击触发"被撸"动画；
    - 猫咪会自己发呆、眨眼、在桌面自动游走、碰壁转向、累了会睡觉；
    - 鼠标右键弹出菜单：暂停/继续走动、睡觉/唤醒、退出。

运行方式：
    python main.py

依赖：
    pip install pillow

素材：
    所有图片放在 assets/cat/ 目录下，命名规范见 README.md。
    替换成你自己的猫咪素材后无需改动本文件。
"""

import os
import json
import math
import random
import sys
import time
import tkinter as tk
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageTk


# ===========================================================================
# 一、可配置区：素材路径、动画参数（替换素材时通常只改这里）
# ===========================================================================

# 猫咪素材目录：把素材 PNG 放这里
# 普通运行时相对本文件；用 PyInstaller 打包成 exe 后，素材被打包在
# _MEIPASS 临时目录里，这里两种路径都兼容。
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets", "cat")

# 猫咪显示尺寸（像素，正方形）：程序会把所有素材缩放到这个大小
# 也可运行时用命令行参数指定：python main.py --size 320
PET_SIZE = 256

# 猫头上方预留的气泡区高度（说话气泡显示在这里，不挡猫）
BUBBLE_ZONE = 96

# 消除"紫色描边"：
# Windows 透明色窗口会把品红(MAGENTA)变成透明，图片半透明边缘和品红混合后
# 会形成一圈紫色。开启后，加载时把半透明像素硬化为"完全透明/完全不透明"。
ALPHA_HARDEN = True
ALPHA_THRESHOLD = 180   # alpha 低于该值视为完全透明，否则完全不透明

# 右键菜单"大小"可选档位
SIZE_PRESETS = [("小 192", 192), ("中 256", 256), ("大 320", 320)]

# 动画状态配置：帧数必须和 assets/cat/ 下实际 PNG 数量一致
#   frames     : 该状态共几帧（代码会加载 state_1.png ~ state_N.png）
#   interval_ms: 每帧切换间隔（毫秒），越大动作越慢
#   loop       : True 循环播放；False 播放一遍后自动回到基础状态
ANIM_CONFIG = {
    "idle":   {"frames": 8, "interval_ms": 300, "loop": True},   # 发呆（放慢 50%）
    "blink":  {"frames": 4, "interval_ms": 240, "loop": False},  # 眨眼（放慢 50%）
    "walk":   {"frames": 8, "interval_ms": 480, "loop": True},   # 走路（放慢 50%）
    "pet":    {"frames": 8, "interval_ms": 200, "loop": False},  # 被抚摸（放慢 50%）
    "sleep":  {"frames": 10, "interval_ms": 440, "loop": True},  # 睡觉（放慢 50%）
}

# 行为参数（都可以按喜好调整）
WALK_SPEED = 2                # 走路速度：每次移动(50ms)前进的像素数（慢速踱步）
WALK_MIN_SECONDS = 6          # 一次自动游走的最短时间（秒）
WALK_MAX_SECONDS = 15         # 一次自动游走的最长时间（秒）
BLINK_CHANCE = 0.004          # 发呆时每 tick 触发眨眼的概率
WALK_CHANCE = 0.02            # 发呆时每 tick 触发走路的概率（约 1~5 秒内开始走）
SLEEP_AFTER_MIN = 45          # 连续发呆多久（秒）后开始考虑睡觉
SLEEP_AFTER_MAX = 70
SLEEP_DURATION_MIN = 15       # 睡多久后自己醒（秒）
SLEEP_DURATION_MAX = 40

# ===========================================================================
# 二、配置系统：右键菜单 / 动作 / 行为都可以用 config.json 配置，
#     并支持启动时从 GitHub(jsDelivr) 拉取最新配置与动画帧，
#     这样改仓库里的文件就能更新 exe 的动作，无需重新打包。
# ===========================================================================

# 本地配置文件（打包时随 exe 一起带上）
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# 远程素材缓存目录（下载过的帧缓存在用户目录，避免每次启动都下载）
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".catpet", "cache")
REMOTE_TIMEOUT = 8           # 远程拉取超时（秒）

# 默认菜单/行为（本地 config.json 缺失时的兜底）
DEFAULT_MENU = {
    "show_actions": True,
    "actions_submenu_label": "动作",
    "show_hearts": True,
    "hearts_label": "发射爱心彩蛋",
    "show_speech": True,
    "speech_label": "说句话",
    "show_pause": True,
    "show_size": True,
    "show_sleep": True,
    "show_exit": True,
}
DEFAULT_BEHAVIOR = {
    "walk_speed": 2,
    "walk_min_seconds": 6,
    "walk_max_seconds": 15,
    "blink_chance": 0.004,
    "walk_chance": 0.02,
    "sleep_after_min": 45,
    "sleep_after_max": 70,
    "sleep_duration_min": 15,
    "sleep_duration_max": 40,
}
DEFAULT_SPEECH = {
    "enabled": True,
    "random_interval_min": 25,
    "random_interval_max": 60,
    "duration_ms": 3500,
    "phrases": ["喵~", "摸摸我嘛~", "想吃小鱼干", "陪我玩一会儿"],
}
DEFAULT_REMOTE = {"enabled": False, "config_url": "", "assets_base": ""}

CFG = None  # 模块级配置（main() 启动时加载并应用）


def _merge(base, extra):
    """浅合并：extra 覆盖 base，字典按 key 递归合并。"""
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _merge(base[k], v)
        else:
            out[k] = v
    return out


def load_config():
    """加载配置：本地 config.json → 远程配置（若启用）→ 合并返回。"""
    cfg = {
        "version": 1,
        "states": dict(ANIM_CONFIG),
        "menu": dict(DEFAULT_MENU),
        "behavior": dict(DEFAULT_BEHAVIOR),
        "speech": dict(DEFAULT_SPEECH),
        "remote": dict(DEFAULT_REMOTE),
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fp:
                cfg = _merge(cfg, json.load(fp))
            print("[配置] 已加载本地 config.json")
        except Exception as exc:
            print("[配置] 本地 config.json 读取失败，使用内置默认值:", exc)

    remote = cfg.get("remote") or {}
    if remote.get("enabled") and remote.get("config_url"):
        url = f"{remote['config_url']}?v={cfg.get('version', 1)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CatPet"})
            with urllib.request.urlopen(req, timeout=REMOTE_TIMEOUT) as resp:
                remote_cfg = json.loads(resp.read().decode("utf-8"))
            cfg = _merge(cfg, remote_cfg)
            print("[配置] 已从远程加载最新配置")
        except Exception as exc:
            print("[配置] 远程配置拉取失败，使用本地配置:", exc)
    return cfg


def apply_config(cfg):
    """把配置应用到模块级变量（动画配置/行为参数/菜单）。"""
    global CFG, ANIM_CONFIG
    global WALK_SPEED, WALK_MIN_SECONDS, WALK_MAX_SECONDS
    global BLINK_CHANCE, WALK_CHANCE
    global SLEEP_AFTER_MIN, SLEEP_AFTER_MAX, SLEEP_DURATION_MIN, SLEEP_DURATION_MAX
    CFG = cfg
    ANIM_CONFIG = cfg["states"]
    b = cfg["behavior"]
    WALK_SPEED = int(b.get("walk_speed", WALK_SPEED))
    WALK_MIN_SECONDS = float(b.get("walk_min_seconds", WALK_MIN_SECONDS))
    WALK_MAX_SECONDS = float(b.get("walk_max_seconds", WALK_MAX_SECONDS))
    BLINK_CHANCE = float(b.get("blink_chance", BLINK_CHANCE))
    WALK_CHANCE = float(b.get("walk_chance", WALK_CHANCE))
    SLEEP_AFTER_MIN = float(b.get("sleep_after_min", SLEEP_AFTER_MIN))
    SLEEP_AFTER_MAX = float(b.get("sleep_after_max", SLEEP_AFTER_MAX))
    SLEEP_DURATION_MIN = float(b.get("sleep_duration_min", SLEEP_DURATION_MIN))
    SLEEP_DURATION_MAX = float(b.get("sleep_duration_max", SLEEP_DURATION_MAX))

# 透明色：窗口背景用这个颜色，Windows 下该颜色会变成完全透明
MAGENTA = "#ff00ff"

# 点击判定：位移小于 CLICK_MAX_MOVE 且持续时间小于 CLICK_MAX_MS 视为"点击"
CLICK_MAX_MOVE = 8
CLICK_MAX_MS = 350


# ===========================================================================
# 二、主程序类
# ===========================================================================
class CatPet:
    """猫咪挂件主控制类：负责窗口、动画、行为、交互。"""

    def __init__(self, root, borderless=True):
        self.root = root
        self.borderless = borderless  # False = 调试用普通窗口（带标题栏）
        self._setup_window()          # 无边框/置顶/透明
        self._load_frames()           # 加载全部动画帧
        self._setup_canvas()          # 画布 + 图片控件
        self._setup_menu()            # 右键菜单
        self._setup_bindings()        # 鼠标事件

        # ---- 状态变量 ----
        self.state = "idle"           # 当前动画状态（idle/blink/walk/pet/sleep）
        self.frame_idx = 0            # 当前播放到第几帧
        self.last_frame_time = 0.0    # 上一次切帧的时间戳
        self.last_move_time = 0.0     # 上一次移动的时间戳
        self.walking = False          # 是否正在自动游走
        self.paused = False           # 右键菜单"暂停走动"
        self.asleep = False           # 是否在睡觉
        self.was_walking = False      # 播放"被撸"前是否在走路（播完恢复）
        self.base_state = "idle"      # 一次性动画播完后的基础状态
        self.walk_until = 0.0         # 本次游走结束时间戳
        self.idle_since = time.monotonic()   # 开始发呆的时间戳
        self.sleep_until = 0.0        # 睡醒时间戳
        # 什么时候开始犯困（必须是"未来的时间戳"，否则一启动就睡着）
        self.sleep_after = time.monotonic() + random.uniform(
            SLEEP_AFTER_MIN, SLEEP_AFTER_MAX
        )
        self._photo_cache = {}        # PhotoImage 缓存，避免被回收
        self._heart_photos = {}       # 爱心彩蛋的图片缓存
        self._hearts = []             # 正在飘散的爱心列表
        self._heart_anim_running = False
        self._speech_items = []       # 说话气泡的画布元素
        self._next_speech_time = time.monotonic() + random.uniform(
            (CFG or {}).get("speech", DEFAULT_SPEECH).get("random_interval_min", 25),
            (CFG or {}).get("speech", DEFAULT_SPEECH).get("random_interval_max", 60),
        )
        self._walk_dir = 1            # 当前朝向：1 向右，-1 向左

        # ---- 拖拽/点击判定 ----
        self._press_x = 0             # 按下时鼠标全局 x
        self._press_y = 0
        self._press_time = 0.0
        self._win_x = 0               # 按下时窗口位置
        self._win_y = 0
        self._dragging = False

        # 初始化窗口位置：屏幕右下角
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.start_x = screen_w - self.window_w - 80
        self.start_y = screen_h - self.window_h - 120
        self.root.geometry(f"+{self.start_x}+{self.start_y}")
        print(f"[启动] 猫咪窗口 {self.window_w}x{self.window_h}"
              f"，位置 ({self.start_x}, {self.start_y})")
        print(f"[启动] 已加载动画帧: "
              + ", ".join(f"{k}={len(v)}" for k, v in self.pil_frames.items()))
        # 把窗口提到最前面，避免被其他窗口盖住（macOS 上尤其需要）
        self.root.lift()
        self.root.update_idletasks()

        # 启动主循环
        self.last_frame_time = time.monotonic()
        self.last_move_time = time.monotonic()
        self._show_frame()
        self._tick()

    # ------------------------------------------------------------------
    # 窗口初始化
    # ------------------------------------------------------------------
    def _setup_window(self):
        """设置无边框、置顶、透明窗口。"""
        if self.borderless:
            self.root.overrideredirect(True)   # 去掉系统标题栏/边框
        self.root.attributes("-topmost", True)  # 置顶显示

        # Windows 支持"透明色"：背景色为 MAGENTA 的像素完全透明
        # macOS 的 Tk 不支持该属性，会回退成普通窗口（本项目目标平台为 Windows）
        try:
            self.root.attributes("-transparentcolor", MAGENTA)
        except tk.TclError:
            print("[提示] 当前系统不支持透明色，将以普通窗口显示（Windows 下正常）。")

    def _load_frames(self):
        """
        按 ANIM_CONFIG 加载所有状态的动画帧。

        命名规范：assets/cat/{状态}_{序号}.png，例如 idle_1.png、walk_2.png。
        帧来源优先级：本地缓存 → 远程仓库（config 启用时）→ 打包内素材。
        某个状态的帧缺失时自动回退到 idle 帧并给出提示，程序不会崩溃。
        """
        self.pil_frames = {}   # state -> [PIL.Image, ...]
        for state, cfg in ANIM_CONFIG.items():
            frames = []
            for i in range(1, cfg["frames"] + 1):
                path = self._get_frame_path(state, i)
                if os.path.exists(path):
                    img = Image.open(path).convert("RGBA")
                    frames.append(self._prepare_frame(img, PET_SIZE))
            if not frames:
                print(f"[提示] 缺少 {state} 动画帧，将用 idle 帧代替。")
                frames = self.pil_frames.get("idle", [])
            self.pil_frames[state] = frames

        # 窗口/画布尺寸 = 猫咪尺寸 + 上方气泡区
        self.pet_size = PET_SIZE
        self.window_w = PET_SIZE
        self.window_h = PET_SIZE + BUBBLE_ZONE

    def _get_frame_path(self, state, idx):
        """
        找某一帧图片的路径：先看本地缓存，再尝试从远程下载，最后用打包内素材。
        远程地址来自 config.json 的 remote.assets_base（jsDelivr CDN）。
        """
        name = f"{state}_{idx}.png"
        cache = os.path.join(CACHE_DIR, name)
        if os.path.exists(cache):
            return cache

        remote = (CFG or {}).get("remote") or {}
        if remote.get("enabled") and remote.get("assets_base"):
            url = f"{remote['assets_base']}/{name}?v={(CFG or {}).get('version', 1)}"
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                req = urllib.request.Request(url, headers={"User-Agent": "CatPet"})
                with urllib.request.urlopen(req, timeout=REMOTE_TIMEOUT) as resp:
                    data = resp.read()
                with open(cache, "wb") as fp:
                    fp.write(data)
                print(f"[素材] 已从远程下载 {name}")
                return cache
            except Exception:
                pass  # 远程失败则用本地素材
        return os.path.join(ASSET_DIR, name)

    def _prepare_frame(self, img, size):
        """缩放 + 可选"硬化"半透明边缘（去掉紫色描边）。"""
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        if ALPHA_HARDEN:
            alpha = img.getchannel("A").point(
                lambda a: 255 if a >= ALPHA_THRESHOLD else 0
            )
            img.putalpha(alpha)
        return img

    def set_size(self, size):
        """运行时调整猫咪大小（保持窗口中心不动）。"""
        size = max(100, min(600, int(size)))
        if size == self.pet_size:
            return
        old_w, old_h = self.window_w, self.window_h
        cx = self.root.winfo_x() + old_w // 2
        cy = self.root.winfo_y() + old_h // 2

        self.pet_size = size
        self.window_w = size
        self.window_h = size + BUBBLE_ZONE
        self.pil_frames = {
            state: [self._prepare_frame(img, size) for img in imgs]
            for state, imgs in self.pil_frames.items()
        }
        self._photo_cache.clear()
        self.canvas.config(width=size, height=size + BUBBLE_ZONE)
        self.root.geometry(f"+{cx - size // 2}+{cy - size // 2}")
        self._show_frame()
        print(f"[大小] 猫咪调整为 {size}x{size}")

    def _setup_canvas(self):
        """创建画布并显示第一帧。"""
        self.canvas = tk.Canvas(
            self.root,
            width=self.window_w,
            height=self.window_h,
            bg=MAGENTA,             # 透明色背景
            highlightthickness=0,   # 去掉画布边框
            bd=0,
        )
        self.canvas.pack()
        # 猫图片放在下方，上方留出气泡区
        self.img_item = self.canvas.create_image(0, BUBBLE_ZONE, anchor="nw")

    def _setup_menu(self):
        """右键菜单。内容在弹出时动态生成，保证文案与状态一致。"""
        self.menu = tk.Menu(self.root, tearoff=0)

    def _setup_bindings(self):
        """绑定鼠标事件。"""
        # 左键：拖拽移动 / 单击交互
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # 右键菜单（macOS 上是 Button-2，顺手也绑上）
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_right_click)

    # ------------------------------------------------------------------
    # PhotoImage 缓存：正反两个朝向
    # ------------------------------------------------------------------
    def _get_photo(self, state, idx, facing):
        """
        获取某个状态某帧的 PhotoImage。

        facing = 1 表示朝右，facing = -1 表示朝左（水平翻转）。
        翻转结果会缓存，避免每帧重复翻转浪费性能。
        """
        key = (state, idx, facing)
        if key not in self._photo_cache:
            img = self.pil_frames[state][idx]
            if facing < 0:
                try:
                    flip = Image.Transpose.FLIP_LEFT_RIGHT
                except AttributeError:  # 兼容旧版 Pillow
                    flip = Image.FLIP_LEFT_RIGHT
                img = img.transpose(flip)
            self._photo_cache[key] = ImageTk.PhotoImage(img)
        return self._photo_cache[key]

    def _show_frame(self):
        """把当前状态/帧/朝向对应的图片显示到画布上。"""
        photo = self._get_photo(self.state, self.frame_idx, self._walk_dir)
        self.canvas.itemconfig(self.img_item, image=photo)

    # ------------------------------------------------------------------
    # 动画控制
    # ------------------------------------------------------------------
    def set_state(self, state):
        """切换到指定动画状态，并从第 0 帧开始播放。"""
        if state not in self.pil_frames or not self.pil_frames[state]:
            return
        self.state = state
        self.frame_idx = 0
        self.last_frame_time = time.monotonic()
        self._show_frame()

    def _finish_one_shot(self):
        """一次性动画（眨眼/被撸）播完后的收尾。"""
        if self.state == "blink":
            # 眨眼结束：回到发呆
            self.set_state("idle")
        elif self.state == "pet":
            # 被撸结束：如果撸之前在路上走，就继续走；否则发呆
            if self.was_walking and not self.paused and not self.asleep:
                self.walking = True
                self.set_state("walk")
            else:
                self.walking = False
                self.set_state("idle")
                self.idle_since = time.monotonic()

    def _tick_animation(self, now):
        """按 interval_ms 切换帧。"""
        cfg = ANIM_CONFIG[self.state]
        if now - self.last_frame_time >= cfg["interval_ms"] / 1000.0:
            self.last_frame_time = now
            self.frame_idx += 1
            if self.frame_idx >= cfg["frames"]:
                if cfg["loop"]:
                    self.frame_idx = 0
                else:
                    self._finish_one_shot()
                    return
            self._show_frame()

    # ------------------------------------------------------------------
    # 自动行为：发呆 -> 眨眼 / 走路 / 睡觉
    # ------------------------------------------------------------------
    def _tick_behavior(self, now):
        """控制猫咪的自主行为（只在非一次性动画期间生效）。"""
        if self.state in ("blink", "pet"):
            return  # 播放一次性动画时不叠加新行为

        # ---- 睡觉状态 ----
        if self.asleep:
            if now >= self.sleep_until:
                self._wake_up()          # 睡够了，自己醒
            return

        # ---- 走路状态 ----
        if self.walking:
            if self.paused:              # 被菜单暂停：原地待着
                self.walking = False
                self.set_state("idle")
            elif now >= self.walk_until:
                # 走够了，停下来发呆
                self.walking = False
                self.set_state("idle")
                self.idle_since = now
            return

        # ---- 发呆状态：随机触发眨眼 / 走路 / 睡觉 ----
        if self.state in ("idle",):
            r = random.random()
            if r < BLINK_CHANCE:
                self.set_state("blink")
                return
            if r < BLINK_CHANCE + WALK_CHANCE and not self.paused:
                self._start_walking()
                return

            # 随机卖萌说话
            speech = (CFG or {}).get("speech", DEFAULT_SPEECH)
            if speech.get("enabled", True) and now >= self._next_speech_time:
                phrases = speech.get("phrases") or ["喵~"]
                self.say(random.choice(phrases))
                self._next_speech_time = now + random.uniform(
                    speech.get("random_interval_min", 25),
                    speech.get("random_interval_max", 60),
                )

            # 发呆太久 -> 犯困睡觉
            if now - self.idle_since > self.sleep_after:
                self._go_sleep()

    def _start_walking(self):
        """开始一次自动游走：随机方向 + 随机时长。"""
        if self.asleep:
            self._wake_up()             # 睡着就先叫醒
        if self.paused:
            self.paused = False         # 暂停中就解除暂停
        self.walking = True
        self._walk_dir = random.choice((-1, 1))
        self.walk_until = time.monotonic() + random.uniform(
            WALK_MIN_SECONDS, WALK_MAX_SECONDS
        )
        self.set_state("walk")
        self.say("出去逛逛~")
        print(f"[行为] 开始走路（{self.walk_until - time.monotonic():.0f} 秒）")

    def _go_sleep(self):
        """进入睡觉状态。"""
        self.asleep = True
        self.walking = False
        self.sleep_until = time.monotonic() + random.uniform(
            SLEEP_DURATION_MIN, SLEEP_DURATION_MAX
        )
        self.set_state("sleep")
        self.say("晚安，喵~ zzz")

    def _wake_up(self):
        """睡醒：回到发呆状态，重新计时。"""
        self.asleep = False
        self.idle_since = time.monotonic()
        self.sleep_after = time.monotonic() + random.uniform(
            SLEEP_AFTER_MIN, SLEEP_AFTER_MAX
        )
        self.set_state("idle")

    # ------------------------------------------------------------------
    # 移动：自动游走 + 碰壁转向
    # ------------------------------------------------------------------
    def _tick_move(self, now):
        """每 50ms 移动一次窗口（如果正在走路且没被暂停）。"""
        if not self.walking or self.paused or self.asleep or self._dragging:
            return
        if now - self.last_move_time < 0.05:
            return
        self.last_move_time = now

        x = self.root.winfo_x() + WALK_SPEED * self._walk_dir
        y = self.root.winfo_y()

        # 屏幕边界（主屏逻辑尺寸）
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()

        # 碰壁转向
        if x <= 0:
            x = 0
            self._walk_dir = 1          # 撞到左墙 -> 向右走
        elif x + win_w >= screen_w:
            x = screen_w - win_w
            self._walk_dir = -1         # 撞到右墙 -> 向左走

        # 防止 y 超出屏幕（只在初始摆放时可能出现）
        if y < 0:
            y = 0
        elif y + win_h > screen_h:
            y = screen_h - win_h

        self.root.geometry(f"+{int(x)}+{int(y)}")
        self._show_frame()              # 换朝向时同步换图

    # ------------------------------------------------------------------
    # 鼠标交互：点击被撸 / 拖拽移动
    # ------------------------------------------------------------------
    def _on_press(self, event):
        """记录按下时的鼠标位置、窗口位置和时间，用于区分点击/拖拽。"""
        self._press_x = event.x_root
        self._press_y = event.y_root
        self._press_time = time.monotonic()
        self._win_x = self.root.winfo_x()
        self._win_y = self.root.winfo_y()
        self._dragging = False

    def _on_drag(self, event):
        """按住左键拖动窗口；移动超过阈值后判定为拖拽。"""
        dx = abs(event.x_root - self._press_x)
        dy = abs(event.y_root - self._press_y)
        if not self._dragging and (dx + dy) > CLICK_MAX_MOVE:
            self._dragging = True       # 正式进入拖拽模式

        if self._dragging:
            self.root.geometry(
                f"+{self._win_x + (event.x_root - self._press_x)}"
                f"+{self._win_y + (event.y_root - self._press_y)}"
            )

    def _on_release(self, event):
        """
        松开左键：如果基本没动且时间很短，判定为"点击"，触发被撸动画；
        如果是拖拽，则什么都不做（位置已经跟着鼠标走了）。
        """
        if self._dragging:
            self._dragging = False
            return

        moved = abs(event.x_root - self._press_x) + abs(event.y_root - self._press_y)
        duration_ms = (time.monotonic() - self._press_time) * 1000
        if moved <= CLICK_MAX_MOVE and duration_ms <= CLICK_MAX_MS:
            self._on_click()

    def _on_click(self):
        """单击猫咪：睡觉就唤醒，否则播放"被撸"动画。"""
        if self.asleep:
            self._wake_up()             # 先叫醒
        self._play_pet()

    def _play_pet(self):
        """播放被撸动画；记录撸之前是否在走路，播完后恢复。"""
        if self.state == "pet":
            return
        self.was_walking = self.walking
        self.walking = False
        self.set_state("pet")
        self.say("好舒服~ 再摸摸")

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------
    def _on_right_click(self, event):
        """弹出右键菜单：结构由 config.json 的 menu 段配置。"""
        self.menu.delete(0, "end")
        menu_cfg = (CFG or {}).get("menu", DEFAULT_MENU)
        state_cfg = (CFG or {}).get("states", ANIM_CONFIG)

        # 动作子菜单：菜单项来自 states 配置（label 可改、状态可增删）
        if menu_cfg.get("show_actions", True):
            anim_menu = tk.Menu(self.root, tearoff=0)
            for state in state_cfg:
                label = state_cfg[state].get("label", state)
                command = {
                    "idle": self._play_idle,
                    "blink": self._play_blink,
                    "walk": self._start_walking,
                    "pet": self._play_pet,
                    "sleep": self._go_sleep,
                }.get(state, self._play_idle)
                anim_menu.add_command(label=label, command=command)
            self.menu.add_cascade(
                label=menu_cfg.get("actions_submenu_label", "动作"),
                menu=anim_menu,
            )
            self.menu.add_separator()

        # 爱心彩蛋按钮
        if menu_cfg.get("show_hearts", True):
            self.menu.add_command(
                label=menu_cfg.get("hearts_label", "发射爱心彩蛋"),
                command=self.launch_hearts,
            )
            self.menu.add_separator()

        # 说话按钮
        if menu_cfg.get("show_speech", True):
            self.menu.add_command(
                label=menu_cfg.get("speech_label", "说句话"),
                command=self.say_random,
            )
            self.menu.add_separator()

        # 大小子菜单
        if menu_cfg.get("show_size", True):
            size_menu = tk.Menu(self.root, tearoff=0)
            for label, s in SIZE_PRESETS:
                size_menu.add_command(
                    label=label,
                    command=lambda s=s: self.set_size(s),
                )
            self.menu.add_cascade(label=f"大小 ({self.pet_size})", menu=size_menu)
            self.menu.add_separator()

        # 行为开关
        if menu_cfg.get("show_pause", True):
            self.menu.add_command(
                label="继续走动" if self.paused else "暂停走动",
                command=self._toggle_pause,
            )
        if menu_cfg.get("show_sleep", True):
            self.menu.add_command(
                label="唤醒猫咪" if self.asleep else "睡觉",
                command=self._toggle_sleep,
            )
        if menu_cfg.get("show_exit", True):
            self.menu.add_separator()
            self.menu.add_command(label="退出", command=self.root.destroy)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _play_idle(self):
        """手动切回发呆：唤醒 + 停止走路。"""
        self.asleep = False
        self.walking = False
        self.idle_since = time.monotonic()
        self.sleep_after = time.monotonic() + random.uniform(
            SLEEP_AFTER_MIN, SLEEP_AFTER_MAX
        )
        self.set_state("idle")

    def _play_blink(self):
        """手动播放一次眨眼：唤醒 + 停止走路后播放，播完自动回发呆。"""
        if self.asleep:
            self._wake_up()
        self.walking = False
        self.set_state("blink")

    # ------------------------------------------------------------------
    # 说话气泡：猫头上弹出文字，几秒后自动消失
    # ------------------------------------------------------------------
    def _clear_bubble(self):
        """清除当前说话气泡。"""
        for item in self._speech_items:
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._speech_items = []

    def say(self, text):
        """
        在猫头上方弹出"80% 透明白 + 毛玻璃感"气泡显示 text，自动消失。
        文字太长会自动换行（最多两行）。
        """
        speech = (CFG or {}).get("speech", DEFAULT_SPEECH)
        duration = int(speech.get("duration_ms", 3500))
        self._clear_bubble()

        w = self.window_w
        font = self._load_speech_font(20)
        char_w = 20                       # 近似中文字宽（用于折行估算）
        width_chars = sum(2 if ord(c) > 127 else 1 for c in text)
        max_chars = (w - 40) // char_w    # 单行最多容纳的"半角字符数"
        lines = [text]
        if width_chars > max_chars:
            # 按显示宽度折半成两行
            half = width_chars // 2
            cur = ""
            cur_w = 0
            lines = []
            for c in text:
                cw = 2 if ord(c) > 127 else 1
                if cur_w + cw > half and cur:
                    lines.append(cur)
                    cur, cur_w = c, cw
                else:
                    cur += c
                    cur_w += cw
            if cur:
                lines.append(cur)
            lines = lines[:2]

        # 用字体实际测量宽度，保证气泡大小贴合文字
        if font is not None:
            line_widths = [int(font.getlength(ln)) for ln in lines]
        else:
            line_widths = [sum(2 if ord(c) > 127 else 1 for c in ln) * 11 for ln in lines]
        bubble_w = min(max(max(line_widths) + 32, 92), w - 12)
        line_h = 26
        bubble_h = line_h * len(lines) + 16

        # ---- 用 PIL 画"半透明毛玻璃"气泡图片 ----
        tail_h = 12
        pad = 5                       # 阴影/模糊留白
        img_w = bubble_w + pad * 2
        img_h = bubble_h + pad * 2 + tail_h
        base = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        # 半透明白圆角矩形（80% 透明度）+ 柔和描边
        d.rounded_rectangle(
            [pad, pad, pad + bubble_w, pad + bubble_h],
            radius=14,
            fill=(255, 255, 255, 204),       # 80% 白
            outline=(120, 120, 130, 220),
            width=2,
        )
        # 指向猫的尾巴
        cx = img_w // 2
        d.polygon(
            [(cx - 10, pad + bubble_h), (cx + 10, pad + bubble_h), (cx, pad + bubble_h + tail_h)],
            fill=(255, 255, 255, 204),
        )
        # 高斯模糊 → 毛玻璃感（文字最后画，保持清晰）
        bubble_img = base.filter(ImageFilter.GaussianBlur(1.2))
        d2 = ImageDraw.Draw(bubble_img)
        text_y = pad + bubble_h // 2 - ((len(lines) - 1) * line_h) // 2
        for i, line in enumerate(lines):
            lw = line_widths[i]
            d2.text(
                (cx - lw // 2, text_y + i * line_h),
                line,
                font=font,
                fill=(60, 60, 70, 255),
            )

        self._bubble_photo = ImageTk.PhotoImage(bubble_img)
        bx = (w - img_w) // 2
        # 气泡贴近猫头顶（放在气泡区底部，间距 -25 更紧凑）
        by = max(2, BUBBLE_ZONE - img_h - 25)
        self._speech_items.append(
            self.canvas.create_image(bx, by, anchor="nw", image=self._bubble_photo)
        )
        self.root.after(duration, self._clear_bubble)
        print(f"[说话] {text}")

    def _load_speech_font(self, size):
        """加载支持中文的气泡字体（各平台找常见中文字体，找不到返回 None）。"""
        if hasattr(self, "_speech_font") and self._speech_font is not None:
            return self._speech_font
        import os as _os
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",          # macOS
            "/System/Library/Fonts/Hiragino Sans GB.ttc",  # macOS
            "C:/Windows/Fonts/msyh.ttc",                   # Windows 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",                 # Windows 黑体
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        ]
        try:
            from PIL import ImageFont
            for path in candidates:
                if _os.path.exists(path):
                    self._speech_font = ImageFont.truetype(path, size)
                    return self._speech_font
        except Exception:
            pass
        self._speech_font = None
        return None

    def say_random(self):
        """从配置的短语里随机说一句（右键菜单"说句话"）。"""
        speech = (CFG or {}).get("speech", DEFAULT_SPEECH)
        phrases = speech.get("phrases") or ["喵~"]
        self.say(random.choice(phrases))

    # ------------------------------------------------------------------
    # 爱心彩蛋：从猫咪身上喷出飘散的爱心
    # ------------------------------------------------------------------
    HEART_PATTERN = [
        ".XX.",
        "X.X.X",
        "X.X.X",
        ".XXX.",
    ]

    def _make_heart_photo(self, size, alpha):
        """生成一张粉色爱心图（按大小 + 透明度缓存）。"""
        key = (size, alpha)
        if key not in self._heart_photos:
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            s = size / 5.0
            for row, line in enumerate(self.HEART_PATTERN):
                for col, ch in enumerate(line):
                    if ch == "X":
                        x0, y0 = col * s, row * s
                        d.rectangle(
                            [x0, y0, x0 + s - 1, y0 + s - 1],
                            fill=(255, 105, 180, alpha),
                        )
            # 左上高光，更有立体感
            if size >= 20:
                d.rectangle([int(s * 1.2), int(s * 1.2),
                             int(s * 1.8), int(s * 1.8)],
                            fill=(255, 200, 220, alpha))
            self._heart_photos[key] = ImageTk.PhotoImage(img)
        return self._heart_photos[key]

    def launch_hearts(self):
        """爱心彩蛋：从猫胸口向四周喷出 12 颗爱心。"""
        cx = self.window_w // 2
        cy = int(self.window_h * 0.30)
        for _ in range(12):
            size = random.choice((16, 22, 30))
            angle = random.uniform(math.pi * 0.70, math.pi * 1.30)  # 向上扇形
            speed = random.uniform(2.0, 4.5)
            item = self.canvas.create_image(
                cx, cy, image=self._make_heart_photo(size, 255)
            )
            life = random.randint(35, 60)
            self._hearts.append({
                "item": item,
                "x": float(cx),
                "y": float(cy),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": life,
                "max_life": life,
                "size": size,
            })
        if not self._heart_anim_running:
            self._heart_anim_running = True
            self.root.after(30, self._animate_hearts)
        print("[彩蛋] 发射爱心！")

    def _animate_hearts(self):
        """爱心动画：飘散 + 重力 + 渐隐，播完自动清理。"""
        alive = []
        for h in self._hearts:
            h["life"] -= 1
            if h["life"] <= 0:
                self.canvas.delete(h["item"])
                continue
            h["vy"] += 0.12          # 重力
            h["vx"] *= 0.99          # 空气阻力
            h["x"] += h["vx"]
            h["y"] += h["vy"]
            self.canvas.coords(h["item"], h["x"], h["y"])

            # 按剩余生命渐隐
            frac = h["life"] / h["max_life"]
            alpha = 255
            if frac < 0.25:
                alpha = 20
            elif frac < 0.5:
                alpha = 70
            elif frac < 0.7:
                alpha = 130
            elif frac < 0.85:
                alpha = 190
            self.canvas.itemconfig(
                h["item"], image=self._make_heart_photo(h["size"], alpha)
            )
            alive.append(h)
        self._hearts = alive
        if self._hearts:
            self.root.after(30, self._animate_hearts)
        else:
            self._heart_anim_running = False

    def _toggle_pause(self):
        """切换"暂停走动"。"""
        self.paused = not self.paused
        if self.paused:
            self.walking = False
            if self.state == "walk":
                self.set_state("idle")
        else:
            # 恢复走动：直接重新开始一次游走，省得手动点
            if not self.asleep:
                self._start_walking()

    def _toggle_sleep(self):
        """菜单手动睡觉/唤醒。"""
        if self.asleep:
            self._wake_up()
        else:
            self._go_sleep()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------
    def _tick(self):
        """主循环：每 50ms 刷新一次（移动 + 行为 + 动画）。"""
        now = time.monotonic()
        self._tick_move(now)
        self._tick_behavior(now)
        self._tick_animation(now)
        self.root.after(50, self._tick)


# ===========================================================================
# 三、入口
# ===========================================================================
_SINGLE_LOCK = {}


def _ensure_single_instance():
    """
    防止同时运行两只猫咪。
    Windows：命名互斥锁；其他平台：占用本地端口当锁。
    返回 False 表示已经有一只猫在运行。
    """
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        _SINGLE_LOCK["mutex"] = kernel32.CreateMutexW(
            None, False, "CatPet_SingleInstance"
        )
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        return True

    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 48765))
        s.listen(1)
        _SINGLE_LOCK["socket"] = s  # 保持引用，防止被垃圾回收
        return True
    except OSError:
        return False


def _parse_size():
    """解析命令行 --size 参数，例如：python main.py --size 320"""
    if "--size" in sys.argv:
        try:
            idx = sys.argv.index("--size")
            return max(100, min(600, int(sys.argv[idx + 1])))
        except (ValueError, IndexError):
            print("[提示] --size 需要数字，例如 --size 320，使用默认值。")
    return PET_SIZE


def main():
    if not _ensure_single_instance():
        print("[提示] 已经有一只猫咪在运行了，本窗口直接退出。")
        return
    try:
        apply_config(load_config())
        root = tk.Tk()
        root.title("桌面猫咪")
        # 调试辅助：
        #   python main.py --center  让猫出现在屏幕正中央
        #   python main.py --normal  用带标题栏的普通窗口（macOS 排查用）
        borderless = "--normal" not in sys.argv
        pet = CatPet(root, borderless=borderless)
        if _parse_size() != PET_SIZE:
            pet.set_size(_parse_size())
        if "--center" in sys.argv:
            cx = (root.winfo_screenwidth() - pet.window_w) // 2
            cy = (root.winfo_screenheight() - pet.window_h) // 2
            root.geometry(f"+{cx}+{cy}")
            root.lift()
            print(f"[调试] 已把猫咪移到屏幕中央 ({cx}, {cy})")
        # 诊断模式：画一个红色椭圆 + 一个蓝色 PIL 图片方块，用来判断
        # "画布绘制"和"PIL 图片显示"哪个环节出了问题
        if "--diag" in sys.argv:
            pet.canvas.create_oval(20, 20, 120, 120, fill="red", outline="")
            blue = Image.new("RGBA", (80, 80), (0, 0, 255, 255))
            blue_photo = ImageTk.PhotoImage(blue)
            pet.canvas.create_image(180, 120, image=blue_photo)
            print("[诊断] 已在窗口里画红色椭圆 + 蓝色方块")
            print("[诊断] 若两个都看不到 = 画布/窗口问题；"
                  "若只有红色椭圆 = PIL 图片显示问题（Tk 版本太旧）")
        print("[启动] 一切正常，窗口应显示在屏幕右下角；按 Ctrl+C 可退出。")
        root.mainloop()
    except Exception as exc:
        print(f"[错误] 启动失败: {exc}")
        import traceback
        traceback.print_exc()
        input("按回车键关闭...")


if __name__ == "__main__":
    main()
