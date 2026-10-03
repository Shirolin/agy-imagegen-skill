# 领域模型术语表 (Domain Glossary)

本文档记录本项目在领域与架构上的核心实体与接缝命名规范，避免术语漂移。

---

## 核心领域概念 (Core Domain Concepts)

### 1. 资产形态 (Asset Form)
- **Full-Frame Asset (全幅资产)**: 填满画幅、包含完整背景与光影的图像（如场景原画、概念插画、宣传海报、全景壁纸、平铺纹理贴图）。生成时不应施加纯色底，严禁执行色键剔除。
- **Isolated Asset (透明切片资产)**: 需将主体与背景分离、拥有透明通道的游戏精灵（Sprite）、角色立绘、Boss、道具图标或 UI 控件。必须在生成时锁定纯色底，并经过色键后处理与居中呼吸留白规约。

### 2. 管线与模块 (Pipeline & Deep Modules)
- **Pipeline Engine (调度与后处理深模块)**: 本系统的核心深模块（Deep Module）。对外仅提供单一生图与规约接口，内部完全封装并发锁、宿主驱动子进程管理、路径边界限定、魔数校验与色键去色溢处理。
- **Chromakey (色键抠图)**: 基于色相差判定算法（Greenness 与 Magentaness）将纯色背景分离为 Alpha 蒙版的技术。
- **Despill (去色溢)**: 消除半透明边缘由于光栅化采样渗入的背景色（去绿边/去紫边）的颜色重构算法。
- **Standardize / Canvas (尺寸规约)**: 基于真实不透明像素的紧凑包围盒（Bbox）裁剪，并在保持原始纵横比前提下缩放至预设画布尺寸（如 64, 96, 128, 256），四周保留预设呼吸边距（Padding）的工程化处理。

### 3. 接缝与适配器 (Seams & Adapters)
- **CLI Adapter (命令行适配器)**: 位于系统最外层接缝（`bin/agy-img`、`bin/chromakey`），仅负责将终端命令行参数映射为 Pipeline Engine 接口参数，不承担业务实现。
- **ImageGenDriver (生图驱动契约接缝)**: 位于 Pipeline Engine 内部的核心架构接缝（Seam）。定义从抽象提示词、参考图到本地位图生成的调用契约，将底层宿主通信协议与高层资产管线完全解耦。
- **AgySubprocessDriver (CLI 子进程驱动适配器)**: 默认生产驱动适配器（Adapter）。封装子进程 `Popen` 调度、64KB+ 异步防死锁通信、魔数核验与瞬时重试状态机。
- **MockDriver (内存模拟驱动适配器)**: 供单元测试与离线隔离环境使用的内存驱动。零磁盘与子进程 I/O 开销，实现毫秒级快速测试与精准故障注入。
- **Driver Model (驱动调度模型)**: 负责在外部环境调用 `agy` 宿主执行生图任务的代理模型（默认为 `gemini-3.8-flash-low`），仅作为调度驱动，最终绘制由宿主原生的 `generate_image`（Imagen 3 / Nano Banana）承接。
