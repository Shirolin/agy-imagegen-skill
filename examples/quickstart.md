# 快速上手与典型用例示例 (Quickstart Examples)

本指南提供 `agy-imagegen` 技能的典型实操代码与命令，涵盖文生图、图生图与透明资产规约全流程。

---

## 1. 轨道 A：通用全幅图像生成

### 场景 1：宽屏概念场景原画 (16:9)
```bash
agy-img "Cinematic fantasy castle on a floating island, waterfalls falling into clouds, golden hour sunset, matte concept art" \
  -o assets/bg_castle.png \
  --ratio 16:9
```

### 场景 2：手机端二次元风格竖屏壁纸 (9:16)
```bash
agy-img "Anime girl standing on a train platform under cherry blossom petals, makoto shinkai aesthetic, vibrant blue skies, lens flare" \
  -o assets/wallpaper_mobile.png \
  --ratio 9:16
```

### 场景 3：垫图图生图 / 风格迁移 (Image-to-Image)
基于一张黑白线稿草图或摄影照片，转换成吉卜力水彩画风：
```bash
agy-img "Transform this sketch into a lush Studio Ghibli style watercolor illustration, vibrant green meadows, sunny day" \
  -o assets/watercolor_scene.png \
  --ref ./drafts/sketch.png \
  --ratio 4:3
```

---

## 2. 轨道 B：专业透明资产生成与工程化规约

### 场景 1：非绿色常规角色 (绿底规约至 256x256)
生成机甲战狼，并在单条命令中直接完成绿底剔除、去溢色与自适应留白居中：
```bash
agy-img "A fierce cyber wolf boss, glowing red armor, mechanical joints, solid pure neon green background (#00FF00), no shadows on background" \
  -o raw-assets/boss_wolf.png \
  -k green \
  --canvas 256
```

### 场景 2：草木系/绿色主体精灵 (洋红底规约至 64x64)
针对绿色史莱姆，使用洋红底（Magenta）避免主体被绿幕剔除算法误伤：
```bash
agy-img "A cute glowing green slime monster with big kawaii eyes, pixel art style, solid pure vivid magenta background (#FF00FF), no shadows on background" \
  -o raw-assets/slime_green.png \
  -k magenta \
  --canvas 64
```

### 场景 3：离线批量规约
若设计收件箱 `art-inbox/` 中有批量纯色底原图，使用全局 `chromakey` 命令一键批量规约：
```bash
chromakey art-inbox/ -o raw-assets/sprites/ --bg green --canvas 128
```

---

## 3. Python 进程内直接调用 (Programmatic Usage)

在构建自定义流水线脚本或自动化任务时，可直接导入核心深模块：

```python
import pathlib
from scripts.engine import generate_image_asset

# 1. 生成全景插画
scene_path = generate_image_asset(
    prompt="A cozy coffee shop in rainy night, warm yellow interior lights, realistic photo",
    output="dist/coffeeshop.png",
    ratio="16:9"
)

# 2. 生成 128x128 透明道具图标
sword_path = generate_image_asset(
    prompt="A legendary flaming sword, golden hilt, solid pure neon green background",
    output="dist/sword.png",
    ratio="1:1",
    chromakey="green",
    canvas=128
)
print(f"Generated transparent asset: {sword_path}")
```
