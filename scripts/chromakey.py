#!/usr/bin/env python3
"""chromakey.py — 通用色键抠图与资产规约深模块。

提供针对切片资产 (Isolated Asset) 的纯内存规约深模块，以及面向文件和 CLI 的轻量适配器。

核心深接口:
  standardize_isolated_asset(im, bg_color, canvas_size, padding_ratio, ...) -> Image.Image

薄适配器:
  process_image(src_path, dst_path, ...) -> bool
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PIL import Image, ImageChops


# ==============================================================================
# 领域异常契约
# ==============================================================================

class StandardizationError(ValueError):
    """资产规约基础领域异常。"""
    pass


class EmptyAlphaError(StandardizationError):
    """抠图后全透明异常（通常由于图像底色与指定的 bg_color 不符）。"""
    pass


# ==============================================================================
# 私有标量算子与向量化 LUT 构造实现 (内部实现细节)
# ==============================================================================

def _calculate_alpha_green(r: int, g: int, b: int, threshold: float = 100.0, softness: float = 60.0) -> float:
    """计算绿底像素的保留 alpha（0.0 为完全背景，1.0 为完全主体）。"""
    greenness = g - max(r, b)
    if greenness <= (threshold - softness):
        return 1.0
    if greenness >= threshold:
        return 0.0
    return max(0.0, min(1.0, (threshold - greenness) / softness))


def _calculate_alpha_magenta(r: int, g: int, b: int, threshold: float = 80.0, softness: float = 60.0) -> float:
    """计算洋红底（品红）像素的保留 alpha。"""
    magentaness = min(r, b) - g
    if magentaness <= (threshold - softness):
        return 1.0
    if magentaness >= threshold:
        return 0.0
    return max(0.0, min(1.0, (threshold - magentaness) / softness))


def _despill_green(r: int, g: int, b: int, alpha: float) -> Tuple[int, int, int]:
    """抑制半透明边缘的绿溢色。"""
    if alpha >= 0.99 or alpha <= 0.01:
        return r, g, b
    max_allowed_g = int((r + b) / 2)
    new_g = min(g, max_allowed_g) if g > max_allowed_g else g
    final_g = int(g * alpha + new_g * (1.0 - alpha))
    return r, final_g, b


def _despill_magenta(r: int, g: int, b: int, alpha: float) -> Tuple[int, int, int]:
    """抑制半透明边缘的洋红溢色。"""
    if alpha >= 0.99 or alpha <= 0.01:
        return r, g, b
    new_r = min(r, g)
    new_b = min(b, g)
    final_r = int(r * alpha + new_r * (1.0 - alpha))
    final_b = int(b * alpha + new_b * (1.0 - alpha))
    return final_r, g, final_b


def _chromakey_vectorized(
    im: Image.Image,
    bg_color: str = "green",
    threshold: float | None = None,
    softness: float = 60.0,
) -> Image.Image:
    """纯 Pillow 原生算子执行全图向量化色键抠图与去溢色（比逐像素遍历提速 40x+）。"""
    if threshold is None:
        threshold = 80.0 if bg_color == "magenta" else 100.0

    r, g, b, _ = im.split()
    if bg_color == "magenta":
        min_rb = ImageChops.darker(r, b)
        magentaness = ImageChops.subtract(min_rb, g)
        lut = [int(round(_calculate_alpha_magenta(gn, 0, gn, threshold, softness) * 255)) for gn in range(256)]
        alpha = magentaness.point(lut, mode="L")
        new_r = ImageChops.darker(r, g)
        new_b = ImageChops.darker(b, g)
        final_r = Image.composite(r, new_r, alpha)
        final_b = Image.composite(b, new_b, alpha)
        final_g = g
    else:
        max_rb = ImageChops.lighter(r, b)
        greenness = ImageChops.subtract(g, max_rb)
        lut = [int(round(_calculate_alpha_green(0, gn, 0, threshold, softness) * 255)) for gn in range(256)]
        alpha = greenness.point(lut, mode="L")
        rb_avg = ImageChops.add(r, b, scale=2.0)
        new_g = ImageChops.darker(g, rb_avg)
        final_g = Image.composite(g, new_g, alpha)
        final_r, final_b = r, b

    return Image.merge("RGBA", (final_r, final_g, final_b, alpha))


# 向后兼容别名（供外部特殊测试工具使用）
calculate_alpha_green = _calculate_alpha_green
calculate_alpha_magenta = _calculate_alpha_magenta
despill_green = _despill_green
despill_magenta = _despill_magenta
chromakey_vectorized = _chromakey_vectorized


# ==============================================================================
# 纯内存资产规约核心接口 (Deep Module Interface)
# ==============================================================================

def standardize_isolated_asset(
    im: Image.Image,
    bg_color: str = "green",
    canvas_size: int | None = None,
    padding_ratio: float = 0.04,
    threshold: float | None = None,
    softness: float = 60.0,
) -> Image.Image:
    """在纯内存中完成色键抠图、去溢色、紧凑包围盒裁剪与等比居中呼吸留白规约。

    参数:
        im: 输入的 PIL 图像对象
        bg_color: 纯色背景类型 ('green' 或 'magenta')
        canvas_size: 目标正方形画布尺寸 (如 64, 96, 128, 256)；若为 None 则保持原紧凑裁剪尺寸
        padding_ratio: 呼吸边距占画布边长的比例 (默认 0.04 即 4%)
        threshold: 色相差判定阈值
        softness: 边缘羽化过渡宽度

    返回:
        规约后的全新 RGBA PIL 图像对象。

    抛出:
        EmptyAlphaError: 抠图后完全透明（底色与选择的 bg_color 不符）。
        StandardizationError: 参数非法或几何尺寸无效。
    """
    if bg_color not in ("green", "magenta"):
        raise StandardizationError(f"unsupported bg_color: '{bg_color}', expected 'green' or 'magenta'")
    if canvas_size is not None and canvas_size <= 0:
        raise StandardizationError(f"canvas_size must be positive, got {canvas_size}")
    if padding_ratio < 0.0 or padding_ratio >= 0.5:
        raise StandardizationError(f"padding_ratio must be in [0.0, 0.5), got {padding_ratio}")

    im_rgba = im.convert("RGBA") if im.mode != "RGBA" else im
    keyed = _chromakey_vectorized(im_rgba, bg_color=bg_color, threshold=threshold, softness=softness)

    bbox = keyed.getchannel("A").getbbox()
    if bbox is None:
        raise EmptyAlphaError(f"chromakey resulted in completely transparent image with bg_color={bg_color}")

    cropped = keyed.crop(bbox)
    if canvas_size is None:
        return cropped

    crop_w, crop_h = cropped.size
    pad_px = int(canvas_size * padding_ratio)
    inner_w = canvas_size - pad_px * 2
    inner_h = canvas_size - pad_px * 2

    if inner_w <= 0 or inner_h <= 0:
        raise StandardizationError(f"canvas_size {canvas_size} too small for padding_ratio {padding_ratio}")

    scale = min(inner_w / crop_w, inner_h / crop_h)
    new_w = max(1, round(crop_w * scale))
    new_h = max(1, round(crop_h * scale))

    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    final_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset_x = (canvas_size - new_w) // 2
    offset_y = (canvas_size - new_h) // 2
    final_canvas.paste(resized, (offset_x, offset_y), resized)
    return final_canvas


# ==============================================================================
# 磁盘与文件适配器 (Disk Adapter)
# ==============================================================================

def process_image(
    src_path: pathlib.Path | str,
    dst_path: pathlib.Path | str,
    bg_color: str = "green",
    canvas_size: int | None = None,
    padding_ratio: float = 0.04,
    dry_run: bool = False,
    threshold: float | None = None,
    softness: float = 60.0,
    verbose: bool = False,
) -> bool:
    """对单张文件执行规约。保持向后兼容性。"""
    src = pathlib.Path(src_path)
    dst = pathlib.Path(dst_path)

    if not src.is_file():
        if verbose:
            print(f"[-] 文件不存在: {src}", file=sys.stderr)
        return False

    try:
        with Image.open(src) as im:
            final_img = standardize_isolated_asset(
                im=im,
                bg_color=bg_color,
                canvas_size=canvas_size,
                padding_ratio=padding_ratio,
                threshold=threshold,
                softness=softness,
            )
            src_size = im.size
    except Exception as e:
        if verbose:
            print(f"[-] 处理图像失败 {src}: {e}", file=sys.stderr)
        return False

    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final_img.save(dst, format="PNG")

    if verbose:
        alpha_hist = final_img.getchannel("A").histogram()
        opaque_px = sum(alpha_hist[1:])
        total_px = final_img.width * final_img.height
        print(
            f"[Chromakey] {dst.name if not dry_run else '(dry) ' + dst.name} "
            f"| 画布: {final_img.width}x{final_img.height} "
            f"| 源: {src_size[0]}x{src_size[1]} "
            f"| 不透明度: {100.0 * opaque_px / total_px:.1f}%"
        )

    return True


# ==============================================================================
# CLI 适配器 (CLI Adapter)
# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="通用色键抠图与规格化工具")
    parser.add_argument("input", help="输入图像路径或包含图像的目录")
    parser.add_argument("-o", "--output", required=True, help="输出图像路径或输出目录")
    parser.add_argument("--bg", choices=["green", "magenta"], default="green", help="底色选择 (默认 green)")
    parser.add_argument("--canvas", type=int, default=None, help="正方形画布尺寸 (例如 64, 96, 128, 256)")
    parser.add_argument("--padding", type=float, default=0.04, help="内容框呼吸留白比例 (默认 0.04 即 4%%)")
    parser.add_argument("--threshold", type=float, default=None, help="色键判定阈值 (默认 green=100.0, magenta=80.0)")
    parser.add_argument("--softness", type=float, default=60.0, help="边缘平滑过渡宽度 (默认 60.0)")
    parser.add_argument("--dry", action="store_true", help="演练模式，不写入文件")
    parser.add_argument("--quiet", action="store_true", help="静默模式，不输出统计信息")
    args = parser.parse_args()

    src = pathlib.Path(args.input)
    dst = pathlib.Path(args.output)
    verbose = not args.quiet

    if src.is_file():
        success = process_image(
            src,
            dst,
            bg_color=args.bg,
            canvas_size=args.canvas,
            padding_ratio=args.padding,
            dry_run=args.dry,
            threshold=args.threshold,
            softness=args.softness,
            verbose=verbose,
        )
        return 0 if success else 1

    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in src.iterdir() if p.is_file() and p.suffix.lower() in valid_exts]
        if not files:
            print(f"目录中未找到支持的图像: {src}", file=sys.stderr)
            return 1

        stem_counts: dict[str, int] = {}
        for f in files:
            stem_counts[f.stem] = stem_counts.get(f.stem, 0) + 1

        ok_count = 0
        for f in files:
            if stem_counts[f.stem] > 1:
                clean_ext = f.suffix.lstrip(".").lower()
                out_name = f"{f.stem}_{clean_ext}.png"
            else:
                out_name = f"{f.stem}.png"

            out_file = dst / out_name
            if process_image(
                f,
                out_file,
                bg_color=args.bg,
                canvas_size=args.canvas,
                padding_ratio=args.padding,
                dry_run=args.dry,
                threshold=args.threshold,
                softness=args.softness,
                verbose=verbose,
            ):
                ok_count += 1
        if verbose:
            print(f"处理完成: 成功 {ok_count} / {len(files)}")
        return 0 if ok_count > 0 else 1

    print(f"路径无效: {src}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
