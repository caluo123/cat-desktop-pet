# -*- coding: utf-8 -*-
"""
占位帧生成脚本：根据 assets/cat/idle_*.png 自动生成：
    - blink_*.png  眨眼动画（自动识别眼睛位置，画出"闭眼"帧）
    - pet_*.png    被撸动画（发呆帧 + 漂浮的粉色小心心）

用途：
    1. 首次使用：生成随项目一起发布的占位眨眼/被撸帧。
    2. 替换成你自己的猫咪素材后（只替换了 idle_*.png 的情况下），
       重新运行本脚本即可为新猫生成配套的眨眼/被撸占位帧：
           python3 scripts/make_placeholder_frames.py

注意：
    - 本脚本只是"占位兜底"方案。想让效果最好，建议后续给自家猫单独制作
      blink_*.png 和 pet_*.png（命名规范见 README.md）。
    - 如果眼睛识别不理想（例如猫脸朝向侧面、眼睛被刘海挡住），可以手动
      调整下方 BLINK_EYE_ROW 等参数，或直接删掉生成的 blink/pet 帧，
      主程序会自动回退到 idle 帧，不影响运行。
"""

import os
import sys

from PIL import Image

# ---------------------------------------------------------------------------
# 可配置参数
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(PROJECT_ROOT, "assets", "cat")

# 眨眼动画按"睁-闭-睁-闭"循环，共 4 帧（1=睁眼, 2=闭眼）
BLINK_SOURCE_IDS = [1, 2, 1, 2]
# 被撸动画使用发呆帧 1、2 交替 + 不同位置的小心心生成 4 帧
PET_SOURCE_IDS = [1, 2, 1, 2]

# 小心心颜色（粉色）与 5x4 像素图案（. 表示透明，X 表示粉色像素）
HEART_COLOR = (255, 105, 180, 255)
HEART_PATTERN = [
    ".XX.",
    "X.X.X",
    "X.X.X",
    ".XXX.",
]

# 小心心在每个被撸帧中的左上角位置（相对画布，从右上角向上升）
HEART_POSITIONS = [
    [(46, 8)],
    [(46, 5), (38, 3)],
    [(46, 2), (38, 1)],
    [(46, 1)],
]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def load_idle_frame(idx):
    """按序号加载 idle 帧，返回 RGBA 模式的 PIL Image。"""
    path = os.path.join(ASSET_DIR, f"idle_{idx}.png")
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到发呆帧: {path}，请先准备 idle_*.png 素材")
    return Image.open(path).convert("RGBA")


def find_eye_blobs(img):
    """
    在画面上半部分找"眼睛"像素块。

    眼睛的特征：
        - 颜色很暗（接近黑色）；
        - 位于画面中部偏上的区域（0.25h ~ 0.6h）；
        - 是 2~20 像素的小色块（不是大片轮廓）；
        - 四周被不透明像素包围（在脸内部，而不是贴着身体边缘）。

    返回按从左到右排序的色块列表，每个元素是坐标集合 {(x, y), ...}。
    """
    width, height = img.size
    px = img.load()

    # 第一遍：收集上半部分足够暗的像素
    candidates = set()
    for y in range(int(height * 0.25), int(height * 0.6)):
        for x in range(int(width * 0.1), int(width * 0.9)):
            r, g, b, a = px[x, y]
            if a >= 128 and max(r, g, b) < 70:
                candidates.add((x, y))

    # 第二遍：四邻域聚类
    blobs = []
    while candidates:
        seed = candidates.pop()
        blob = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (x + dx, y + dy)
                if neighbor in candidates:
                    candidates.remove(neighbor)
                    blob.add(neighbor)
                    stack.append(neighbor)
        blobs.append(blob)

    # 第三遍：过滤——只保留尺寸合适且被不透明像素包围的小块
    def is_inside_face(blob):
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        # 尺寸过滤：眼睛通常 2~8 像素宽
        if max_x - min_x < 1 or max_x - min_x > 8:
            return False
        if max_y - min_y < 1 or max_y - min_y > 8:
            return False
        if len(blob) > 20:
            return False
        # 外围一圈不能有透明像素（否则是轮廓线而不是眼睛）
        for x in range(min_x - 1, max_x + 2):
            for y in (min_y - 1, max_y + 1):
                if 0 <= x < width and 0 <= y < height and px[x, y][3] < 128:
                    return False
        for y in range(min_y - 1, max_y + 2):
            for x in (min_x - 1, max_x + 1):
                if 0 <= x < width and 0 <= y < height and px[x, y][3] < 128:
                    return False
        return True

    blobs = [b for b in blobs if is_inside_face(b)]
    blobs.sort(key=lambda b: (sum(p[1] for p in b) / len(b),
                              sum(p[0] for p in b) / len(b)))
    return blobs


