# hitems3D-comfyUI

ComfyUI custom node package for [Hitem3D](https://www.hitem3d.ai/) Image-to-3D API. Quickly generate high-quality 3D models from images using Hitem3D AI services.

## ✨ Features

- **Image to 3D**: Generate 3D models from a single image or multi-view images. Supports hitem3dv1.5 and hitem3dv2.0 models.
- **Portrait/Scene to 3D**: Optimized 3D reconstruction for portraits and scenes. Supports scene-portraitv1.5 / v2.0 / v2.1 models.
- **Texture Regeneration**: Re-texture existing 3D models based on a reference image.

## 📦 Installation

### Method 1: Manual Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-repo/hitems3D-comfyUI.git
cd hitems3D-comfyUI
pip install -r requirements.txt
```

### Method 2: ComfyUI Manager

Search for `hitems3D` in ComfyUI Manager and install it.

### Method 3: 官网下载压缩包

1. 从 [官网](https://www.hitem3d.ai/) 或项目发布页下载 `hitems3D-comfyUI` 压缩包。
2. 解压到 ComfyUI 的 `custom_nodes` 目录下。
3. 在解压后的目录中执行依赖安装：

```bash
cd ComfyUI/custom_nodes/hitems3D-comfyUI
pip install -r requirements.txt
```

## ⚙️ Configuration

You need to configure the Hitem3D API keys (ak / sk) before use. You can get them by registering at [Hitem3D Website](https://www.hitem3d.ai/).

### Option 1: config.json (Recommended)

Edit `config.json` in the node directory:

```json
{
    "hitems3d_ak": "your_access_key",
    "hitems3d_sk": "your_secret_key"
}
```

### Option 2: Environment Variables

```bash
export hitems3d_ak=your_access_key
export hitems3d_sk=your_secret_key
```

> **Note:** If ak/sk are configured in `config.json` or environment variables, the input fields in the nodes can be left empty.

## 🧩 Node Descriptions

### hi3d:ImageTo3D

Generates a 3D model from a single image or multi-view images. Suitable for general objects.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ak` | STRING | Hitem3D API Access Key (leave empty if configured globally) |
| `sk` | STRING | Hitem3D API Secret Key (leave empty if configured globally) |
| `image` | IMAGE | Main front image (Required) |
| `image_back` | IMAGE | Back reference image (Optional, for multi-view) |
| `image_left` | IMAGE | Left reference image (Optional, for multi-view) |
| `image_right` | IMAGE | Right reference image (Optional, for multi-view) |
| `texture` | BOOLEAN | Whether to generate texture map (Default: True) |
| `model` | COMBO | Model version: `hitem3dv1.5` / `hitem3dv2.0` |
| `resolution` | COMBO | Generation resolution: `512` / `1024` / `1536` / `1536pro` |
| `face` | INT | Target poly count (Range: 100,000 ~ 2,000,000, Default: 500,000) |
| `format` | COMBO | Output format: `glb` / `stl` / `fbx` / `usdz` |

**Outputs:**
- `model_file` (STRING): Local path to the downloaded 3D model file.
- `model_task` (HITMES3D_MODEL_TASK): Task info, can be passed to TextrueNode.

---

### hi3d:PortraitImageTo3D

Similar to ImageTo3D, but optimized for portraits and scenes.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ak` | STRING | Hitem3D API Access Key (leave empty if configured globally) |
| `sk` | STRING | Hitem3D API Secret Key (leave empty if configured globally) |
| `image` | IMAGE | Main front image (Required) |
| `image_back` | IMAGE | Back reference image (Optional) |
| `image_left` | IMAGE | Left reference image (Optional) |
| `image_right` | IMAGE | Right reference image (Optional) |
| `texture` | BOOLEAN | Whether to generate texture map (Default: True) |
| `model` | COMBO | Model version: `scene-portraitv1.5` / `scene-portraitv2.0` / `scene-portraitv2.1` |
| `face` | INT | Target poly count (Range: 100,000 ~ 2,000,000, Default: 500,000) |
| `format` | COMBO | Output format: `glb` / `stl` / `fbx` / `usdz` |

> **Note:** Resolution is automatically decided by the model version: v1.5 uses `1536`, v2.0/v2.1 uses `1536pro`.

**Outputs:** Same as ImageTo3D

---

### hi3d:Textrue

Regenerates texture map for an existing 3D model based on a reference image.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ak` | STRING | Hitem3D API Access Key (leave empty if configured globally) |
| `sk` | STRING | Hitem3D API Secret Key (leave empty if configured globally) |
| `mesh_url` | STRING | Local path or network URL of the 3D model |
| `image` | IMAGE | Texture reference image (Required) |
| `model_task` | HITMES3D_MODEL_TASK | Optional upstream task info (from ImageTo3D output) |
| `model` | COMBO | Model version: `hitem3dv1.5` / `scene-portraitv1.5` |
| `format` | COMBO | Output format: `glb` / `stl` / `fbx` / `usdz` |

> **Tip:** Use either `model_task` OR `mesh_url`. If `model_task` is connected, it will automatically use that model's URL.

**Outputs:** Same as ImageTo3D

## 📄 License

MIT