# 0001: 统一 Python 深模块架构与单一事实源设计 (Unified Python Deep Module and Single Source of Truth)

- **状态**: Accepted
- **日期**: 2026-10-03
- **上下文**:
  - 原实现存在跨语言碎片化痛点：Bash（`bin/agy-img`）与 PowerShell（`bin/agy-img.ps1`）分别维护了近乎平行的模型调度驱动、参数解析与路径正则过滤，不仅难以保证 Windows 与 POSIX 行为严格等价，而且跨进程并发单例锁实现脆弱。
  - 存在事实源漂移（Source Drift）隐患：仓库根目录与 `skills/agy-imagegen/` 子目录同时维护了两份代码（`engine.py`、`chromakey.py`）与两份文档（`SKILL.md`、`references/`），在迭代中出现了哈希不一致与相对路径断链风险。
  - 调度管道隐患：原先调用 `agy` 调度时未妥善处理 stdout 管道缓冲区（高输出堵塞死锁）、参数优先级被环境变量覆写、以及色键后处理覆盖原图导致原始素材损毁。

- **决策 (Decision)**:
  1. **收敛至 Python 单一深模块 (Deep Module)**:
     - 核心业务调度、并发互斥、沙箱边界校验、位图魔数核验、色相差色键及边缘去溢色全部下沉收敛至 `scripts/engine.py` 与 `scripts/chromakey.py`。
     - 外部适配器（`bin/agy-img`、`bin/chromakey`）降级为 0 业务逻辑的纯委托脚本（Thin Adapters），仅负责定位系统 Python 并透明转发命令行参数。
  2. **确立仓库根目录为自包含单一事实源 (Single Source of Truth)**:
     - 规范仓库根目录为标准 Antigravity Skill 结构：包含 `SKILL.md`、`scripts/`、`references/`、`resources/`、`examples/`。
     - 废弃并移除 `skills/agy-imagegen/` 冗余副本，消除双份代码与哈希漂移。
     - 全局安装工具（`install.py` / `install.ps1`）直接将本仓库根目录软链或打包安装至 `~/.gemini/config/skills/agy-imagegen`。
  3. **健全工程可靠性契约**:
     - **管道防死锁**: 调度驱动使用底层非阻塞/异步聚合的 `proc.communicate(input=..., timeout=...)`，杜绝 64KB+ 高输出下的子进程管道堵塞死锁。
     - **原图保护机制**: 执行色键抠图（`-k green|magenta`）时，自动将未经抠图的原始底图持久化为 `<name>_raw.<ext>`，避免直接覆写销毁原始资产。
     - **参数优先级对齐**: 严格遵循 `显式命令行参数 > 环境变量 > 默认缺省值`，修复超时时间与锁等待时间被环境覆盖的缺陷。
     - **单例互斥锁优化**: 依托操作系统内核级句柄锁机制（Windows `msvcrt.locking`，POSIX `fcntl.flock`），移除冗余的进程残留探测并支持自定义锁路径隔离测试。
     - **自动化全量测试**: 测试套件统一采用标准库 `unittest`，消除外部第三方测试运行器依赖，确保全平台免装环境一键发现并运行（`python -m unittest discover tests`）。

- **后果 (Consequences)**:
  - **正面影响**:
    - 根目录即技能，消除任何路径相对引用的歧义。
    - 跨平台行为 100% 幂等一致，终端输出统一 UTF-8 编码。
    - 调度与规约具备完整的鲁棒性与异常保护能力。
  - **权衡约束**:
    - CLI 适配器依赖宿主环境已安装 Python 3.10+ 及 Pillow。安装脚本提供自动检测与环境就绪引导。
