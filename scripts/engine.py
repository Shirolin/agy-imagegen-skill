#!/usr/bin/env python3
"""engine.py — agy-imagegen 统一生图与资产后处理深模块 (Pipeline Engine)。

作为本项目的核心深模块 (Deep Module)，封装：
1. 跨平台单实例并发互斥锁 (Cross-platform SingleInstanceLock)
2. agy 宿主定位与子进程调度，防管道死锁安全异步读取
3. 路径边界限制与参考图防逃逸验证
4. 图像魔数快速校验与扩展名自适应校准
5. 进程内直接衔接向量化色键抠图、去色溢与原图保护 (Keep-Raw)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 导入同级 chromakey 模块
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from chromakey import process_image


class EngineError(Exception):
    """Pipeline Engine 基础异常。"""
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class LockBusyError(EngineError):
    """并发锁等待超时异常。"""
    def __init__(self, message: str):
        super().__init__(message, exit_code=75)


class InvalidArgumentError(EngineError):
    """参数校验异常。"""
    def __init__(self, message: str):
        super().__init__(message, exit_code=64)


class SingleInstanceLock:
    """跨平台单实例互斥锁。操作系统保证进程退出时句柄与锁自动释放。"""

    def __init__(self, wait_seconds: int = 60, lock_path: str | pathlib.Path | None = None):
        self.wait_seconds = wait_seconds
        if lock_path:
            self.lock_path = pathlib.Path(lock_path)
        else:
            self.lock_path = pathlib.Path(tempfile.gettempdir()) / "agy-img.single.lock"
        self._file = None

    def acquire(self) -> None:
        start_time = time.monotonic()
        while time.monotonic() - start_time < self.wait_seconds:
            try:
                self._file = open(self.lock_path, "a+b")
                if sys.platform == "win32":
                    import msvcrt
                    self._file.seek(0)
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # 成功获取排他锁
                self._file.seek(0)
                self._file.truncate()
                lock_data = f"pid={os.getpid()} ts={time.time()}\n".encode("utf-8")
                self._file.write(lock_data)
                self._file.flush()
                return
            except (OSError, IOError):
                if self._file:
                    try:
                        self._file.close()
                    except OSError:
                        pass
                    self._file = None
                time.sleep(0.3)

        raise LockBusyError(
            f"error: agy-img busy (another instance holds the lock after {self.wait_seconds}s). "
            f"Set AGY_IMG_LOCK_WAIT to wait longer."
        )

    def release(self) -> None:
        if self._file:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self._file.seek(0)
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                self._file.close()
                self._file = None

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def get_image_kind(path: pathlib.Path) -> dict | None:
    """仅读取文件头前 16 字节判定图像魔数，避免大图读入内存。"""
    if not path.is_file():
        return None
    try:
        length = path.stat().st_size
        if length < 16:
            return None
        with open(path, "rb") as f:
            hdr = f.read(16)
        if len(hdr) < 12:
            return None

        # PNG: 89 50 4E 47
        if hdr.startswith(b"\x89PNG"):
            return {"ext": ".png", "len": length}
        # JPG: FF D8
        if hdr.startswith(b"\xff\xd8"):
            return {"ext": ".jpg", "len": length}
        # WEBP: RIFF....WEBP
        if hdr.startswith(b"RIFF") and hdr[8:12] == b"WEBP":
            return {"ext": ".webp", "len": length}
        return None
    except OSError:
        return None


def is_path_inside(target: pathlib.Path, parent: pathlib.Path) -> bool:
    """严格判断 target 是否位于 parent 目录内（绝对路径前缀匹配）。"""
    try:
        t_abs = target.resolve()
        p_abs = parent.resolve()
        return t_abs == p_abs or p_abs in t_abs.parents
    except (OSError, RuntimeError):
        return False


def find_image_path(text: str, work_dir: pathlib.Path) -> pathlib.Path | None:
    """从大模型响应中解析产物图片路径，并强校验其必须位于 work_dir 内，严防路径逃逸。"""
    if text:
        # 1. 优先匹配 IMAGE_PATH: <path>
        for line in text.splitlines():
            line_str = line.strip()
            if line_str.startswith("IMAGE_PATH:"):
                raw_path = line_str[len("IMAGE_PATH:"):].strip().strip('"').strip("'")
                cand_path = pathlib.Path(raw_path)
                if cand_path.is_file() and is_path_inside(cand_path, work_dir):
                    return cand_path

        # 2. 正则回退匹配图片路径（必须在 work_dir 内）
        pattern = r"(?i)([A-Za-z]:\\[^\s\"']+\.(?:png|jpe?g|webp)|/[^\s\"']+\.(?:png|jpe?g|webp))"
        for m in re.finditer(pattern, text):
            cand_path = pathlib.Path(m.group(1))
            if cand_path.is_file() and is_path_inside(cand_path, work_dir):
                return cand_path

    # 3. 如果模型没输出结构化标记，但实际在 work_dir 内生成了文件，抓取最新文件
    if work_dir.is_dir():
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in work_dir.rglob("*") if p.is_file() and p.suffix.lower() in valid_exts]
        if files:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return files[0]

    return None


def resolve_agy_executable() -> str:
    """定位本机 agy 可执行文件。"""
    env_agy = os.environ.get("AGY_IMG_AGY")
    if env_agy and pathlib.Path(env_agy).is_file():
        return env_agy

    which_agy = shutil.which("agy")
    if which_agy:
        return which_agy

    # Windows 本地应用路径回退
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            fallback = pathlib.Path(local_app) / "agy" / "bin" / "agy.exe"
            if fallback.is_file():
                return str(fallback)

    raise EngineError(
        "error: agy not installed (agy executable not on PATH). Install Antigravity CLI first.",
        exit_code=127,
    )


def check_agy_auth() -> None:
    """检查 agy 登录鉴权状态。"""
    if os.environ.get("ANTIGRAVITY_API_KEY"):
        return
    user_home = pathlib.Path.home()
    if (user_home / ".gemini" / "antigravity-cli").exists():
        return
    if (user_home / ".gemini" / "oauth_creds.json").exists():
        return
    raise EngineError(
        "error: agy not logged in. Run `agy` once interactively, or set ANTIGRAVITY_API_KEY.",
        exit_code=1,
    )


def resolve_output_path(requested: pathlib.Path, kind_ext: str) -> pathlib.Path:
    """根据真实图像魔数扩展名校准输出路径扩展名。"""
    cur_ext = requested.suffix.lower()
    want_ext = kind_ext.lower()
    if (want_ext == ".jpg" and cur_ext in {".jpg", ".jpeg"}) or (cur_ext == want_ext):
        return requested
    return requested.with_suffix(want_ext)


def invoke_agy_once(
    agy_path: str,
    model: str,
    timeout_sec: int,
    prompt_body: str,
    work_dir: pathlib.Path,
    extra_dirs: List[pathlib.Path],
) -> Tuple[bool, bool, int, str, pathlib.Path | None, dict | None, str]:
    """单次调用 agy 子进程调度出图，杜绝管道死锁。

    返回: (ok, recoverable, exit_code, response, src_path, image_kind, error_msg)
    """
    cmd = [
        agy_path,
        "--model", model,
        "--dangerously-skip-permissions",
        "--print-timeout", f"{timeout_sec}s",
        "--add-dir", str(work_dir.resolve()),
    ]
    seen_dirs = {str(work_dir.resolve())}
    for d in extra_dirs:
        d_str = str(d.resolve())
        if d_str not in seen_dirs:
            cmd.extend(["--add-dir", d_str])
            seen_dirs.add(d_str)

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work_dir),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        return False, False, 1, "", None, None, f"failed to start agy: {e}"

    try:
        stdout, stderr = proc.communicate(input=prompt_body, timeout=timeout_sec + 20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return False, True, 124, "", None, None, f"agy timed out after {timeout_sec}s"

    rc = proc.returncode
    src = find_image_path(stdout, work_dir)

    if not src or not src.is_file():
        is_recoverable = (rc == 0 or rc == 124)
        msg = f"agy failed (exit {rc}). {stderr.strip()}" if rc != 0 else (
            "could not parse image path from agy output (no valid image under work dir)."
        )
        return False, is_recoverable, (rc if rc != 0 else 2), stdout, None, None, msg

    kind = get_image_kind(src)
    if not kind:
        return False, True, 2, stdout, src, None, f"resolved path is not a valid image format ({src})."

    return True, False, 0, stdout, src, kind, ""


def generate_image_asset(
    prompt: str,
    output: str | pathlib.Path,
    refs: list[str | pathlib.Path] | None = None,
    ratio: str = "1:1",
    chromakey: str | None = None,
    canvas: int | None = None,
    name: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    lock_wait: int | None = None,
    keep_raw: bool = True,
    lock_path: str | pathlib.Path | None = None,
) -> pathlib.Path:
    """单一核心深模块接口 (Deep Interface)：完成生图、防逃逸、原图保护与向量化后处理规约全流程。"""
    # 1. 基础校验
    prompt = prompt.strip()
    if not prompt:
        raise InvalidArgumentError("error: prompt required.")

    valid_ratios = {"1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2"}
    if ratio not in valid_ratios:
        raise InvalidArgumentError(f"error: invalid --ratio '{ratio}' (use {'|'.join(sorted(valid_ratios))})")

    if chromakey and chromakey.lower() not in {"green", "magenta"}:
        raise InvalidArgumentError(f"error: invalid --chromakey '{chromakey}' (must be 'green' or 'magenta')")

    if canvas is not None and canvas <= 0:
        raise InvalidArgumentError(f"error: --canvas must be a positive integer, got '{canvas}'")

    out_path = pathlib.Path(output).resolve()
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_refs: List[pathlib.Path] = []
    if refs:
        for r in refs:
            p = pathlib.Path(r).resolve()
            if not p.is_file():
                raise InvalidArgumentError(f"error: --ref file not found: {p}")
            resolved_refs.append(p)

    # 优先级规则：显式参数 > 环境变量 > 默认值
    if model is not None:
        driver_model = model
    elif "AGY_IMG_MODEL" in os.environ:
        driver_model = os.environ["AGY_IMG_MODEL"]
    else:
        driver_model = "gemini-3.8-flash-low"

    if timeout is not None:
        timeout_sec = timeout
    elif "AGY_IMG_TIMEOUT" in os.environ:
        timeout_sec = int(os.environ["AGY_IMG_TIMEOUT"])
    else:
        timeout_sec = 180

    if lock_wait is not None:
        lock_wait_sec = lock_wait
    elif "AGY_IMG_LOCK_WAIT" in os.environ:
        lock_wait_sec = int(os.environ["AGY_IMG_LOCK_WAIT"])
    else:
        lock_wait_sec = 60

    agy_exe = resolve_agy_executable()
    check_agy_auth()

    extra_dirs = [out_dir]
    for r in resolved_refs:
        if r.parent not in extra_dirs:
            extra_dirs.append(r.parent)

    # 2. 单实例并发互斥加锁
    with SingleInstanceLock(wait_seconds=lock_wait_sec, lock_path=lock_path):
        name_clause = f' Save the image with base name "{name}".' if name else ""

        ref_block = ""
        if resolved_refs:
            ref_lines = [
                "Reference images (MUST pass these absolute paths as ImagePaths / reference inputs "
                "to generate_image for img2img or edit — do NOT only describe them in text):"
            ]
            for idx, rr in enumerate(resolved_refs, 1):
                ref_lines.append(f"{idx}. {rr.resolve()}")
            ref_lines.append(
                "When calling generate_image, include every listed path as image/reference inputs. "
                "Preserve subject identity and key visual traits from the references while applying the edit description below."
            )
            ref_block = "\n".join(ref_lines) + "\n\n"

        max_attempts = 2
        last_error = ""
        last_response = ""
        final_image: pathlib.Path | None = None

        # 3. 调度循环与瞬时容错重试
        for attempt in range(1, max_attempts + 1):
            work_dir = pathlib.Path(tempfile.mkdtemp(prefix="agy-img-"))
            try:
                mode_line = (
                    "Use your built-in generate_image tool (Nano Banana / Imagen) in image-to-image / edit mode with the reference ImagePaths below."
                    if resolved_refs else
                    "Use your built-in generate_image tool (Nano Banana / Imagen) to create an image. Do not describe the image in prose instead of generating it."
                )

                prompt_body = (
                    f"{mode_line}\n\n"
                    f"{ref_block}Description / edit instruction: {prompt}\n"
                    f"Aspect ratio: {ratio}.{name_clause}\n"
                    f"Write the output file under this absolute directory (create if needed): {work_dir.resolve()}\n\n"
                    "After generate_image succeeds, you MUST end your entire reply with exactly one line in this format (no quotes, no markdown, nothing after it):\n"
                    "IMAGE_PATH: <absolute path to the generated image file>\n\n"
                    "The IMAGE_PATH line is required for the calling wrapper."
                )

                if attempt > 1:
                    print(f"retry: recoverable failure on attempt 1 ({last_error}); retrying once...", file=sys.stderr)
                    time.sleep(2)

                ok, recoverable, code, response_txt, src_path, kind, err_msg = invoke_agy_once(
                    agy_path=agy_exe,
                    model=driver_model,
                    timeout_sec=timeout_sec,
                    prompt_body=prompt_body,
                    work_dir=work_dir,
                    extra_dirs=extra_dirs,
                )

                last_response = response_txt
                if ok and src_path and kind:
                    # 4. 成功获取图片，直接拷贝至目标路径并处理原图保护
                    if chromakey:
                        # 开启色键时：原图保存为 *_raw.<ext>，保证素材不被覆盖丢失
                        raw_stem = f"{out_path.stem}_raw" if keep_raw else f"{out_path.stem}_chroma_tmp"
                        raw_output = out_dir / f"{raw_stem}{kind['ext']}"
                        shutil.copy2(src_path, raw_output)

                        target_png = out_path.with_suffix(".png")
                        success = process_image(
                            src_path=raw_output,
                            dst_path=target_png,
                            bg_color=chromakey.lower(),
                            canvas_size=canvas,
                            padding_ratio=0.04,
                        )
                        if not success or not target_png.is_file():
                            raise EngineError(
                                f"error: chromakey post-processing failed for {raw_output.name}",
                                exit_code=1,
                            )
                        if not keep_raw and raw_output.is_file():
                            raw_output.unlink(missing_ok=True)
                        final_image = target_png
                    else:
                        # 全幅图像模式：根据真实魔数校准扩展名后直接落地
                        raw_output = resolve_output_path(out_path, kind["ext"])
                        shutil.copy2(src_path, raw_output)
                        final_image = raw_output
                    break

                last_error = err_msg
                if not recoverable or attempt >= max_attempts:
                    raise EngineError(f"error: {err_msg}", exit_code=code)
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

        if not final_image or not final_image.is_file():
            raise EngineError(f"error: {last_error}", exit_code=1)

        # 打印干净响应与最终产物路径
        clean_lines = [
            line for line in last_response.splitlines()
            if not line.strip().startswith("IMAGE_PATH:")
        ]
        clean_body = "\n".join(clean_lines).strip()
        if clean_body:
            print(clean_body)
        print(f"IMAGE_PATH: {final_image.resolve()}")
        return final_image


def main() -> int:
    parser = argparse.ArgumentParser(
        description="agy-img — headless image generation & chromakey standardized asset pipeline",
        add_help=True,
    )
    parser.add_argument("prompt", nargs="?", default="", help="Prompt / edit instruction")
    parser.add_argument("-o", "--output", required=False, help="Output image path")
    parser.add_argument("--ref", action="append", default=[], help="Reference image for img2img (repeatable)")
    parser.add_argument("--ratio", default="1:1", help="Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2)")
    parser.add_argument("--name", default=None, help="Base filename hint")
    parser.add_argument("-k", "--chromakey", choices=["green", "magenta"], default=None, help="Optional chromakey color")
    parser.add_argument("--canvas", type=int, default=None, help="Square canvas size (e.g. 64, 96, 128, 256)")
    parser.add_argument("--model", default=None, help="Driver model for agy")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout in seconds")
    parser.add_argument("--lock-wait", type=int, default=None, help="Seconds to wait for single-instance lock")
    parser.add_argument("--no-keep-raw", action="store_true", help="Do not keep the un-keyed raw image when using --chromakey")
    args = parser.parse_args()

    if not args.prompt or not args.output:
        parser.print_help()
        print("\nerror: both prompt and -o/--output are required.", file=sys.stderr)
        return 64

    try:
        generate_image_asset(
            prompt=args.prompt,
            output=args.output,
            refs=args.ref,
            ratio=args.ratio,
            chromakey=args.chromakey,
            canvas=args.canvas,
            name=args.name,
            model=args.model,
            timeout=args.timeout,
            lock_wait=args.lock_wait,
            keep_raw=not args.no_keep_raw,
        )
        return 0
    except EngineError as e:
        print(str(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:
        print(f"unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
