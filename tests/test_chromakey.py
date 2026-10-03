#!/usr/bin/env python3
"""test_chromakey.py — chromakey 抠图与去色溢单元测试。"""

import pathlib
import sys
import tempfile
from PIL import Image

# 确保 scripts 模块可导入
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chromakey import (
    calculate_alpha_green,
    calculate_alpha_magenta,
    despill_green,
    despill_magenta,
    process_image,
)


def test_green_keyout():
    # 纯绿背景 (G 高，R/B 极低)
    assert calculate_alpha_green(10, 245, 10) == 0.0
    # 纯红主体
    assert calculate_alpha_green(220, 20, 20) == 1.0
    # 纯蓝主体
    assert calculate_alpha_green(20, 20, 220) == 1.0
    # 白色主体 (高光)
    assert calculate_alpha_green(250, 250, 250) == 1.0
    # 金黄色主体 (R/G 均高)
    assert calculate_alpha_green(230, 200, 20) == 1.0


def test_magenta_keyout():
    # 纯洋红背景 (R/B 极高，G 极低)
    assert calculate_alpha_magenta(240, 15, 240) == 0.0
    # 绿色草木主体 (G 高，R/B 低) -> 在洋红底中必须被完整保留
    assert calculate_alpha_magenta(20, 220, 20) == 1.0
    # 纯黄主体
    assert calculate_alpha_magenta(240, 240, 20) == 1.0


def test_despill():
    # 半透明边缘带绿溢色 (R=50, G=180, B=50, alpha=0.5)
    r, g, b = despill_green(50, 180, 50, 0.5)
    assert g < 180  # G 分量被有效压制

    # 洋红边缘带紫红溢色
    r_m, g_m, b_m = despill_magenta(180, 50, 180, 0.5)
    assert r_m < 180 and b_m < 180


def test_process_image_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)
        src_img_path = tmp_path / "test_green_box.png"
        dst_img_path = tmp_path / "test_output.png"

        # 生成 100x100 图像：纯绿背景，中心 40x40 红色方块
        img = Image.new("RGBA", (100, 100), (10, 245, 10, 255))
        for y in range(30, 70):
            for x in range(30, 70):
                img.putpixel((x, y), (230, 30, 30, 255))
        img.save(src_img_path)

        # 执行规约至 64x64
        success = process_image(
            src_path=src_img_path,
            dst_path=dst_img_path,
            bg_color="green",
            canvas_size=64,
            padding_ratio=0.04,
        )

        assert success is True
        assert dst_img_path.exists()

        result = Image.open(dst_img_path)
        assert result.size == (64, 64)

        # 检查四周角（原绿底）已透明
        corners = [
            result.getpixel((0, 0)),
            result.getpixel((63, 0)),
            result.getpixel((0, 63)),
            result.getpixel((63, 63)),
        ]
        for c in corners:
            assert c[3] == 0  # alpha 必须为 0

        # 检查中心像素为红色且不透明
        center = result.getpixel((32, 32))
        assert center[0] > 180  # R
        assert center[3] > 200  # 不透明度


if __name__ == "__main__":
    test_green_keyout()
    test_magenta_keyout()
    test_despill()
    test_process_image_end_to_end()
    print("[+] 全部单元测试通过！")
