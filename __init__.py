from __future__ import annotations

import os
import json
import torch
from PIL import Image
from typing_extensions import override
import folder_paths
from folder_paths import get_output_directory, get_input_directory
from comfy_api.latest import ComfyExtension, io

from .api.utils import Hitem3dAPI
from comfy_api_nodes.util import (
    download_url_to_file_3d,
)

__version__ = "1.0.5"

hitem3d_ak = os.environ.get("hitem3d_ak")
hitem3d_sk = os.environ.get("hitem3d_sk")

if not hitem3d_ak or not hitem3d_sk:
    p = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(p, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
            if not hitem3d_ak:
                hitem3d_ak = config.get("hitem3d_ak")
            if not hitem3d_sk:
                hitem3d_sk = config.get("hitem3d_sk")

# ── 常量 ──────────────────────────────────────────────────────────────

IMAGE_TO_3D_SCENE_MODELS = {
    "general": ["hitem3dv1.5", "hitem3dv2.0"],
    "portrait": ["scene-portraitv1.5", "scene-portraitv2.0", "scene-portraitv2.1"],
}

IMAGE_TO_3D_MODEL_RESOLUTIONS = {
    "hitem3dv1.5": ["512", "1024", "1536", "1536pro"],
    "hitem3dv2.0": ["1536", "1536pro"],
    "scene-portraitv1.5": ["1536"],
    "scene-portraitv2.0": ["1536pro"],
    "scene-portraitv2.1": ["1536pro"],
}

ALL_IMAGE_TO_3D_MODELS = [
    "hitem3dv1.5",
    "hitem3dv2.0",
    "scene-portraitv1.5",
    "scene-portraitv2.0",
    "scene-portraitv2.1",
]

ALL_IMAGE_TO_3D_RESOLUTIONS = ["512", "1024", "1536", "1536pro"]



ALL_FORMATS = ["glb", "stl", "fbx", "usdz"]

Hitem3DModelTask = io.Custom("HITEM3D_MODEL_TASK")

# ── 工具函数 ───────────────────────────────────────────────────────────


def getHitem3dAPI(ak: str, sk: str):
    ak = hitem3d_ak if hitem3d_ak else ak
    sk = hitem3d_sk if hitem3d_sk else sk
    if not ak:
        raise RuntimeError("ak is required")
    if not sk:
        raise RuntimeError("sk is required")
    return Hitem3dAPI(ak, sk), ak, sk


def get_default_model_for_scene(scene):
    return IMAGE_TO_3D_SCENE_MODELS[scene][0]


def infer_scene_from_model(model):
    for scene, models in IMAGE_TO_3D_SCENE_MODELS.items():
        if model in models:
            return scene
    return None


def validate_image_to_3d_options(scene, model, resolution):
    allowed_models = IMAGE_TO_3D_SCENE_MODELS.get(scene)
    if allowed_models is None:
        valid_scenes = ", ".join(IMAGE_TO_3D_SCENE_MODELS.keys())
        raise RuntimeError(f"Invalid scene '{scene}'. Valid scenes: {valid_scenes}")

    if model not in allowed_models:
        allowed_models_text = ", ".join(allowed_models)
        raise RuntimeError(
            f"Model '{model}' is not available for scene '{scene}'. "
            f"Allowed models: {allowed_models_text}"
        )

    allowed_resolutions = IMAGE_TO_3D_MODEL_RESOLUTIONS[model]
    if resolution not in allowed_resolutions:
        allowed_resolutions_text = ", ".join(allowed_resolutions)
        raise RuntimeError(
            f"Resolution '{resolution}' is not available for model '{model}'. "
            f"Allowed resolutions: {allowed_resolutions_text}"
        )




def save_tensor(image_tensor, filename):
    if image_tensor.dim() > 3:
        image_tensor = image_tensor[0]
    if image_tensor.dtype == torch.float32:
        image_tensor = (image_tensor * 255).byte()
    if image_tensor.dim() == 2:
        image_tensor = image_tensor.unsqueeze(0)
    if image_tensor.dim() == 3 and image_tensor.size(0) == 3:
        image_tensor = image_tensor.permute(1, 2, 0)
    if image_tensor.is_cuda:
        image_tensor = image_tensor.cpu()
    image_np = image_tensor.numpy()
    image_pil = Image.fromarray(image_np)
    if image_np.shape[2] == 4:
        name = filename + ".png"
        image_pil.save(name, "PNG")
    else:
        name = filename + ".jpg"
        image_pil.save(name, "JPEG")
    return name


def toImagePath(image, filename):
    if image is None:
        return None
    if not isinstance(image, (str, bytes, os.PathLike)):
        return save_tensor(image, os.path.join(get_input_directory(), filename))
    return image


def build_multi_view_payload(image_path, image_back=None, image_left=None, image_right=None):
    multi_images = [image_path]
    image_dict = {
        "image_back": image_back,
        "image_left": image_left,
        "image_right": image_right,
    }
    multi_images_bit = "1"
    for image_name in ["image_back", "image_left", "image_right"]:
        img = image_dict[image_name]
        if img is not None:
            image_filename = toImagePath(img, image_name)
            multi_images.append(image_filename)
            multi_images_bit += "1"
        else:
            multi_images_bit += "0"
            multi_images.append(None)
    return multi_images, multi_images_bit


async def run_image_to_3d_task(
    ak, sk, texture, scene,
    image=None, image_back=None, image_left=None, image_right=None,
    model=None, face=None, resolution=None,
):
    if image is None:
        raise RuntimeError("image is required")

    if not scene:
        scene = infer_scene_from_model(model) or "general"
    if not model:
        model = get_default_model_for_scene(scene)
    if not resolution:
        resolution = IMAGE_TO_3D_MODEL_RESOLUTIONS[model][0]

    validate_image_to_3d_options(scene, model, resolution)
    request_type = 3 if texture else 1
    image_path = toImagePath(image, "image")
    api, ak, sk = getHitem3dAPI(ak, sk)

    if image_back is None and image_left is None and image_right is None:
        result = await api.image_to_3d(
            image_path, request_type, face, model, resolution
        )
    else:
        multi_images, multi_images_bit = build_multi_view_payload(
            image_path, image_back=image_back, image_left=image_left, image_right=image_right
        )
        result = await api.multi_view_to_3d(
            multi_images, multi_images_bit, request_type, face, model, resolution
        )

    if result["status"] != "success":
        raise RuntimeError(f"Failed to generate mesh: {result['message']}")
    task_id = result["task_id"]
    model_url = result["model_url"]
    glb = await download_url_to_file_3d(model_url, "glb", task_id=task_id)

    return glb, {"task_id": task_id, "model_url": model_url, "ak": ak, "sk": sk}


# ── 节点定义 ───────────────────────────────────────────────────────────

class ImageTo3DNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ImageTo3DNode",
            display_name="hitem3d:ImageTo3D",
            category="Hitem3D",
            description=(
                "Generates a 3D model from a single or multi-view image. "
                "Use `scene` to switch between general object models and portrait/scene models. "
                "Model and resolution options are linked together in the node UI."
            ),
            inputs=[
                io.String.Input(
                    "ak", default="",
                    tooltip="Hitem3D API Access Key. Leave empty if configured in config.json or environment variables.",
                ),
                io.String.Input(
                    "sk", default="",
                    tooltip="Hitem3D API Secret Key. Leave empty if configured in config.json or environment variables.",
                ),
                io.Image.Input(
                    "image", optional=True,
                    tooltip="Main front image (Required) for 3D model generation.",
                ),
                io.Image.Input(
                    "image_back", optional=True,
                    tooltip="Back reference image (Optional) for multi-view 3D reconstruction.",
                ),
                io.Image.Input(
                    "image_left", optional=True,
                    tooltip="Left reference image (Optional) for multi-view 3D reconstruction.",
                ),
                io.Image.Input(
                    "image_right", optional=True,
                    tooltip="Right reference image (Optional) for multi-view 3D reconstruction.",
                ),
                io.Boolean.Input(
                    "texture", default=False, optional=True,
                    tooltip="Whether to generate textures. If enabled, the model will include vertex colors/textures.",
                ),
                io.Combo.Input(
                    "scene", options=["general", "portrait"], default="general", optional=True,
                    tooltip="Scene preset. `general` is for common objects, `portrait` is for portrait/scene generation.",
                ),
                io.Combo.Input(
                    "model", options=ALL_IMAGE_TO_3D_MODELS, default="hitem3dv1.5", optional=True,
                    tooltip="3D generation model version. The node UI filters valid versions according to the selected scene.",
                ),
                io.Combo.Input(
                    "resolution", options=ALL_IMAGE_TO_3D_RESOLUTIONS, default="1024", optional=True,
                    tooltip="Generation resolution. The node UI filters valid resolutions according to the selected model.",
                ),
                io.Int.Input(
                    "face", min=100000, max=2000000, default=500000, optional=True,
                    tooltip="Output poly count. Higher count means finer detail but larger file size.",
                ),
            ],
            outputs=[
                io.File3DGLB.Output(
                    display_name="GLB",
                ),
                Hitem3DModelTask.Output(
                    display_name="model_task",
                    tooltip="Task information to be passed to the Texture node for re-texturing",
                ),
            ],
        )

    @classmethod
    async def execute(
        cls, ak, sk,
        image=None, image_back=None, image_left=None, image_right=None,
        texture=False, scene="general", model=None, resolution=None,
        face=500000,
    ):
        glb, task_info = await run_image_to_3d_task(
            ak, sk, texture, scene,
            image=image, image_back=image_back,
            image_left=image_left, image_right=image_right,
            model=model, face=face, resolution=resolution,
        )
        return io.NodeOutput(glb, task_info)


class TextureNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TextureNode",
            display_name="hitem3d:Texture",
            category="Hitem3D",
            description=(
                "Regenerates texture maps for existing 3D models. "
                "Provide a reference image and the original model (via path/URL or upstream node) "
                "to generate new textures."
            ),
            inputs=[
                io.String.Input(
                    "ak", default="",
                    tooltip="Hitem3D API Access Key. Leave empty if configured in config.json or environment variables.",
                ),
                io.String.Input(
                    "sk", default="",
                    tooltip="Hitem3D API Secret Key. Leave empty if configured in config.json or environment variables.",
                ),
                io.MultiType.Input(
                    "GLB",
                    types=[io.File3DGLB, io.File3DAny],
                    optional=True,
                    tooltip="Input 3D model in GLB format. Either this or model_task is required.",
                ),
                io.Image.Input(
                    "image", optional=True,
                    tooltip="Texture reference image (Required). The model will generate a new texture map based on this image.",
                ),
                Hitem3DModelTask.Input(
                    "model_task", optional=True,
                    tooltip="Task output from ImageTo3D nodes. Automatically uses that model's URL if connected.",
                ),
                io.Combo.Input(
                    "model", options=["hitem3dv1.5", "scene-portraitv1.5"],
                    default="hitem3dv1.5", optional=True,
                    tooltip="Model version used for texture generation.",
                ),

            ],
            outputs=[
                io.File3DGLB.Output(
                    display_name="GLB",
                ),
                Hitem3DModelTask.Output(
                    display_name="model_task",
                    tooltip="Task information to be passed to subsequent nodes",
                ),
            ],
        )

    @classmethod
    async def execute(
        cls, ak, sk,
        GLB=None, image=None, model_task=None, model=None,
    ):
        if image is None:
            raise RuntimeError("image is required")

        if model_task is not None:
            if not ak and "ak" in model_task:
                ak = model_task["ak"]
            if not sk and "sk" in model_task:
                sk = model_task["sk"]

        api, ak, sk = getHitem3dAPI(ak, sk)

        if model_task is not None:
            mesh_url = model_task["model_url"]
        elif GLB is not None:
            if GLB.is_disk_backed:
                mesh_path = GLB.get_source()
            else:
                tmp_path = os.path.join(get_input_directory(), f"_tmp_texture_input.{GLB.format or 'glb'}")
                GLB.save_to(tmp_path)
                mesh_path = tmp_path
            mesh_url = await api.upload_file(mesh_path)
        else:
            raise RuntimeError("GLB or model_task is required")
        image_path = toImagePath(image, "image")
        result = await api.texture(image_path, mesh_url, model)

        if result["status"] != "success":
            raise RuntimeError(f"Failed to generate mesh: {result['message']}")

        task_id = result["task_id"]
        model_url = result["model_url"]
        glb = await download_url_to_file_3d(model_url, "glb", task_id=task_id)
        return io.NodeOutput(
            glb,
            {"task_id": task_id, "model_url": model_url, "ak": ak, "sk": sk},
        )


