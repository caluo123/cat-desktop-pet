# -*- coding: utf-8 -*-
"""
照片 → 五态动画帧生成器（真实猫咪贴纸风）
============================================

把你家猫的"透明底照片"自动变成桌面挂件需要的五套动画帧：
    - idle_1..4.png   发呆：身体轻微呼吸起伏
    - blink_1..4.png  眨眼：第 2、4 帧闭眼（自动识别眼睛，识别不到则用"低头"代替）
    - walk_1..4.png   走路：上下颠簸 + 轻微前倾（贴纸式走动）
    - pet_1..4.png    被撸：头顶粉色小心心上升
    - sleep_1..6.png  睡觉：闭眼 + 头顶 Zzz + 呼吸起伏

用法：
    python scripts/generate_frames.py \
        --front 正面猫透明图.png \
        --side  侧面/站立猫透明图.png \
        [--size 256] \
        [--out assets/cat]

前置要求：
    - 两张输入都是透明背景 PNG（可以用 rembg 抠图得到）；
    - --front 用于发呆/眨眼/被撸/睡觉，--side 用于走路。

说明：
    - 输出统一为 --size 指定的正方形画布（默认 256x256），内容居中、贴底；
    - 会直接覆盖 assets/cat/ 下 idle/blink/walk/pet/sleep 帧，帧数与
      main.py 顶部的 ANIM_CONFIG 保持一致；
    - 眼睛识别是"尽力而为"：照片上如果识别不到眼睛，眨眼/睡觉会退化为
      低头/呼吸动作并打印提示，不影响运行。
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageOps

# ---------------------------------------------------------------------------
# 可配置参数
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "assets", "cat")

FRAME_COUNTS = {"idle": 8, "blink": 4, "walk": 8, "pet": 8, "sleep": 10}

# 画布留白比例（上下左右各留 6%，防止贴底后猫被裁）
PADDING = 0.06

# 心跳/呼吸缩放序列（围绕底部中心缩放）
BREATH_SCALE = [1.000, 1.010, 1.000, 1.010, 1.000, 1.010]
# 走路颠簸：dy 为相对底部的纵向偏移（正数表示抬高）
WALK_BOUNCE = [0, 6, 12, 6]
# 走路倾斜角度（度，围绕底部中心旋转）
WALK_TILT = [-2, 0, 2, 0]

# 被撸时小心心的左上角坐标（相对画布，从右上方向上升）
HEART_POSITIONS = [
    [(52, 24)],
    [(56, 16), (40, 20)],
    [(52, 8), (36, 12), (60, 12)],
    [(44, 2), (56, 4)],
]

# 睡觉时 Zzz 的左上角坐标（逐帧上浮，循环）
ZZZ_POSITIONS = [
    [(56, 60)],
    [(52, 48), (64, 56)],
    [(48, 36), (60, 44)],
    [(44, 24), (56, 32), (68, 40)],
    [(40, 12), (52, 20)],
    [(36, 0), (48, 8)],
]

HEART_COLOR = (255, 105, 180, 255)
HEART_LIGHT = (255, 180, 215, 255)
HEART_PATTERN = [
    ".XX.",
    "X.X.X",
    "X.X.X",
    ".XXX.",
]

# Z 字像素图案（5x5）
Z_PATTERN = [
    "#####",
    "...#.",
    "..#..",
    ".#...",
    "#####",
]


# ---------------------------------------------------------------------------
# 基础图像工具
# ---------------------------------------------------------------------------
def load_cutout(path):
    """加载透明底照片，返回 RGBA 图像。"""
    if not os.path.exists(path):
        print(f"[错误] 找不到输入图片: {path}")
        sys.exit(1)
    return Image.open(path).convert("RGBA")


def content_box(img):
    """返回非透明内容的外接矩形 (left, top, right, bottom)。"""
    bbox = img.getbbox()
    return bbox or (0, 0, img.width, img.height)


def paste_centered_bottom(img, canvas, content=None, dy=0):
    """
    把 img 的透明内容缩放到画布中：水平居中、底部对齐（可加 dy 纵向偏移）。
    content 用于指定源内容区域（默认自动取非透明包围盒）。
    """
    canvas = canvas.copy()
    if content is None:
        content = content_box(img)
    l, t, r, b = content
    piece = img.crop(content)
    cw, ch = canvas.width, canvas.height
    max_w = int(cw * (1 - 2 * PADDING))
    max_h = int(ch * (1 - 2 * PADDING))
    scale = min(max_w / piece.width, max_h / piece.height, 1.0)
    piece = piece.resize(
        (max(1, int(piece.width * scale)), max(1, int(piece.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = (cw - piece.width) // 2
    y = ch - dy - piece.height
    canvas.paste(piece, (x, y), piece)
    return canvas


def breath_frame(base, canvas, scale, dy=0):
    """呼吸帧：以底部中心为原点整体缩放 scale，再上移 dy 像素。"""
    content = content_box(base)
    piece = base.crop(content)
    w, h = piece.size
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    piece = piece.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    x = (canvas.width - nw) // 2
    y = canvas.height - dy - nh
    out.paste(piece, (x, y), piece)
    return out


def tilt_frame(base, canvas, angle, dy=0):
    """倾斜帧：内容绕底部中心旋转 angle 度，再上移 dy。"""
    content = content_box(base)
    piece = base.crop(content)
    piece = piece.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    x = (canvas.width - piece.width) // 2
    y = canvas.height - dy - piece.height
    out.paste(piece, (x, y), piece)
    return out


# ---------------------------------------------------------------------------
# 眼睛识别与闭眼
# ---------------------------------------------------------------------------
def find_eye_blobs(img):
    """
    在画面上半部分找"眼睛"暗色小块，返回 [({(x,y),...}), ...]。
    照片里瞳孔通常比周围深；找暗色聚类，过滤掉轮廓/噪点后返回。
    """
    width, height = img.size
    l, t, r, b = content_box(img)
    px = img.load()
    candidates = set()
    y0, y1 = int(t + (b - t) * 0.15), int(t + (b - t) * 0.55)
    for y in range(y0, y1):
        for x in range(l, r):
            rr, gg, bb, aa = px[x, y]
            if aa >= 128 and max(rr, gg, bb) < 90:
                candidates.add((x, y))

    blobs = []
    while candidates:
        seed = candidates.pop()
        blob = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (x + dx, y + dy)
                if nb in candidates:
                    candidates.remove(nb)
                    blob.add(nb)
                    stack.append(nb)
        # 只保留 2~40 像素、宽高 1~10 的小块（眼睛尺度）
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        if 2 <= len(blob) <= 40 and 1 <= max(xs) - min(xs) <= 10 and 1 <= max(ys) - min(ys) <= 10:
            blobs.append(blob)

    # 按中心 x 排序
    blobs.sort(key=lambda bl: sum(p[0] for p in bl) / len(bl))
    return blobs


def pair_eyes(blobs, width):
    """尽量配成左右两只眼；配对失败就全当眼睛处理。"""
    if len(blobs) < 2:
        return blobs
    centers = [
        (sum(p[0] for p in bl) / len(bl), sum(p[1] for p in bl) / len(bl), bl)
        for bl in blobs
    ]
    mid = width / 2
    left = [c for c in centers if c[0] < mid]
    right = [c for c in centers if c[0] >= mid]
    best = None
    for a in left:
        for c in right:
            if abs(a[1] - c[1]) > 8:
                continue
            if best is None or abs(a[1] - c[1]) < best[0]:
                best = (abs(a[1] - c[1]), a[2], c[2])
    return [best[1], best[2]] if best else blobs


def close_eyes(img):
    """
    返回闭眼副本：把眼睛暗块涂成周围平均色，再画一条横向闭眼线。
    识别不到眼睛时返回 (原图副本, False)。
    """
    img = img.copy()
    px = img.load()
    blobs = pair_eyes(find_eye_blobs(img), img.width)
    if not blobs:
        return img, False
    for blob in blobs:
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cy = round(sum(ys) / len(ys))
        # 眼睛块外围一圈的平均颜色当作"眼皮颜色"
        ring = []
        for x in range(min_x - 2, max_x + 3):
            for y in range(min_y - 2, max_y + 3):
                if (x, y) in blob or not (0 <= x < img.width and 0 <= y < img.height):
                    continue
                rr, gg, bb, aa = px[x, y]
                if aa >= 128:
                    ring.append((rr, gg, bb))
        if ring:
            skin = tuple(round(sum(c[i] for c in ring) / len(ring)) for i in range(3))
        else:
            skin = (200, 200, 200)
        for x, y in blob:
            px[x, y] = (*skin, 255)
        for x in range(min_x, max_x + 1):
            px[x, cy] = (35, 35, 35, 255)
    return img, True


# ---------------------------------------------------------------------------
# 装饰绘制：小心心 / Zzz
# ---------------------------------------------------------------------------
def draw_hearts(img, positions):
    """在画布指定位置画粉色小心心。"""
    img = img.copy()
    px = img.load()
    for sx, sy in positions:
        for row, line in enumerate(HEART_PATTERN):
            for col, ch in enumerate(line):
                if ch != "X":
                    continue
                x, y = sx + col, sy + row
                if 0 <= x < img.width and 0 <= y < img.height:
                    px[x, y] = HEART_LIGHT if (row == 0 and col in (1, 2)) else HEART_COLOR
    return img


def draw_zzz(img, positions):
    """在画布指定位置画白色 Z（带深色描边，保证在浅色背景上可见）。"""
    img = img.copy()
    px = img.load()
    for sx, sy in positions:
        for row, line in enumerate(Z_PATTERN):
            for col, ch in enumerate(line):
                if ch != "#":
                    continue
                for dx, dy in ((1, 0), (0, 1)):
                    x, y = sx + col + dx, sy + row + dy
                    if 0 <= x < img.width and 0 <= y < img.height:
                        px[x, y] = (60, 60, 70, 255)
                x, y = sx + col, sy + row
                if 0 <= x < img.width and 0 <= y < img.height:
                    px[x, y] = (255, 255, 255, 255)
    return img


# ---------------------------------------------------------------------------
# 五态生成
# ---------------------------------------------------------------------------
def build_frames(front, side, size):
    """根据正面/侧面透明照片生成五态帧，返回 {state: [PIL.Image, ...]}。"""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    front_base = paste_centered_bottom(front, canvas)
    side_base = paste_centered_bottom(side, canvas)

    frames = {}

    # 1) 发呆：呼吸起伏
    idle = []
    for i in range(FRAME_COUNTS["idle"]):
        idle.append(breath_frame(front_base, canvas, BREATH_SCALE[i], dy=2 if i % 2 else 0))
    frames["idle"] = idle

    # 2) 眨眼：睁-闭-睁-闭；闭眼失败则用"低头"代替
    blink = []
    eye_ok = True
    for i in range(FRAME_COUNTS["blink"]):
        base = idle[i % len(idle)]
        if i % 2 == 1:
            closed, ok = close_eyes(base)
            if ok:
                blink.append(closed)
            else:
                eye_ok = False
                blink.append(breath_frame(front_base, canvas, 1.0, dy=4))  # 低头代替
        else:
            blink.append(base)
    frames["blink"] = blink
    if not eye_ok:
        print("[提示] 未能识别到眼睛，眨眼用'低头'代替。")

    # 3) 走路：颠簸 + 倾斜
    walk = []
    for i in range(FRAME_COUNTS["walk"]):
        walk.append(tilt_frame(side_base, canvas, WALK_TILT[i], dy=WALK_BOUNCE[i]))
    frames["walk"] = walk

    # 4) 被撸：小心心上升
    pet = []
    for i in range(FRAME_COUNTS["pet"]):
        pet.append(draw_hearts(idle[i % len(idle)], HEART_POSITIONS[i]))
    frames["pet"] = pet

    # 5) 睡觉：闭眼 + 呼吸 + Zzz
    sleep = []
    sleep_eye_ok = True
    for i in range(FRAME_COUNTS["sleep"]):
        base = breath_frame(front_base, canvas, BREATH_SCALE[i], dy=1 if i % 2 else 0)
        closed, ok = close_eyes(base)
        if not ok:
            sleep_eye_ok = False
            closed = base
        sleep.append(draw_zzz(closed, ZZZ_POSITIONS[i]))
    frames["sleep"] = sleep
    if not sleep_eye_ok:
        print("[提示] 未能识别到眼睛，睡觉用'呼吸 + Zzz'代替。")

    return frames


def save_frames(frames, out_dir):
    """按命名规范保存：{state}_{序号}.png。"""
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for state, images in frames.items():
        for i, img in enumerate(images, start=1):
            path = os.path.join(out_dir, f"{state}_{i}.png")
            img.save(path)
            saved.append(path)
    return saved


# ---------------------------------------------------------------------------
# 自测：用合成图跑一遍完整流程
# ---------------------------------------------------------------------------
def make_synthetic_front():
    """合成一张"正面猫"测试图：圆头 + 耳朵 + 眼睛 + 身体。"""
    img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(120, 120), (160, 60), (200, 110)], fill=(120, 120, 130, 255))
    d.polygon([(280, 120), (240, 60), (200, 110)], fill=(120, 120, 130, 255))
    d.ellipse((100, 100, 300, 300), fill=(160, 160, 170, 255))
    d.ellipse((150, 180, 170, 200), fill=(30, 30, 30, 255))
    d.ellipse((230, 180, 250, 200), fill=(30, 30, 30, 255))
    d.ellipse((130, 280, 270, 480), fill=(150, 150, 160, 255))
    return img


def make_synthetic_side():
    """合成一张"侧面猫"测试图：椭圆身体 + 圆头 + 尾巴。"""
    img = Image.new("RGBA", (500, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((60, 120, 260, 320), fill=(150, 150, 160, 255))
    d.ellipse((240, 80, 360, 220), fill=(160, 160, 170, 255))
    d.polygon([(330, 80), (350, 30), (365, 90)], fill=(120, 120, 130, 255))
    d.arc((20, 200, 120, 320), 90, 270, fill=(130, 130, 140, 255), width=18)
    d.ellipse((300, 140, 320, 160), fill=(30, 30, 30, 255))
    return img


def self_test(size):
    """自测：合成正面/侧面图 → 生成五态 → 校验文件与尺寸。"""
    out_dir = "/private/tmp/frame_test/out"
    report_path = "/private/tmp/frame_test/report.txt"
    os.makedirs(out_dir, exist_ok=True)
    front = make_synthetic_front()
    side = make_synthetic_side()
    frames = build_frames(front, side, size)
    saved = save_frames(frames, out_dir)

    errors = []
    for state, n in FRAME_COUNTS.items():
        if len(frames[state]) != n:
            errors.append(f"{state} 帧数 {len(frames[state])} != {n}")
    for path in saved:
        im = Image.open(path)
        if im.size != (size, size) or im.mode != "RGBA":
            errors.append(f"{path} 尺寸/模式异常: {im.size} {im.mode}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"self-test size={size}\n")
        f.write(f"saved {len(saved)} files\n")
        for p in sorted(saved):
            f.write(f"  {os.path.basename(p)}\n")
        f.write("errors: " + ("; ".join(errors) if errors else "none") + "\n")
    print("self-test report ->", report_path)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("SELF-TEST PASSED")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="照片 → 五态动画帧生成器")
    parser.add_argument("--front", help="正面透明 PNG（发呆/眨眼/被撸/睡觉）")
    parser.add_argument("--side", help="侧面/站立透明 PNG（走路）")
    parser.add_argument("--size", type=int, default=256, help="画布边长（默认 256）")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出目录（默认 assets/cat）")
    parser.add_argument("--self-test", action="store_true", help="用合成图自测")
    args = parser.parse_args()

    if args.self_test:
        self_test(args.size)
        return

    if not args.front or not args.side:
        parser.error("请提供 --front 和 --side 两张透明 PNG（或用 --self-test）")

    front = load_cutout(args.front)
    side = load_cutout(args.side)
    print(f"正面图: {args.front} {front.size}")
    print(f"侧面图: {args.side} {side.size}")

    frames = build_frames(front, side, args.size)
    saved = save_frames(frames, args.out)
    print(f"已生成 {len(saved)} 帧 -> {args.out}")
    for p in sorted(saved):
        print("  ", os.path.basename(p))
    print("完成！运行 python main.py 查看效果。")


if __name__ == "__main__":
    main()
