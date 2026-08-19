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
import random
import sys
import time
import tkinter as tk

from PIL import Image, ImageTk


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

# 素材放大倍数：照片素材已按 256x256 生成，无需放大；
# 若换成小尺寸素材（如 64x64 像素画），可调回 2 让它更清楚
FRAME_SCALE = 1

# 动画状态配置：帧数必须和 assets/cat/ 下实际 PNG 数量一致
#   frames     : 该状态共几帧（代码会加载 state_1.png ~ state_N.png）
#   interval_ms: 每帧切换间隔（毫秒），越大动作越慢
#   loop       : True 循环播放；False 播放一遍后自动回到基础状态
ANIM_CONFIG = {
    "idle":   {"frames": 8, "interval_ms": 150, "loop": True},   # 发呆（视频连续 8 帧）
    "blink":  {"frames": 4, "interval_ms": 120, "loop": False},  # 眨眼
    "walk":   {"frames": 8, "interval_ms": 100, "loop": True},  # 走路（一个猫步 8 帧，腿速稍放慢）
    "pet":    {"frames": 8, "interval_ms": 100, "loop": False},  # 被抚摸（视频连续 8 帧）
    "sleep":  {"frames": 10, "interval_ms": 220, "loop": True},  # 睡觉（视频连续 10 帧）
}

# 行为参数（都可以按喜好调整）
WALK_SPEED = 3                # 走路速度：每次移动(50ms)前进的像素数（4→3 变慢 25%）
WALK_MIN_SECONDS = 6          # 一次自动游走的最短时间（秒）
WALK_MAX_SECONDS = 15         # 一次自动游走的最长时间（秒）
BLINK_CHANCE = 0.004          # 发呆时每 tick 触发眨眼的概率
WALK_CHANCE = 0.02            # 发呆时每 tick 触发走路的概率（约 1~5 秒内开始走）
SLEEP_AFTER_MIN = 45          # 连续发呆多久（秒）后开始考虑睡觉
SLEEP_AFTER_MAX = 70
SLEEP_DURATION_MIN = 15       # 睡多久后自己醒（秒）
SLEEP_DURATION_MAX = 40

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
        某个状态的帧缺失时自动回退到 idle 帧并给出提示，程序不会崩溃。
        """
        self.pil_frames = {}   # state -> [PIL.Image, ...]
        for state, cfg in ANIM_CONFIG.items():
            frames = []
            for i in range(1, cfg["frames"] + 1):
                path = os.path.join(ASSET_DIR, f"{state}_{i}.png")
                if os.path.exists(path):
                    img = Image.open(path).convert("RGBA")
                    if FRAME_SCALE != 1:
                        # 像素画用 NEAREST 放大，保持清晰边缘
                        try:
                            resample = Image.Resampling.NEAREST
                        except AttributeError:  # 兼容旧版 Pillow
                            resample = Image.NEAREST
                        img = img.resize(
                            (img.width * FRAME_SCALE, img.height * FRAME_SCALE),
                            resample,
                        )
                    frames.append(img)
            if not frames:
                print(f"[提示] 缺少 {state} 动画帧，将用 idle 帧代替。")
                frames = self.pil_frames.get("idle", [])
            self.pil_frames[state] = frames

        # 以 idle 第一帧的尺寸作为窗口/画布尺寸
        first = self.pil_frames["idle"][0]
        self.window_w = first.width
        self.window_h = first.height

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
        self.img_item = self.canvas.create_image(0, 0, anchor="nw")

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
        print(f"[行为] 开始走路（{self.walk_until - time.monotonic():.0f} 秒）")

    def _go_sleep(self):
        """进入睡觉状态。"""
        self.asleep = True
        self.walking = False
        self.sleep_until = time.monotonic() + random.uniform(
            SLEEP_DURATION_MIN, SLEEP_DURATION_MAX
        )
        self.set_state("sleep")

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

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------
    def _on_right_click(self, event):
        """弹出右键菜单（文案随当前状态变化）。"""
        self.menu.delete(0, "end")
        # ---- 动作子菜单：手动触发任意一套动画 ----
        anim_menu = tk.Menu(self.root, tearoff=0)
        anim_menu.add_command(label="发呆", command=self._play_idle)
        anim_menu.add_command(label="眨眼", command=self._play_blink)
        anim_menu.add_command(label="被抚摸", command=self._play_pet)
        anim_menu.add_command(label="立即走动", command=self._start_walking)
        anim_menu.add_command(label="睡觉", command=self._go_sleep)
        self.menu.add_cascade(label="动作", menu=anim_menu)
        self.menu.add_separator()
        # ---- 行为开关 ----
        self.menu.add_command(
            label="继续走动" if self.paused else "暂停走动",
            command=self._toggle_pause,
        )
        self.menu.add_command(
            label="唤醒猫咪" if self.asleep else "睡觉",
            command=self._toggle_sleep,
        )
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
def main():
    try:
        root = tk.Tk()
        root.title("桌面猫咪")
        # 调试辅助：
        #   python main.py --center  让猫出现在屏幕正中央
        #   python main.py --normal  用带标题栏的普通窗口（macOS 排查用）
        borderless = "--normal" not in sys.argv
        pet = CatPet(root, borderless=borderless)
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
