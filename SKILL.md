---
name: agy-imagegen
description: "生成、编辑或导入 AI 位图图像资产（角色立绘、Boss、敌人、UI 图标、特效、纹理或透明切片）。当任务需要生成新图、垫图生图、或纯色底色键抠图（Chromakey）并规约至目标尺寸时使用。"
---

# agy-imagegen

为项目生成高质量图像资产，并提供纯色底色键抠图、去色溢与尺寸规约全流程支持。

## 1. 模式决策（Dual Mode）

在开始生图前，根据当前执行宿主具备的工具能力选择执行路径：

| 模式 | 判定依据 | 调用方式 |
| :--- | :--- | :--- |
| **原生工具模式（推荐）** | 当前会话环境中存在 `generate_image` 原生工具 | 直接调用内置 `generate_image`，保存产物至临时目录或资产待收箱（如 `art-inbox/`） |
| **CLI 包装模式（回退）** | 环境无原生生图工具（外部 CLI、轻量子智能体） | 调用本机命令行 `agy-img` 调度出图 |

## 2. 纯色底与色彩决策（针对透明资产）

主流生成模型（如 Imagen / Nano Banana）通常默认生成不透明背景。若需要透明背景资产（游戏精灵、UI 图标等），采用**纯色底生成 + 色键抠图（Chromakey）**流程：

- **常规主体**（非绿色角色、武器、UI 等）：
  - 提示词显式要求：`isolated on a solid pure neon green background (#00FF00), no shadows on background`
  - 抠图参数：`--bg green`
- **草系 / 绿色系主体**（史莱姆、树木、绿发角色、植物）：
  - 提示词显式要求：`isolated on a solid pure bright magenta background (#FF00FF), no shadows on background`
  - 抠图参数：`--bg magenta`（避免绿色角色被绿键误伤）

## 3. 标准作业流（SOP）

### 步骤 1：出图与垫图（Generate）
- **CLI 模式调用示例**：
  ```bash
  # 普通文生图
  agy-img "A cute fantasy slime monster, pixel art style, thick outline, solid pure neon green background" -o art-inbox/slime_raw.png --ratio 1:1

  # 垫图保持风格一致（图生图）
  agy-img "Dark version of the wolf boss, glowing red eyes, solid pure neon green background" -o art-inbox/boss_dark.png --ref raw-assets/run/boss_wolf.png --ratio 1:1
  ```
- 若使用原生 `generate_image` 工具，传入提示词与 `ImagePaths`（对应垫图本地绝对路径）。

### 步骤 2：色键抠图与规格化（Chromakey & Resize）
使用项目通用抠图工具规约尺寸并消除色溢：
```bash
# 将原始绿底图抠图为 256x256、留 4% 呼吸边距的透明 PNG
python scripts/chromakey.py art-inbox/boss_dark.png -o raw-assets/boss_dark.png --bg green --canvas 256
```

### 步骤 3：资产入库与验证
1. 将最终透明 PNG 移入目标资源目录（如游戏图集源目录 `raw-assets/...`）。
2. 在渲染表/皮肤表（如 `skins/`）中完成别名绑定与锚点配置。
3. 运行项目既有测试/门禁验证渲染与逻辑完整性。

## 4. 边界与禁区
- **不要**在提示词中假设模型能原生生成 100% 干净透明的 PNG，必须显式指定纯色底并执行后处理。
- **不要**并行批量狂刷 `agy-img`（底层具备单实例并发锁，排队会阻塞时间）。
- **不要**将大尺寸原图直接拷入运行时包体，务必经过 `--canvas <N>` 规格化以控制资源体积。