def pair_eye_blobs(blobs, width):
    """
    把识别到的暗色小块配成"左右两只眼"。

    规则：优先选择 y 坐标接近、且分别位于画面中线左右两侧的一对。
    找不到成对的就退化为"全部当成眼睛处理"，保证闭眼帧至少有点变化。
    """
    if len(blobs) < 2:
        return blobs

    centers = []
    for blob in blobs:
        cx = sum(p[0] for p in blob) / len(blob)
        cy = sum(p[1] for p in blob) / len(blob)
        centers.append((cx, cy, blob))

    center_x = width / 2
    left = [c for c in centers if c[0] < center_x]
    right = [c for c in centers if c[0] >= center_x]
    best = None
    for l in left:
        for r in right:
            if abs(l[1] - r[1]) > 4:  # 两只眼的高度差不能太大
                continue
            score = abs(l[1] - r[1])  # y 越接近越好
            if best is None or score < best[0]:
                best = (score, l[2], r[2])
    if best:
        return [best[1], best[2]]
    return blobs


def close_eyes(img):
    """
    返回一张"闭眼"的副本：把眼睛像素替换成周围脸皮颜色，再画一条横向细线。
    如果识别不到眼睛，则原样返回（生成一帧睁眼帧，动画仍可播放）。
    """
    img = img.copy()
    width, height = img.size
    px = img.load()

    blobs = pair_eye_blobs(find_eye_blobs(img), width)
    for blob in blobs:
        xs = [p[0] for p in blob]
        ys = [p[1] for p in blob]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        center_y = round(sum(ys) / len(ys))

        # 取眼睛块外围 1 圈的平均颜色作为"脸皮颜色"
        ring_colors = []
        for x in range(min_x - 1, max_x + 2):
            for y in range(min_y - 1, max_y + 2):
                if (x, y) in blob:
                    continue
                if 0 <= x < width and 0 <= y < height:
                    r, g, b, a = px[x, y]
                    if a >= 128:
                        ring_colors.append((r, g, b))
        if ring_colors:
            skin = tuple(round(sum(c[i] for c in ring_colors) / len(ring_colors)) for i in range(3))
        else:
            skin = (200, 200, 200)

        # 1) 把原眼睛像素涂成脸皮颜色
        for x, y in blob:
            px[x, y] = (*skin, 255)
        # 2) 在眼睛中心行画一条"闭眼线"
        for x in range(min_x, max_x + 1):
            px[x, center_y] = (20, 20, 20, 255)
    return img


def draw_hearts(img, positions):
    """在画布指定位置画粉色小心心，返回副本。"""
    img = img.copy()
    px = img.load()
    width, height = img.size
    for start_x, start_y in positions:
        for row, line in enumerate(HEART_PATTERN):
            for col, ch in enumerate(line):
                if ch != "X":
                    continue
                x, y = start_x + col, start_y + row
                if 0 <= x < width and 0 <= y < height:
                    px[x, y] = HEART_COLOR
    return img


def main():
    """生成 blink_*.png 和 pet_*.png。"""
    if not os.path.isdir(ASSET_DIR):
        print(f"素材目录不存在: {ASSET_DIR}")
        sys.exit(1)

    # ---- 生成眨眼帧 ----
    for i, source_id in enumerate(BLINK_SOURCE_IDS, start=1):
        base = load_idle_frame(source_id)
        # 奇数帧睁眼，偶数帧闭眼，形成 睁-闭-睁-闭 的眨眼循环
        frame = base if i % 2 == 1 else close_eyes(base)
        path = os.path.join(ASSET_DIR, f"blink_{i}.png")
        frame.save(path)
        print(f"已生成: {path}")

    # ---- 生成被撸帧 ----
    for i, source_id in enumerate(PET_SOURCE_IDS, start=1):
        base = load_idle_frame(source_id)
        frame = draw_hearts(base, HEART_POSITIONS[i - 1])
        path = os.path.join(ASSET_DIR, f"pet_{i}.png")
        frame.save(path)
        print(f"已生成: {path}")

    print("完成！可以把 assets/cat 下的素材替换成你家猫的图，命名规范见 README.md。")


if __name__ == "__main__":
    main()
