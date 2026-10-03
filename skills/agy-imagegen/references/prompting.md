# 图像生成提示词与场景指南（Prompting & Style Guide）

针对 Google Antigravity 内置生图（Nano Banana / Imagen）与 `agy-img` 调度的最佳实践。

---

## 1. 全幅场景、插画与背景（Full-Frame & Concept Art）

当生成不透明全景画面（游戏背景、概念原画、网站 Banner、海报、壁纸、纹理材质）时，**不要**添加纯色底提示词，使用完整的场景构图与光影修饰短语：

### 构图与镜头控制（Camera & Framing）
- **超广角全景**：`ultra-wide angle panoramic view, epic sense of scale, landscape vista`
- **等轴测 / 俯视角**：`isometric projection, bird's-eye view, tilt-shift miniature effect`
- **特写与景深**：`cinematic close-up, dramatic shallow depth of field, bokeh background`

### 常见画风锚点（Art Style Anchors）
- **概念原画 / 场景原画**：`concept art by industry masters, matte painting, highly detailed digital illustration, atmospheric lighting`
- **赛博朋克 / 科幻**：`cyberpunk metropolis, neon signs reflecting in wet pavement, volumetric fog, moody dusk`
- **二次元 / 动漫场景**：`makoto shinkai aesthetic, vibrant blue skies, fluffy dramatic clouds, nostalgic lighting`
- **写实 / 摄影质感**：`realistic photography, 35mm lens, natural daylight, ray tracing reflections, 8k resolution`
- **无缝纹理 / 材质贴图**：`seamless tileable texture of cracked cobblestone stone floor, top-down flat projection, diffuse map, perfectly repeatable edges`

---

## 2. 独立物件与透明切片（Isolated & Chromakey Assets）

当生成角色精灵（Sprite）、UI 图标、道具、武器等需要透明背景的资产时，模型原生通常填充复杂背景。为确保后续色键后处理（Chromakey）100% 干净，必须在提示词中强制锁定纯色底：

### 绿底约束（常规主体，非绿色角色/道具）
```text
isolated on a solid pure neon green background (#00FF00), high contrast, flat lighting, clean sharp silhouette, no shadows on background, no green elements on the subject
```

### 洋红底约束（草木系、绿色主体角色）
```text
isolated on a solid pure vivid magenta background (#FF00FF), high contrast, flat lighting, clean sharp silhouette, no shadows on background, no magenta/pink elements on the subject
```

### 游戏精灵风格修饰（Sprite Anchor）
- **厚描边与赛璐珞**：`thick bold black outlines, cel shaded, clear silhouette, vector graphics clean lines`
- **复古像素风**：`16-bit pixel art style, retro game sprite, crisp pixels, no antialiasing on outer edge`
- **UI 图标高光质感**：`mobile game UI icon, chunky golden metallic bevel, gloss reflection, vibrant gems`

---

## 3. 垫图（Image-to-Image / Reference）使用技巧

通过 `--ref <path>` 传入参考图时，在提示词中明确说明**保留点**与**变更点**：

- **风格迁移（保持结构，改变画风）**：
  > "Preserve the building shapes, perspective, and composition from the reference image, but transform the entire scene into an anime watercolor painting during golden hour sunset."
- **变体换皮（同族角色/怪物换属性）**：
  > "Create an ice-element variant based on the reference creature. Replace forest green fur with translucent light-cyan frost crystals, keeping the exact same silhouette and camera angle."
- **草图线稿上色**：
  > "Render this sketch into a fully colored high-fantasy digital painting with dramatic rim lighting and polished metal textures."
