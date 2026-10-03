#!/usr/bin/env python3
"""test_mock_agy.py — 使用模拟 agy 脚本验证 Pipeline Engine 端到端调度、管道防死锁与原图保护。"""

import os
import pathlib
import sys
import tempfile
import unittest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from engine import generate_image_asset


class TestMockAgyE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = pathlib.Path(self.tmpdir.name)

        # 模拟生成 100x100 纯绿底、中心红色的合法位图
        self.sample_img_path = self.tmp_path / "mock_template.png"
        img = Image.new("RGBA", (100, 100), (10, 245, 10, 255))
        for y in range(30, 70):
            for x in range(30, 70):
                img.putpixel((x, y), (230, 30, 30, 255))
        img.save(self.sample_img_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_mock_agy(self, behavior: str = "success") -> pathlib.Path:
        """创建用于测试的 mock agy 脚本入口。"""
        runner_py = self.tmp_path / "fake_agy_runner.py"
        template_str = str(self.sample_img_path.resolve()).replace("\\", "\\\\")

        code = f"""import sys, os, pathlib, shutil, time

behavior = "{behavior}"
# 必须完全消费 stdin
_ = sys.stdin.read()

# 从命令行参数提取工作目录
work_dir = None
for i, arg in enumerate(sys.argv):
    if arg == "--add-dir" and i + 1 < len(sys.argv):
        work_dir = pathlib.Path(sys.argv[i + 1])
        break

if behavior == "success":
    out_img = work_dir / "generated.png"
    shutil.copy2(r"{template_str}", out_img)
    # 打印 64KB+ 的大量日志，用于压力测试子进程管道是否会出现死锁！
    large_payload = "A" * 1024
    for _ in range(65):
        print(large_payload)
    print(f"IMAGE_PATH: {{out_img.resolve()}}")
    sys.exit(0)

elif behavior == "retry_once":
    counter_file = pathlib.Path(r"{self.tmp_path.resolve()}".replace("\\\\", "/")) / "attempt.cnt"
    attempt = 1
    if counter_file.exists():
        attempt = int(counter_file.read_text().strip()) + 1
    counter_file.write_text(str(attempt))

    if attempt == 1:
        # 第一次模拟失败（无 IMAGE_PATH）
        print("transient error, no image generated")
        sys.exit(0)
    else:
        out_img = work_dir / "retry_gen.png"
        shutil.copy2(r"{template_str}", out_img)
        print(f"IMAGE_PATH: {{out_img.resolve()}}")
        sys.exit(0)
"""
        runner_py.write_text(code, encoding="utf-8")

        # Windows 下包装为 .cmd 批处理入口，Linux/macOS 下为可执行脚本
        if sys.platform == "win32":
            cmd_entry = self.tmp_path / "fake_agy.cmd"
            cmd_entry.write_text(f'@"{sys.executable}" "{runner_py.resolve()}" %*\n', encoding="utf-8")
            return cmd_entry
        else:
            sh_entry = self.tmp_path / "fake_agy"
            sh_entry.write_text(f'#!/usr/bin/env sh\nexec "{sys.executable}" "{runner_py.resolve()}" "$@"\n', encoding="utf-8")
            sh_entry.chmod(0o755)
            return sh_entry

    def test_e2e_full_frame_and_pipeline_unblock(self):
        """测试 1：大输出（64KB+ 管道压力）正常通信，不发生死锁，全幅图像正常落地。"""
        mock_agy = self._create_mock_agy(behavior="success")
        os.environ["AGY_IMG_AGY"] = str(mock_agy.resolve())
        os.environ["ANTIGRAVITY_API_KEY"] = "mock_key_for_testing"

        target_output = self.tmp_path / "dist" / "wallpaper.png"
        custom_lock = self.tmp_path / "test_isolated.lock"

        final_path = generate_image_asset(
            prompt="Epic landscape with mountains and lake",
            output=target_output,
            ratio="16:9",
            lock_path=custom_lock,
        )

        self.assertTrue(final_path.is_file())
        self.assertEqual(final_path.resolve(), target_output.resolve())
        self.assertGreater(final_path.stat().st_size, 100)

    def test_e2e_chromakey_and_raw_preservation(self):
        """测试 2：色键抠图一步到位，且原始未抠图绿底图被安全保留为 *_raw.png。"""
        mock_agy = self._create_mock_agy(behavior="success")
        os.environ["AGY_IMG_AGY"] = str(mock_agy.resolve())
        os.environ["ANTIGRAVITY_API_KEY"] = "mock_key_for_testing"

        target_output = self.tmp_path / "dist" / "hero.png"
        custom_lock = self.tmp_path / "test_isolated_chroma.lock"

        final_path = generate_image_asset(
            prompt="A brave knight, solid pure neon green background",
            output=target_output,
            chromakey="green",
            canvas=64,
            keep_raw=True,
            lock_path=custom_lock,
        )

        # 检查抠图后的主产物
        self.assertTrue(final_path.is_file())
        self.assertEqual(final_path.resolve(), target_output.resolve())
        img = Image.open(final_path)
        self.assertEqual(img.size, (64, 64))
        # 确认四个角是透明的 (Alpha = 0)
        self.assertEqual(img.getpixel((0, 0))[3], 0)

        # 检查原图保护：*_raw.png 必须存在且未被覆盖！
        expected_raw = target_output.parent / f"{target_output.stem}_raw.png"
        self.assertTrue(expected_raw.is_file(), f"Expected raw image not found at {expected_raw}")
        raw_img = Image.open(expected_raw)
        self.assertEqual(raw_img.size, (100, 100))
        # 确认原图四角依然是原绿底 (Alpha = 255)
        self.assertEqual(raw_img.getpixel((0, 0))[3], 255)

    def test_e2e_retry_on_transient_failure(self):
        """测试 3：第一次调用瞬时无产物时，自动重试第 2 次并成功返回。"""
        mock_agy = self._create_mock_agy(behavior="retry_once")
        os.environ["AGY_IMG_AGY"] = str(mock_agy.resolve())
        os.environ["ANTIGRAVITY_API_KEY"] = "mock_key_for_testing"

        target_output = self.tmp_path / "dist" / "retry_test.png"
        custom_lock = self.tmp_path / "test_isolated_retry.lock"

        final_path = generate_image_asset(
            prompt="A mysterious tower",
            output=target_output,
            lock_path=custom_lock,
        )

        self.assertTrue(final_path.is_file())
        self.assertEqual(final_path.resolve(), target_output.resolve())


if __name__ == "__main__":
    unittest.main()
