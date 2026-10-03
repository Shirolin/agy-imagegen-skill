# 0002: 解耦驱动调度接缝与引入可插拔 ImageGenDriver (Pluggable ImageGenDriver Seam)

- **状态**: Accepted
- **日期**: 2026-10-03
- **上下文**:
  - 在 ADR 0001 中，我们将跨语言实现收敛至 Python 单一深模块 [`scripts/engine.py`](scripts/engine.py)。
  - 然而在进一步的代码库设计审查中发现：`generate_image_asset` 内部仍与外部 `agy` CLI 子进程、参数构造、子进程管道通信、stdout 正则提取以及自动重试状态机紧密耦合在一起。
  - 这导致了两个主要架构摩擦：
    1. **测试成本高且脆弱**：为了验证调度重试与管道防死锁，单元测试（`tests/test_mock_agy.py`）必须在磁盘上动态生成模拟的假批处理/Python 脚本来扮演 `agy.exe`，跑完全套测试需 10 秒以上，且依赖临时目录环境。
    2. **驱动缺乏替代性**：如果环境具备 Python 原生 API（如在 Agent 会话进程内或使用直接 SDK），引擎无法直接复用，依然只能开销额外的外部子进程。

- **决策 (Decision)**:
  1. **确立 `ImageGenDriver` 契约接缝 (Seam)**:
     - 在 `scripts/engine.py` 中定义抽象协议 `ImageGenDriver`：
       ```python
       class ImageGenDriver(Protocol):
           def dispatch(
               self,
               prompt: str,
               work_dir: pathlib.Path,
               refs: list[pathlib.Path],
               ratio: str = "1:1",
               name: str | None = None,
               model: str | None = None,
               timeout: int = 180,
           ) -> Tuple[pathlib.Path, dict]:
               """执行生图调度并返回落地在 work_dir 内的原始图像路径及魔数信息。"""
       ```
  2. **将子进程调度与重试内聚至 `AgySubprocessDriver`**:
     - 所有的子进程 Popen、超时 kill、64KB+ 非阻塞管道通信、stdout 正则解析以及**失败自动重试 1 次**逻辑，全部封装在 `AgySubprocessDriver` 内部。
     - `Pipeline Engine`（`generate_image_asset`）彻底摆脱子进程 I/O 细节，仅作为单例互斥锁、驱动调度、原图素材保护（`*_raw`）与色键规约的高层编排者。
  3. **提供内存级 `MockDriver` 赋能测试**:
     - 提供纯内存实现的 `MockDriver`，支持无外部依赖注入预设位图或模拟故障，将测试耗时缩减至毫秒级。
     - `generate_image_asset(..., driver: ImageGenDriver | None = None)` 支持依赖注入；默认缺省为生产级 `AgySubprocessDriver`。

- **后果 (Consequences)**:
  - **正面影响**:
    - 接口与测试表面完美对齐（"The interface is the test surface"）。
    - 核心业务编排更加清晰，深度显著增加。
    - 单元测试无需在磁盘生成复杂的批处理伪造文件，测试稳定性与速度大幅提升。
    - 为未来直接接入 Python 原生 SDK 或其他 Driver 提供了标准扩展点。
  - **向后兼容**:
    - CLI 命令行入口（`agy-img`）行为与参数 100% 保持一致，无任何破坏性变更。
