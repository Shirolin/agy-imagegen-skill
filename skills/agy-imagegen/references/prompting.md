# 图像生成提示词指南（Prompting Guide）

针对 Google Antigravity 内置生图（Nano Banana / Imagen）与 `agy-img` 调度的最佳实践。

---

## 1. 纯色底（Solid Background）强制锁定

生成游戏精灵（Sprites）、UI 图标、独立物件切片时，模型往往默认填充复杂自然背景或渐变光晕。为了保证后续色键抠图（Chromakey）成功率，必须在提示词中加入强约束：

### 绿底（针对一般主体）
```text
isolated on a solid pure neon green background (#00FF00), high contrast, flat lighting, clean sharp silhouette, no shadows on background, no green elements on the subject
```

### 洋红底（针对绿色系/植物主体）
```text
isolated on a solid pure vivid magenta background (#FF00FF), high contrast, flat lighting, clean sharp silhouette, no shadows on background, no magenta/pink elements on the subject
```

---

## 2. 游戏风格锁定提示词（Style Anchor）

为保持与 2D 像素/卡通游戏风格协调，推荐使用以下修饰短语：
- **厚描边（Thick Outline）**：`thick bold black outlines, cel shaded, clear silhouette`
- **像素/复古风**：`16-bit pixel art style, retro game sprite, crisp pixels`
- **高光与质感**：`chibi anime aesthetic, kawaii face features, chunky highlights, four-point star specular sparkles`

---

## 3. 垫图（Image-to-Image / Reference）使用技巧

通过 `--ref <path>` 传入参考图时，在提示词中明确说明变更点与保留点：

- **姿态与主体继承**：
  > "Preserve the overall character proportions, thick outlines, and eye shape from the reference image, but change the armor color to obsidian black with glowing red runes."
- **变体生成（同族换皮）**：
  > "Create an ice-element variant based on the reference creature. Replace forest green parts with translucent light-cyan ice crystals, keeping the exact same silhouette and camera angle."
