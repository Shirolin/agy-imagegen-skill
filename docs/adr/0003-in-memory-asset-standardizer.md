# 0003: 提炼纯内存资产规约深模块与消除控制台副作用 (In-Memory Asset Standardizer Deep Module)

- **状态**: Accepted
- **日期**: 2026-10-03
- **上下文**:
  - 在既有实现中，[`scripts/chromakey.py`](../../scripts/chromakey.py) 的 `process_image` 充当了混合体：它同时承揽了 PIL 图像文件的读取与保存、目录自动创建、色键与去溢色计算、Bbox 裁剪自适应居中规约，并在每次调用时直接向 `sys.stdout` 和 `sys.stderr` 执行 `print(...)` 控制台输出。
  - 这种混合设计引发了数个架构摩擦：
    1. **缺乏局部性与测试摩擦**：单元测试为了验证色键与规约效果，必须在磁盘建立临时目录并进行文件往返；同时为了单元测试细碎算子，代码公开暴露了 4 个标量函数（`calculate_alpha_green`、`despill_green` 等），而生产流水线实际只通过 LUT 查表向量化执行，导致测试并未直接针对真实运行接口（违背 *"the interface is the test surface"*）。
    2. **控制台输出污染**：当 `Pipeline Engine`（`engine.py`）调用 `process_image` 时，后者的 `print` 直接混入引擎 stdout 流，干扰了外层自动化调用的确定性契约。
    3. **错误处理模糊**：`process_image` 捕获异常后仅打印文本并返回 `False`，导致上层调用方丢失了根因上下文（如底色与参数不匹配导致全透明、或尺寸无效）。

- **决策 (Decision)**:
  1. **提炼纯内存深模块 `standardize_isolated_asset`**:
     - 核心图像处理接口接受 `PIL.Image.Image` 并返回新的 `PIL.Image.Image`。
     - 内部完全封装双通道色相差计算、LUT 查表生成、去溢色融合、Bbox 紧凑裁剪与画幅等比呼吸留白居中。
     - 零磁盘 I/O，零控制台 `print` 输出，实现纯函数式的计算深度与确定性。
  2. **确立显式领域异常契约**:
     - 定义 `StandardizationError(ValueError)` 及其子类 `EmptyAlphaError`。当抠图后全透明（底色与 `--bg` 不匹配）或参数非法时显式抛出异常，不再静默吞错并返回 `False`。
  3. **标量微算子私有化与测试演进**:
     - 将原本仅为单测暴露的 4 个标量函数收敛为模块私有实现（`_calculate_alpha_*`, `_despill_*`），仅作为构建 256 项 LUT 的底层数学工具。
     - 测试套件直接面向 `standardize_isolated_asset` 内存接口，使用合成位图验证透明度、边缘去色溢与尺寸规约，消除磁盘开销与伪造夹具。
  4. **薄磁盘与 CLI 适配器退化**:
     - `process_image(src_path, dst_path, ...)` 退化为轻量磁盘适配器，仅负责文件读写与向后兼容；默认 `verbose=False` 保持纯净静默。
     - 控制台打印与批处理循环统一收敛至 CLI 适配器入口（`main()`）。

- **后果 (Consequences)**:
  - **正面影响**:
    - **Locality**: 资产规约的几何运算与色彩变换完全收敛在纯内存深模块中。
    - **Depth**: 外层调用者仅需面对一个极简高层内存接口，即可完成完整的游戏资产/精灵规约。
    - **Testability**: 测试耗时极大缩短，无需在磁盘频繁写临时文件。
  - **向后兼容**:
    - `chromakey` 命令行工具及 `scripts/engine.py` 调用契约 100% 保持向后兼容。
