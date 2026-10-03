#!/usr/bin/env python3
"""chromakey.py — 通用色键抠图与资产规约工具。

功能特性：
1. 双色键支持：
   - --bg green:   适合常规角色/物体，判据 greenness = G - max(R, B)
   - --bg magenta: 适合绿色系、草木系角色，判据 magentaness = min(R, B) - G
2. 去色溢（Despill）：
   - 自动消除边缘由于半透明采样引入的背景溢色（去绿边/去紫边），保留本体真实色彩
3. 尺寸规约与呼吸留白：
   - 按 alpha > 0 提取紧凑包围盒（getbbox）
   - 按比例自适应缩放到目标画布（--canvas 64|96|128|256|512），默认居中并保留 4% 呼吸边距
4. 单图与批量处理：
   - 支持单张图片或整个目录批量规约

用法示例：
  python scripts/chromakey.py input.jpg -o output.png --bg green --canvas 256
  python scripts/chromakey.py art-inbox/ -o raw-assets/ --bg magenta --canvas 96
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Tuple

from PIL import Image


def calculate_alpha_green(r: int, g: int, b: int, threshold: float = 100.0, softness: float = 60.0) -> float:
    """计算绿底像素的保留 alpha（0.0 为完全背景，1.0 为完全主体）。"""
    # 绿意纯度 = G - max(R, B)
    # 绿底通常 G>240 且 R,B<30 => greenness ≈ 210+
    greenness = g - max(r, b)
    if greenness <= (threshold - softness):
        return 1.0
    if greenness >= threshold:
        return 0.0
    return max(0.0, min(1.0, (threshold - greenness) / softness))


def calculate_alpha_magenta(r: int, g: int, b: int, threshold: float = 80.0, softness: float = 60.0) -> float:
    """计算洋红底（品红）像素的保留 alpha。"""
    # 洋红纯度 = min(R, B) - G
    # 品红底通常 R>230, B>230 且 G<30 => magentaness ≈ 200+
    magentaness = min(r, b) - g
    if magentaness <= (threshold - softness):
        return 1.0
    if magentaness >= threshold:
        return 0.0
    return max(0.0, min(1.0, (threshold - magentaness) / softness))


def despill_green(r: int, g: int, b: int, alpha: float) -> Tuple[int, int, int]:
    """抑制半透明边缘的绿溢色（Green Despill）。"""
    if alpha >= 0.99 or alpha <= 0.01:
        return r, g, b
    # 将 G 限制在 (R + B) / 2 之内，并向邻近中性色过渡
    max_allowed_g = int((r + b) / 2)
    new_g = min(g, max_allowed_g) if g > max_allowed_g else g
    # 融合抑制
    final_g = int(g * alpha + new_g * (1.0 - alpha))
    return r, final_g, b


def despill_magenta(r: int, g: int, b: int, alpha: float) -> Tuple[int, int, int]:
    """抑制半透明边缘的洋红溢色（Magenta Despill）。"""
    if alpha >= 0.99 or alpha <= 0.01:
        return r, g, b
    # 洋红是高 R 和高 B，将 R 和 B 压向 G
    new_r = min(r, g)
    new_b = min(b, g)
    final_r = int(r * alpha + new_r * (1.0 - alpha))
    final_b = int(b * alpha + new_b * (1.0 - alpha))
    return final_r, g, final_b


def process_image(
    src_path: pathlib.Path,
    dst_path: pathlib.Path,
    bg_color: str = "green",
    canvas_size: int | None = None,
    padding_ratio: float = 0.04,
    dry_run: bool = False,
) -> bool:
    """对单张图片进行色键抠图、去溢色、规约画布尺寸。"""
    if not src_path.exists():
        print(f"[-] 文件不存在: {src_path}", file=sys.stderr)
        return False

    try:
        im = Image.open(src_path).convert("RGBA")
    except Exception as e:
        print(f"[-] 无法读取图像 {src_path}: {e}", file=sys.stderr)
        return False

    w, h = im.size
    px = im.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()

    calc_alpha = calculate_alpha_magenta if bg_color == "magenta" else calculate_alpha_green
    despill = despill_magenta if bg_color == "magenta" else despill_green

    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            a = calc_alpha(r, g, b)
            if a <= 0.0:
                continue
            r_d, g_d, b_d = despill(r, g, b, a)
            op[x, y] = (r_d, g_d, b_d, int(round(a * 255)))

    bbox = out.getbbox()
    if bbox is None:
        print(f"[-] {src_path.name}: 抠图后完全透明，可能底色与选择的 --bg={bg_color} 不符", file=sys.stderr)
        return False

    cropped = out.crop(bbox)
    crop_w, crop_h = cropped.size

    # 如果指定了目标画布尺寸（如 96, 256 等）
    if canvas_size and canvas_size > 0:
        pad_px = int(canvas_size * padding_ratio)
        inner_w = canvas_size - pad_px * 2
        inner_h = canvas_size - pad_px * 2

        scale = min(inner_w / crop_w, inner_h / crop_h)
        new_w = max(1, round(crop_w * scale))
        new_h = max(1, round(crop_h * scale))

        resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        final_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        offset_x = (canvas_size - new_w) // 2
        offset_y = (canvas_size - new_h) // 2
        final_canvas.paste(resized, (offset_x, offset_y), resized)
    else:
        final_canvas = cropped

    if not dry_run:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        final_canvas.save(dst_path, format="PNG")

    opaque_px = sum(1 for p in final_canvas.getdata() if p[3] > 0)
    total_px = final_canvas.width * final_canvas.height
    print(
        f"[Chromakey] {dst_path.name if not dry_run else '(dry) ' + dst_path.name} "
        f"| 画布: {final_canvas.width}x{final_canvas.height} "
        f"| 源: {w}x{h} "
        f"| 内容: {crop_w}x{crop_h} "
        f"| 不透明度: {100.0 * opaque_px / total_px:.1f}%"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="通用色键抠图与规格化工具")
    parser.add_argument("input", help="输入图像路径或包含图像的目录")
    parser.add_argument("-o", "--output", required=True, help="输出图像路径或输出目录")
    parser.add_argument("--bg", choices=["green", "magenta"], default="green", help="底色选择 (默认 green)")
    parser.add_argument("--canvas", type=int, default=None, help="正方形画布尺寸 (例如 64, 96, 128, 256)")
    parser.add_argument("--padding", type=float, default=0.04, help="内容框呼吸留白比例 (默认 0.04 即 4%%)")
    parser.add_argument("--dry", action="store_true", help="演练模式，不写入文件")
    args = parser.parse_args()

    src = pathlib.Path(args.input)
    dst = pathlib.Path(args.output)

    if src.is_file():
        success = process_image(src, dst, args.bg, args.canvas, args.padding, args.dry)
        return 0 if success else 1

    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in src.iterdir() if p.is_file() and p.suffix.lower() in valid_exts]
        if not files:
            print(f"目录中未找到支持的图像: {src}", file=sys.stderr)
            return 1
        ok_count = 0
        for f in files:
            out_file = dst / f"{f.stem}.png"
            if process_image(f, out_file, args.bg, args.canvas, args.padding, args.dry):
                ok_count += 1
        print(f"处理完成: 成功 {ok_count} / {len(files)}")
        return 0 if ok_count > 0 else 1

    print(f"路径无效: {src}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
