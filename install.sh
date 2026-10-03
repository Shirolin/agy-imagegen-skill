#!/usr/bin/env sh
# install.sh — agy-imagegen-skill POSIX installer (Linux & macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$SCRIPT_DIR"
BIN_DIR="$SKILL_ROOT/bin"
INSTALL_PY="$SKILL_ROOT/scripts/install.py"

echo "=========================================="
echo " Installing agy-imagegen-skill (POSIX) "
echo "=========================================="

# 1. 查找合规 Python 解释器
PYTHON_CMD=""
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
            PYTHON_CMD="$cand"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "[-] Error: Python 3.10+ is required but not found on PATH." >&2
    exit 1
fi

echo "[+] Python 就绪: $($PYTHON_CMD --version)"

# 2. 调度 install.py 完成依赖校验与技能软链
"$PYTHON_CMD" "$INSTALL_PY" "$@"

# 3. 提供 PATH 环境变量配置提示
CURRENT_SHELL="$(basename "${SHELL:-sh}")"
RC_FILE=""
case "$CURRENT_SHELL" in
    zsh)  RC_FILE="$HOME/.zshrc" ;;
    bash) RC_FILE="$HOME/.bashrc" ;;
    *)    RC_FILE="$HOME/.profile" ;;
esac

if ! echo "$PATH" | tr ':' '\n' | grep -Fxq "$BIN_DIR"; then
    echo ""
    echo "[!] 提示: 为了在全局直接调用 \`agy-img\` 与 \`chromakey\`，请将 bin/ 加入 PATH："
    echo "    export PATH=\"$BIN_DIR:\$PATH\""
    if [ -f "$RC_FILE" ]; then
        echo "    可执行: echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> $RC_FILE"
    fi
fi

echo "=========================================="
