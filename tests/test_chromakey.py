#!/usr/bin/env python3
"""test_chromakey.py — 针对 Asset Standardizer 纯内存深模块与磁盘适配器的单元测试。"""

import pathlib
import sys
import tempfile
import unittest
from PIL import Image

# 确保 scripts 模块可导入
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chromakey import (
    standardize_isolated_asset,
    process_image,
    StandardizationError,
    EmptyAlphaError,
    _chromakey_vectorized,
    _calculate_alpha_green,
    _calculate_alpha_magenta,
    _despill_green,
    _despill_magenta,
)


class TestAssetStandardizer(unittest.TestCase):
    def test_standardize_in_memory_green(self):
        """测试纯内存绿底资产规约：抠图、去色溢、紧凑裁剪与画幅呼吸留白居中。"""
        # 创建 100x100 绿底测试图，中心 40x40 红色方块
        img = Image.new("RGBA", (100, 100), (10, 245, 10, 255))
        for y in range(30, 70):
            for x in range(30, 70):
                img.putpixel((x, y), (230, 30, 30, 255))

        out_img = standardize_isolated_asset(
            img,
            bg_color="green",
            canvas_size=64,
            padding_ratio=0.04,
        )

        self.assertEqual(out_img.size, (64, 64))
        self.assertEqual(out_img.mode, "RGBA")

        # 验证四周角彻底透明
        corners = [(0, 0), (63, 0), (0, 63), (63, 63)]
        for pt in corners:
            self.assertEqual(out_img.getpixel(pt)[3], 0)

        # 验证主体中心像素不透明且为主体红色
        center = out_img.getpixel((32, 32))
        self.assertGreater(center[0], 180)  # R
        self.assertGreater(center[3], 200)  # Alpha

    def test_standardize_in_memory_magenta(self):
        """测试纯内存洋红底资产规约：绿植主体在洋红底中必须被完整保留。"""
        # 创建 100x100 洋红底测试图 (R=240, G=15, B=240)，中心放置纯绿草木主体 (G=220)
        img = Image.new("RGBA", (100, 100), (240, 15, 240, 255))
        for y in range(25, 75):
            for x in range(25, 75):
                img.putpixel((x, y), (20, 220, 20, 255))

        out_img = standardize_isolated_asset(
            img,
            bg_color="magenta",
            canvas_size=128,
            padding_ratio=0.04,
        )

        self.assertEqual(out_img.size, (128, 128))
        self.assertEqual(out_img.mode, "RGBA")

        # 验证洋红底已完全透明
        self.assertEqual(out_img.getpixel((0, 0))[3], 0)

        # 验证绿色主体保留完好
        center = out_img.getpixel((64, 64))
        self.assertGreater(center[1], 180)  # G
        self.assertGreater(center[3], 200)  # Alpha

    def test_standardize_tight_crop_when_no_canvas(self):
        """当 canvas_size 为 None 时，应返回紧凑 Bbox 裁剪产物。"""
        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        # 放置一个 20x30 的前景方块
        for y in range(40, 70):
            for x in range(30, 50):
                img.putpixel((x, y), (255, 0, 0, 255))

        out_img = standardize_isolated_asset(img, bg_color="green", canvas_size=None)
        self.assertEqual(out_img.size, (20, 30))

    def test_standardize_empty_alpha_error(self):
        """当图像底色与指定的 bg_color 不符导致全图被抠空时，必须抛出 EmptyAlphaError。"""
        # 纯红图像，如果按 green 抠图，Red主体不会被扣掉；但如果指定纯绿底图却用 magenta 抠图
        green_img = Image.new("RGBA", (50, 50), (10, 245, 10, 255))
        with self.assertRaises(EmptyAlphaError):
            # 用 magenta 规则扣纯绿图，因为 min(R,B)-G 极小不会被扣空？不对：
            # 纯绿图 magentaness = min(10,10)-245 = -235 <= (80-60)=20 => alpha=1.0 (全保留，不会空)
            # 要产生全透明，需要 magentaness >= threshold(80) => min(R,B) - G >= 80，即洋红图！
            # 如果是纯洋红图用 magenta 扣，会全透明！
            magenta_bg = Image.new("RGBA", (50, 50), (240, 10, 240, 255))
            standardize_isolated_asset(magenta_bg, bg_color="magenta")

    def test_standardize_invalid_arguments(self):
        """非法参数校验。"""
        img = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
        with self.assertRaises(StandardizationError):
            standardize_isolated_asset(img, bg_color="blue")

        with self.assertRaises(StandardizationError):
            standardize_isolated_asset(img, canvas_size=-10)

        with self.assertRaises(StandardizationError):
            standardize_isolated_asset(img, padding_ratio=0.6)

    def test_vectorized_consistency(self):
        """数学一致性校验：验证内部向量化通道算子与逐像素标量参考实现结果绝对一致。"""
        img = Image.new("RGBA", (32, 32))
        px = img.load()
        for y in range(32):
            for x in range(32):
                px[x, y] = (x * 8, y * 8, ((x + y) * 4) % 256, 255)

        for bg in ("green", "magenta"):
            vec_out = _chromakey_vectorized(img, bg_color=bg)
            v_px = vec_out.load()
            calc_alpha = _calculate_alpha_magenta if bg == "magenta" else _calculate_alpha_green
            calc_despill = _despill_magenta if bg == "magenta" else _despill_green
            thresh = 80.0 if bg == "magenta" else 100.0

            for y in range(32):
                for x in range(32):
                    r, g, b, _ = px[x, y]
                    a_expected = calc_alpha(r, g, b, threshold=thresh, softness=60.0)
                    expected_alpha = int(round(a_expected * 255))
                    v_r, v_g, v_b, v_a = v_px[x, y]

                    self.assertLessEqual(abs(v_a - expected_alpha), 1)
                    if expected_alpha > 0:
                        exp_r, exp_g, exp_b = calc_despill(r, g, b, a_expected)
                        self.assertLessEqual(abs(v_r - exp_r), 1)
                        self.assertLessEqual(abs(v_g - exp_g), 1)
                        self.assertLessEqual(abs(v_b - exp_b), 1)

    def test_process_image_disk_adapter(self):
        """磁盘适配器端到端集成测试。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            src_path = tmp_path / "raw.png"
            dst_path = tmp_path / "processed.png"

            img = Image.new("RGBA", (64, 64), (0, 255, 0, 255))
            for y in range(20, 44):
                for x in range(20, 44):
                    img.putpixel((x, y), (255, 255, 0, 255))
            img.save(src_path)

            success = process_image(src_path, dst_path, bg_color="green", canvas_size=32)
            self.assertTrue(success)
            self.assertTrue(dst_path.is_file())

            with Image.open(dst_path) as out:
                self.assertEqual(out.size, (32, 32))


if __name__ == "__main__":
    unittest.main()
