# 变更日志 (Changelog)

本项目所有显著变更均记录于此。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，并遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] - 2026-10-03

### 重大变更 (Architecture & Breaking Changes)
- **跨语言逻辑收敛**：彻底废弃原先分散在 Bash（`bin/agy-img`）和 PowerShell（`bin/agy-img.ps1`）中的重复调度实现，全量下沉至 Python 核心深模块 [`scripts/engine.py`](scripts/engine.py)，外部脚本降级为 0 业务逻辑的跨平台薄适配器（Thin Adapters）。
- **确立单一事实源 (Single Source of Truth)**：消除 `skills/agy-imagegen/` 与仓库根目录的双重副本漂移，仓库根目录自包含完整的 Antigravity Skill 标准结构（`SKILL.md`, `scripts/`, `references/`, `resources/`, `examples/`）。记录归档 [ADR 0001](docs/adr/0001-unified-python-pipeline-engine.md)。

### 新增特性 (Added)
- **资产形态双轨决策支持**：
  - **轨道 A（Full-Frame）**：全幅插画、背景壁纸与场景原画，支持 7 种标准宽高比，禁止抠图；
  - **轨道 B（Chromakey）**：游戏精灵、角色立绘与 UI 控件，纯色底生成 + 色键去溢色 + 尺寸呼吸留白居中。
- **40x+ 高性能向量化色键**：基于 Pillow 矩阵运算实现色相差抠图与边缘去色溢（Despill），大幅降低大尺寸位图处理耗时。
- **草木主体洋红底避让**：原生支持洋红底（`--bg magenta` / `-k magenta`），解决绿色主体/史莱姆被绿幕算法误剔除的行业痛点。
- **原始素材保护机制**：开启色键处理时，自动留存未抠图原始底图为 `<name>_raw.<ext>`，避免直接覆写破坏原始素材。
- **标准 Python 打包**：支持通过 `pyproject.toml` 中的 `[project.scripts]` 安装全局 CLI 命令（`agy-img` 与 `chromakey`）。
- **多平台 CI 门禁矩阵**：新增 `.github/workflows/ci.yml`，在 Ubuntu、Windows、macOS 与 Python 3.10-3.12 矩阵下自动运行全量回归。
- **POSIX 安装脚本**：新增根目录 `install.sh`。

### 修复与优化 (Fixed & Improved)
- **子进程管道通信防死锁**：重构调度进程 I/O，使用底层线程聚合的 `proc.communicate()`，杜绝大模型输出 64KB+ 日志时子进程被操作系统缓冲区挂起。
- **参数优先级对齐**：纠正超时与锁等待参数优先级，严格保证“显式命令行参数 > 环境变量 > 缺省默认值”。
- **单例并发文件锁优化**：移除脆弱的僵尸进程 PID 嗅探逻辑，完全依赖内核级句柄锁（Windows `msvcrt` / POSIX `fcntl`）。
- **Windows UTF-8 编码修复**：显式重置控制台输出流编码为 UTF-8，彻底解决中文环境乱码。
- **测试套件规范化**：全量测试收敛为标准库 `unittest.TestCase`，彻底消除第三方 `pytest` 依赖。

---

## [0.1.0] - 2026-10-02

### 新增 (Added)
- 初始原型：提供基本的文生图调度脚本与绿幕抠图工具。
- 初版安装脚本 `install.ps1`。
