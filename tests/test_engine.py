#!/usr/bin/env python3
"""test_engine.py — 针对 Pipeline Engine 核心深模块的单元测试。"""

import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from engine import (
    SingleInstanceLock,
    get_image_kind,
    is_path_inside,
    find_image_path,
    generate_image_asset,
    InvalidArgumentError,
    LockBusyError,
)


class TestPipelineEngine(unittest.TestCase):
    def test_get_image_kind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)

            # PNG
            png_file = tmp_path / "valid.png"
            png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)
            kind = get_image_kind(png_file)
            self.assertIsNotNone(kind)
            self.assertEqual(kind["ext"], ".png")

            # JPG
            jpg_file = tmp_path / "valid.jpg"
            jpg_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 20)
            kind = get_image_kind(jpg_file)
            self.assertIsNotNone(kind)
            self.assertEqual(kind["ext"], ".jpg")

            # WEBP
            webp_file = tmp_path / "valid.webp"
            webp_file.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20)
            kind = get_image_kind(webp_file)
            self.assertIsNotNone(kind)
            self.assertEqual(kind["ext"], ".webp")

            # 非法小文件 / 文本
            txt_file = tmp_path / "invalid.txt"
            txt_file.write_text("not an image", encoding="utf-8")
            self.assertIsNone(get_image_kind(txt_file))

    def test_is_path_inside(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = pathlib.Path(tmpdir) / "work"
            outside_dir = pathlib.Path(tmpdir) / "outside"
            work_dir.mkdir()
            outside_dir.mkdir()

            inside_file = work_dir / "gen.png"
            inside_file.write_text("sample", encoding="utf-8")
            outside_file = outside_dir / "ref.png"
            outside_file.write_text("sample", encoding="utf-8")

            self.assertTrue(is_path_inside(inside_file, work_dir))
            self.assertFalse(is_path_inside(outside_file, work_dir))

    def test_find_image_path_confinement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = pathlib.Path(tmpdir) / "work"
            outside_dir = pathlib.Path(tmpdir) / "outside"
            work_dir.mkdir()
            outside_dir.mkdir()

            real_gen_file = work_dir / "output.png"
            real_gen_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)

            outside_ref_file = outside_dir / "user_ref.png"
            outside_ref_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)

            # 模拟场景：模型在文本中引用了外部参考图路径，但未作为合法工作区图片输出
            response_text = f"""
            I modified the image based on reference: {outside_ref_file.resolve()}
            IMAGE_PATH: {outside_ref_file.resolve()}
            """
            found = find_image_path(response_text, work_dir)
            self.assertEqual(found, real_gen_file)
            self.assertNotEqual(found, outside_ref_file)

    def test_single_instance_lock(self):
        lock1 = SingleInstanceLock(wait_seconds=1)
        lock1.acquire()
        try:
            lock2 = SingleInstanceLock(wait_seconds=1)
            with self.assertRaises(LockBusyError):
                lock2.acquire()
        finally:
            lock1.release()

    def test_validation_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = pathlib.Path(tmpdir) / "test.png"

            with self.assertRaises(InvalidArgumentError):
                generate_image_asset(prompt="", output=out_file)

            with self.assertRaises(InvalidArgumentError):
                generate_image_asset(prompt="cube", output=out_file, ratio="99:1")

            with self.assertRaises(InvalidArgumentError):
                generate_image_asset(prompt="cube", output=out_file, chromakey="yellow")

            with self.assertRaises(InvalidArgumentError):
                generate_image_asset(prompt="cube", output=out_file, canvas=-10)


if __name__ == "__main__":
    unittest.main()
