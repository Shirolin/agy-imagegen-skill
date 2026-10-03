#!/usr/bin/env python3
r"""install.py — agy-imagegen-skill 安装与环境配置脚本。

功能：
1. 检查并安装 Python 依赖（Pillow）
2. 将 bin/ 加入用户 PATH 环境变量（清理旧失效路径，广播变更）
3. 将仓库根目录（单一事实源）软链或同步至全局 ~/.gemini/config/skills/agy-imagegen
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

if sys.platform == "win32":
    import winreg
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN_DIR = SKILL_ROOT / "bin"


def check_and_install_dependencies() -> bool:
    print("[*] 检查 Python 依赖 (Pillow)...")
    try:
        import PIL
        print(f"[+] Pillow 已就绪: 版本 {PIL.__version__}")
        return True
    except ImportError:
        print("[!] 未检测到 Pillow，正在自动安装...")
        cmd = [sys.executable, "-m", "pip", "install", "Pillow>=9.5.0"]
        res = subprocess.run(cmd)
        return res.returncode == 0


def broadcast_environment_change() -> None:
    """在 Windows 上广播 WM_SETTINGCHANGE 通知。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            3000,
            ctypes.byref(result),
        )
    except Exception:
        pass


def update_windows_user_path(add_bin: bool = True) -> bool:
    """更新 Windows 当前用户的 PATH 环境变量。"""
    if sys.platform != "win32":
        print(f"[!] 非 Windows 系统，请手动将 {BIN_DIR} 加入 PATH。")
        return True

    bin_str = str(BIN_DIR)
    bin_norm = os.path.normpath(bin_str).lower()
    legacy_paths = [r"c:\software\agy-img"]

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path, reg_type = "", winreg.REG_EXPAND_SZ

            raw_parts = [p.strip() for p in current_path.split(";") if p.strip()]
            parts: list[str] = []

            # 清理旧历史路径及现有本目录路径
            for p in raw_parts:
                norm_p = os.path.normpath(p).lower()
                if norm_p in legacy_paths or norm_p == bin_norm:
                    continue
                parts.append(p)

            if add_bin:
                parts.insert(0, bin_str)
                new_path = ";".join(parts)
                winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
                print(f"[+] 已将 {bin_str} 写入用户 PATH 环境变量（置顶生效）。")
            else:
                new_path = ";".join(parts)
                winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
                print(f"[+] 已从用户 PATH 中移除 {bin_str}。")

        broadcast_environment_change()
        return True
    except Exception as e:
        print(f"[-] 更新用户 PATH 失败: {e}", file=sys.stderr)
        return False


def copy_skill_bundle(src_root: pathlib.Path, target_dir: pathlib.Path) -> None:
    """复制纯净技能包至目标目录（排除测试和 VCS 文件）。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    # 核心清单文件
    skill_md = src_root / "SKILL.md"
    if skill_md.is_file():
        shutil.copy2(skill_md, target_dir / "SKILL.md")

    # 核心子目录
    for sub in ("scripts", "references", "resources", "examples"):
        src_sub = src_root / sub
        if not src_sub.is_dir():
            continue
        dst_sub = target_dir / sub
        dst_sub.mkdir(parents=True, exist_ok=True)
        for item in src_sub.iterdir():
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            dst_item = dst_sub / item.name
            if item.is_file():
                shutil.copy2(item, dst_item)
            elif item.is_dir():
                shutil.copytree(item, dst_item, dirs_exist_ok=True)


def link_global_skill(unlink: bool = False, prefer_symlink: bool = True, force_dev: bool = False) -> bool:
    """软链或复制本仓库技能至 ~/.gemini/config/skills/agy-imagegen。"""
    home = pathlib.Path.home()
    target_dir = home / ".gemini" / "config" / "skills" / "agy-imagegen"

    if unlink:
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
            print(f"[+] 已移除软链: {target_dir}")
        elif target_dir.is_dir():
            marker = target_dir / "SKILL.md"
            if marker.exists() and "agy-imagegen" in marker.read_text(encoding="utf-8", errors="ignore"):
                shutil.rmtree(target_dir)
                print(f"[+] 已安全删除技能目录: {target_dir}")
            else:
                print(f"[!] 警告: 目录 {target_dir} 缺少有效标记，跳过删除以防误伤。", file=sys.stderr)
        return True

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() or target_dir.is_symlink():
        if target_dir.is_symlink():
            try:
                if target_dir.resolve() == SKILL_ROOT.resolve():
                    print(f"[+] 软链已正确存在: {target_dir} -> {SKILL_ROOT}")
                    return True
            except Exception:
                pass
            target_dir.unlink()
        elif target_dir.is_dir():
            shutil.rmtree(target_dir)

    if prefer_symlink or force_dev:
        try:
            target_dir.symlink_to(SKILL_ROOT, target_is_directory=True)
            print(f"[+] 成功创建全局技能软链: {target_dir} -> {SKILL_ROOT}")
            return True
        except OSError as e:
            if force_dev:
                print(f"[-] 开发者模式要求软链但创建失败: {e}。请开启 Windows 开发者模式或以管理员身份运行。", file=sys.stderr)
                return False
            print(f"[!] 创建软链未获权限 ({e})，自动回退为纯净目录拷贝模式...")

    copy_skill_bundle(SKILL_ROOT, target_dir)
    print(f"[+] 已复制纯净技能文件至: {target_dir}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="agy-imagegen-skill 安装与配置工具")
    parser.add_argument("-dev", action="store_true", help="开发者模式：强行使用软链连接")
    parser.add_argument("-uninstall", action="store_true", help="卸载 PATH 和全局技能")
    args = parser.parse_args()

    if args.uninstall:
        print("[*] 正在卸载 agy-imagegen-skill...")
        update_windows_user_path(add_bin=False)
        link_global_skill(unlink=True)
        print("[+] 卸载完成。")
        return 0

    print("==========================================")
    print(" 安装 agy-imagegen-skill ")
    print("==========================================")

    if not check_and_install_dependencies():
        print("[-] 依赖安装失败，退出。", file=sys.stderr)
        return 1

    if not update_windows_user_path(add_bin=True):
        print("[-] PATH 配置遇到问题。", file=sys.stderr)

    if not link_global_skill(unlink=False, prefer_symlink=True, force_dev=args.dev):
        print("[-] 技能配置遇到问题。", file=sys.stderr)
        return 1

    print("\n[+] 全部配置完成！")
    print("    - 命令行已就绪: `agy-img --help` 或 `chromakey --help`")
    print("    - 技能已注入: ~/.gemini/config/skills/agy-imagegen")
    print("==========================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
