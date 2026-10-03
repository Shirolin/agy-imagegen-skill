# agy-imagegen-skill

> 面向 Google Antigravity / AI Agent 的通用生图与专业色键资产规约双轨工具链。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 核心特性

本项目兼顾**通用创意生图**与**专业工程化透明资产规约**两大轨道：

1. **通用全幅生图（Full-Frame Track）**：
   - 适用于场景原画、概念插画、网站横幅（Banner/Hero）、宣传海报、手机/桌面壁纸、无缝平铺纹理；
   - 原生支持全套标准画幅比例：`1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `2:3`, `3:2`；
   - 支持多模态垫图图生图（`--ref <img>`），精准承接线稿上色、风格迁移与变体生成。
2. **专业透明资产规约（Chromakey Track）**：
   - 解决大模型无法原生生成干净透明 PNG 的行业痛点；
   - 支持绿底（`--bg green`）与洋红底（`--bg magenta`，专用于草木与绿色角色）；
   - 自动边缘去色溢（Despill），消除半透明光晕残留的绿边/紫边；
   - 基于 Pillow 纯算子的高性能向量化加速（比逐像素遍历提速 40x+）；
   - 自动包围盒裁剪，保留 4% 呼吸边距并按 Lanczos 算法规约到目标尺寸（`--canvas 64|96|128|256`）。
3. **加固调度底座（Robust CLI）**：
   - 宿主具备原生生图能力时优先使用内置 `generate_image`，终端与 CI 环境无缝回退至 `agy-img`；
   - 进程级管道防死锁与参数转义安全处理；
   - 解决单实例锁残留死锁问题（支持进程存活检测与孤儿锁自动回收）；
   - 强化路径边界检查，严防 `--ref` 输入文件被误判为生成产物；
   - 结构化返回契约（`IMAGE_PATH: <路径>`）。
4. **一键全局接入**：
   - 通过 `install.ps1` 一键将 CLI（`agy-img` 与 `chromakey`）加入用户 `PATH`，并将 Skill 软链至全局 `~/.gemini/config/skills/`（自包含完整参考规范）。

---

## 目录结构

```text
agy-imagegen-skill/
├── bin/                              # 命令行入口（已加入 PATH）
│   ├── agy-img                       # POSIX Shell 包装器 (Linux/macOS)
│   ├── agy-img.cmd                   # Windows CMD 包装器
│   ├── agy-img.ps1                   # PowerShell 兼容包装器
│   ├── chromakey                     # POSIX Shell 色键包装器 (Linux/macOS)
│   └── chromakey.cmd                 # Windows CMD 色键包装器
├── scripts/                          # 核心驱动与安装脚本
│   ├── engine.py                     # Pipeline Engine 核心深模块 (生图/锁/调度/规约)
│   ├── chromakey.py                  # 高性能向量化色键抠图与去色溢
│   └── install.py                    # 安装配置逻辑
├── skills/                           # 标准 Agent 技能定义
│   └── agy-imagegen/
│       ├── SKILL.md                  # 双轨决策与 SOP 说明书
│       └── references/               # 技能自包含技术规范
│           ├── prompting.md          # 全幅与纯色底提示词指南
│           └── chromakey.md          # 色相判定与去色溢算法详解
├── references/                       # 仓库级参考文档
│   ├── prompting.md          # 全幅与纯色底提示词指南
│   └── chromakey.md          # 色相判定与去色溢算法详解
├── tests/                            # 自动化测试
│   ├── test_engine.py                # 核心引擎单元测试 (锁/防逃逸/魔数/校验)
│   └── test_chromakey.py             # 抠图准确性、去色溢与向量化一致性测试
├── GLOSSARY.md                       # 领域术语与架构接缝定义表
├── install.ps1                       # Windows 一键安装入口
├── pyproject.toml                    # 项目配置与环境依赖
├── SKILL.md                          # 根目录镜像说明
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
2. 将 `bin/` 目录加入当前用户的系统 `PATH` 环境变量（立即广播生效）；
3. 将 `skills/agy-imagegen` 注入全局 `~/.gemini/config/skills/agy-imagegen`。

---

## 常用命令

### 1. 轨道 A：通用全幅生图（场景 / 插画 / 壁纸 / 垫图）
```bash
# 宽屏概念场景原画（16:9）
agy-img "Cinematic fantasy castle on a floating island, golden hour sunset, matte concept art" -o castle.png --ratio 16:9

# 竖屏移动端壁纸（9:16）
agy-img "Cyberpunk alleyway with neon signs reflecting in wet asphalt, volumetric rain" -o wallpaper.png --ratio 9:16

# 垫图风格迁移（传入草图或参考照，指定画风）
agy-img "Transform this sketch into a Studio Ghibli style watercolor illustration" -o scene.png --ref ./sketch.png --ratio 4:3
```

### 2. 轨道 B：独立透明资产规约（立绘 / 精灵 / UI 图标）
```bash
# 生图同时一步到位完成纯色底抠图与 256x256 规格化
agy-img "A fierce cyber wolf boss, glowing red armor, solid pure neon green background" -o boss.png -k green --canvas 256

# 绿色植物/草木角色（用洋红底避免误伤主体，规约至 64x64）：
agy-img "A cute green forest slime monster, solid pure vivid magenta background" -o slime.png -k magenta --canvas 64
```

### 3. 离线/批量色键抠图（`chromakey`）
安装后可在任何目录直接调用：
```bash
# 单图处理：绿底抠图并重采样到 256x256
chromakey raw_boss.jpg -o boss.png --bg green --canvas 256

# 批量规约整个目录（带重名消歧防覆盖）：
chromakey art-inbox/ -o raw-assets/ --bg green --canvas 128
```

---

## 运行测试

```bash
python tests/test_chromakey.py
pwsh -File .\tests\test_cli_helpers.ps1
```

---

## 许可证

[MIT License](LICENSE)
