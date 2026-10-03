#!/usr/bin/env python3
r"""install.py — agy-imagegen-skill 安装与环境配置脚本。

功能：
1. 检查并安装 Python 依赖（Pillow）
2. 将 bin/ 加入用户 PATH 环境变量（优先于或替代旧 C:\Software\agy-img）
3. 将 skills/agy-imagegen 软链至全局 ~/.gemini/config/skills/agy-imagegen
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

if sys.platform == "win32":
    import winreg

SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN_DIR = SKILL_ROOT / "bin"
SOURCE_SKILL_DIR = SKILL_ROOT / "skills" / "agy-imagegen"


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


def update_windows_user_path(add_bin: bool = True) -> bool:
    """更新 Windows 当前用户的 PATH 环境变量。"""
    if sys.platform != "win32":
        print(f"[!] 非 Windows 系统，请手动将 {BIN_DIR} 加入 PATH。")
        return True

    bin_str = str(BIN_DIR)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path, reg_type = "", winreg.REG_EXPAND_SZ

            parts = [p.strip() for p in current_path.split(";") if p.strip()]

            if add_bin:
                if bin_str not in parts:
                    # 插入到最前面以获得最高优先权
                    parts.insert(0, bin_str)
                    new_path = ";".join(parts)
                    winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
                    print(f"[+] 已将 {bin_str} 写入用户 PATH 环境变量。")
                else:
                    print(f"[+] 用户 PATH 中已存在 {bin_str}。")
            else:
                if bin_str in parts:
                    parts = [p for p in parts if p != bin_str]
                    new_path = ";".join(parts)
                    winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
                    print(f"[+] 已从用户 PATH 中移除 {bin_str}。")

        return True
    except Exception as e:
        print(f"[-] 更新用户 PATH 失败: {e}", file=sys.stderr)
        return False


def link_global_skill(unlink: bool = False) -> bool:
    """软链到 ~/.gemini/config/skills/agy-imagegen。"""
    home = pathlib.Path.home()
    target_dir = home / ".gemini" / "config" / "skills" / "agy-imagegen"

    if unlink:
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
            print(f"[+] 已移除软链: {target_dir}")
        elif target_dir.is_dir():
            import shutil
            shutil.rmtree(target_dir)
            print(f"[+] 已删除目录: {target_dir}")
        return True

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if target_dir.exists() or target_dir.is_symlink():
        if target_dir.is_symlink() and target_dir.resolve() == SOURCE_SKILL_DIR.resolve():
            print(f"[+] 软链已正确存在: {target_dir} -> {SOURCE_SKILL_DIR}")
            return True
        print(f"[!] 目标位置已存在 {target_dir}，正在更新软链...")
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
        else:
            import shutil
            shutil.rmtree(target_dir)

    try:
        # 在 Windows 上创建目录符号链接
        target_dir.symlink_to(SOURCE_SKILL_DIR, target_is_directory=True)
        print(f"[+] 成功创建全局技能软链: {target_dir} -> {SOURCE_SKILL_DIR}")
        return True
    except OSError as e:
        # 如果没有符号链接权限（非管理员未开启开发者模式），回退到复制模式
        print(f"[!] 创建软链失败 ({e})，回退为目录拷贝同步模式...")
        import shutil
        shutil.copytree(SOURCE_SKILL_DIR, target_dir)
        print(f"[+] 已复制技能文件至: {target_dir}")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="agy-imagegen-skill 安装与配置工具")
    parser.add_argument("-dev", action="store_true", help="开发者模式")
    parser.add_argument("-uninstall", action="store_true", help="卸载 PATH 和软链")
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

    if not link_global_skill(unlink=False):
        print("[-] 技能软链配置遇到问题。", file=sys.stderr)

    print("\n[+] 全部配置完成！")
    print("    - 命令行测试: 在新终端中执行 `agy-img --help`")
    print("    - 技能已注入: ~/.gemini/config/skills/agy-imagegen")
    print("==========================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
