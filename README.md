# agy-imagegen-skill

> 面向 Google Antigravity / AI Agent 的无头生图与全流程色键资产规约工具链。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 核心特性

1. **双模无缝调度（Dual Mode）**：
   - 宿主具备原生生图能力时，优先使用内置 `generate_image`；
   - 外部终端、CI 或轻量子智能体环境自动回退至加固的 `agy-img` CLI。
2. **通用色键抠图与去溢色（Chromakey & Despill）**：
   - 支持绿底（`--bg green`）与洋红底（`--bg magenta`，专用于草木与绿色角色）；
   - 自动边缘去色溢（Despill），消除半透明光晕残留的绿边/紫边；
   - 自动包围盒裁剪，保留 4% 呼吸边距并按 Lanczos 算法规约到目标尺寸（`--canvas 64|96|128|256`）。
3. **加固调度底座（Robust CLI）**：
   - 解决单实例锁残留死锁问题（支持进程存活检测与孤儿锁自动回收）；
   - 优化垫图（`ImagePaths`）强约束传参，防止图生图静默退化；
   - 结构化返回契约（`IMAGE_PATH: <路径>`）。
4. **一键全局接入**：
   - 通过 `install.ps1` 一键将 CLI 加入用户 `PATH`，并将 Skill 软链至全局 `~/.gemini/config/skills/`。

---

## 目录结构

```text
agy-imagegen-skill/
├── bin/                              # 命令行入口
│   ├── agy-img.cmd                   # Windows CMD 包装器
│   └── agy-img.ps1                   # 核心 PowerShell 调度器
├── scripts/                          # 后处理与安装脚本
│   ├── chromakey.py                  # 通用色键抠图与尺寸规约
│   └── install.py                    # 安装配置逻辑
├── skills/                           # 标准 Agent 技能定义
│   └── agy-imagegen/
│       └── SKILL.md                  # 渐进式披露的 Skill 说明书
├── references/                       # 最佳实践与算法规范
│   ├── prompting.md                  # 纯色底与风格提示词指南
│   └── chromakey.md                  # 色相判定与去色溢算法详解
├── tests/                            # 自动化测试
│   └── test_chromakey.py             # 抠图准确性与去色溢测试
├── install.ps1                       # Windows 一键安装入口
├── pyproject.toml                    # 项目配置
└── README.md                         # 项目主文档
```

---

## 快速安装

在 PowerShell 中进入本项目目录，运行：

```powershell
.\install.ps1
```

该脚本将自动执行：
1. 校验 Python 3.10+ 环境并安装 `Pillow`；
2. 将 `bin/` 目录加入当前用户的系统 `PATH` 环境变量；
3. 将 `skills/agy-imagegen` 软链接至全局 `~/.gemini/config/skills/agy-imagegen`。

---

## 常用命令

### 1. 命令行生图（`agy-img`）
```bash
# 基础纯色底生图
agy-img "A cute fantasy chest, 16-bit pixel art, solid pure neon green background" -o chest.png --ratio 1:1

# 垫图生成（保持风格一致）
agy-img "Ice dragon boss with blue crystal wings" -o dragon_ice.png --ref ./dragon_raw.png --ratio 1:1

# 生图同时自动抠图为 256x256 透明 PNG
agy-img "A magic wand icon, solid pure magenta background" -o wand.png -k magenta --canvas 64
```

### 2. 色键抠图与资产规约（`chromakey.py`）
```bash
# 单图处理：绿底抠图并重采样到 256x256
python scripts/chromakey.py raw_boss.jpg -o boss.png --bg green --canvas 256

# 绿色植物/草木角色（用洋红底避免误伤）：
python scripts/chromakey.py raw_slime.jpg -o slime.png --bg magenta --canvas 96

# 批量规约整个目录：
python scripts/chromakey.py art-inbox/ -o raw-assets/ --bg green --canvas 128
```

---

## 运行测试

```bash
python tests/test_chromakey.py
```

---

## 许可证

[MIT License](LICENSE)