class LoadGLBNode:
    SUPPORTED_EXTENSIONS = {'.glb'}

    @classmethod
    def _scan_files(cls):
        from pathlib import Path
        results = []
        for base_dir in [get_input_directory(), get_output_directory()]:
            base = Path(base_dir)
            if not base.exists():
                continue
            for f in base.rglob("*"):
                if f.suffix.lower() in cls.SUPPORTED_EXTENSIONS:
                    results.append(str(f.relative_to(base)).replace("\\", "/"))
        return sorted(set(results))

    @classmethod
    def INPUT_TYPES(cls):
        files = cls._scan_files()
        return {
            "required": {
                "model_file": (sorted(files) if files else ["(no files found)"],),
            },
        }

    RETURN_TYPES = ("FILE_3D",)
    RETURN_NAMES = ("model_3d",)
    FUNCTION = "execute"
    CATEGORY = "Hitem3D"
    DESCRIPTION = "Load a GLB 3D model file from disk."

    def execute(self, model_file):
        from comfy_api.latest._util.geometry_types import File3D

        filepath = folder_paths.get_annotated_filepath(model_file)
        if not os.path.isfile(filepath):
            raise RuntimeError(f"3D model file not found: {filepath}")
        return (File3D(filepath),)


# ── 扩展注册 ───────────────────────────────────────────────────────────


class Hitem3DExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            ImageTo3DNode,
            TextureNode,
        ]


NODES_LIST: list[type[io.ComfyNode]] = [
    ImageTo3DNode,
    TextureNode,
]

NODE_CLASS_MAPPINGS = {
    "ImageTo3DNode": ImageTo3DNode,
    "TextureNode": TextureNode,
    "LoadGLBNode": LoadGLBNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageTo3DNode": "hitem3d:ImageTo3D",
    "TextureNode": "hitem3d:Texture",
    "LoadGLBNode": "hitem3d:Load3DModel",
}

WEB_DIRECTORY = "./web"


async def comfy_entrypoint() -> Hitem3DExtension:
    return Hitem3DExtension()
