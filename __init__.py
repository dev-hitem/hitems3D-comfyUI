from re import T
from .api.utils import Hitem3dAPI
import os
import json
import torch
import requests
from PIL import Image
from folder_paths import get_output_directory, get_input_directory
__version__ = "1.0.0"
hitems3d_ak = os.environ.get("hitems3d_ak")
hitems3d_sk = os.environ.get("hitems3d_sk")
if not hitems3d_ak:
    p = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(p, 'config.json')) as f:
        config = json.load(f)
        hitems3d_ak = config["hitems3d_ak"]
if not hitems3d_sk:
    p = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(p, 'config.json')) as f:
        config = json.load(f)
        hitems3d_sk = config["hitems3d_sk"]        
def getHitem3dAPI(ak: str, sk: str):
    ak = hitems3d_ak if hitems3d_ak else ak
    sk = hitems3d_sk if hitems3d_sk else sk
    if not ak:
        raise RuntimeError("ak is required")
    if not sk:
        raise RuntimeError("sk is required")     
    return Hitem3dAPI(ak, sk), ak, sk
def convert_format(format):
    FORMAT_MAPPING = {
        "glb": 2,
        "stl": 3,
        "fbx": 4,
        "usdz": 5
    }
    if format in FORMAT_MAPPING:
      return FORMAT_MAPPING[format]
    else:
      raise 2
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
def toImagePath(image,filename):
    if image is None:
        raise None
    if not isinstance(image, (str, bytes, os.PathLike)):
        image_path = save_tensor(image, os.path.join(get_input_directory(), filename))
    else:
        image_path = image   
    return image_path     
def download_model(url,task_id):
    print("downloading model from", url)
    response = requests.get(url)
    if response.status_code == 200:
        subfolder = get_output_directory()
        model_url = url
        # 去掉查询参数
        q_index = model_url.find('?')
        if q_index > 0:
            model_url = model_url[:q_index]
        # 提取文件名
        slash_index = model_url.rfind('/')
        if slash_index >= 0:
            file = task_id+"-"+ model_url[slash_index + 1:]
        out_path = os.path.join(subfolder, file)
        with open(out_path, "wb") as f:
            f.write(response.content)
        print("model downloaded to", out_path)    
        return out_path;
    else:
        raise RuntimeError(f"Failed to download model: {response.status_code}")
class ImageTo3DNode:
    DESCRIPTION = "Generates a 3D model from a single or multi-view image. Supports hitem3dv1.5 / hitem3dv2.0 models with customizable resolution, face count, and output format."

    @classmethod
    def INPUT_TYPES(s):
        config = {
            "required": {
                "ak": ("STRING", {"default": "", "tooltip": "Hitem3D API Access Key. Leave empty if configured in config.json or environment variables."}),
                "sk": ("STRING", {"default": "", "tooltip": "Hitem3D API Secret Key. Leave empty if configured in config.json or environment variables."}),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Main front image (Required) for 3D model generation."}),
                "image_back": ("IMAGE", {"tooltip": "Back reference image (Optional) for multi-view 3D reconstruction."}),
                "image_left": ("IMAGE", {"tooltip": "Left reference image (Optional) for multi-view 3D reconstruction."}),
                "image_right": ("IMAGE", {"tooltip": "Right reference image (Optional) for multi-view 3D reconstruction."}),
                "texture": ("BOOLEAN", {"default": True, "tooltip": "Whether to generate textures. If enabled, the model will include vertex colors/textures."}),
                "model": (["hitem3dv1.5", "hitem3dv2.0"], {"default": "hitem3dv1.5", "tooltip": "3D generation model version. v2.0 provides better quality but takes longer."}),
                "resolution": (["512", "1024", "1536", "1536pro"], {"default": "1024", "tooltip": "Generation resolution. Higher resolution provides more detail but takes more time."}),
                "face": ("INT", {"min": 100000, "max": 2000000, "default": 500000, "tooltip": "Output poly count. Higher count means finer detail but larger file size."}),
                "format": ([ "glb", "stl","fbx","usdz"], {"default": "glb", "tooltip": "Output 3D model file format."}),
            }
        }
        return config

    RETURN_TYPES = ("STRING", "HITMES3D_MODEL_TASK",)
    RETURN_NAMES = ("model_file", "model_task")
    OUTPUT_TOOLTIPS = ("Local path to the downloaded 3D model file", "Task information to be passed to the Texture node for re-texturing")
    FUNCTION = "generate_mesh"
    CATEGORY = "Hitems3D"

    async def generate_mesh(self, ak, sk, texture, image=None, image_back=None, image_left=None, image_right=None, model=None, face=None, format=None, resolution=None):
        if image is None:
            raise RuntimeError("image is required")
        if texture:
            request_type = 3
        else:
            request_type = 1
        format = convert_format(format)    
        image_path = toImagePath(image,"image")
        api, ak, sk = getHitem3dAPI(ak, sk)
        if image_back is None and image_left is None and image_right is None:
            result = await api.image_to_3d(
                image_path, request_type, face, model, format, resolution
            )
        else:
            multi_images = [image_path]
            image_dict = {
                "image_back": image_back,
                "image_left": image_left,
                "image_right": image_right
            }
            multi_images_bit="1";
            for image_name in ["image_back", "image_left", "image_right"]:
                image_ = image_dict[image_name]
                if image_ is not None:
                    image_filename = toImagePath(image_,image_name)
                    multi_images.append(image_filename)
                    multi_images_bit=multi_images_bit+"1"
                else:
                    multi_images_bit=multi_images_bit+"0"
                    multi_images.append(None)
            result = await api.multi_view_to_3d(multi_images,multi_images_bit,request_type, face, model, format, resolution)
               
        if result['status'] != 'success':
            raise RuntimeError(f"Failed to generate mesh: {result['message']}")
        task_id = result['task_id']
        model_url = result['model_url']
        model_file = download_model(model_url,task_id)
        print("model downloaded to", model_file)
        return model_file, {"task_id": task_id, "model_url": model_url, "ak": ak, "sk": sk}
class PortraitImageTo3DNode:
    DESCRIPTION = "Optimized Image-to-3D node for portraits and scenes. Supports scene-portraitv1.5 / v2.0 / v2.1 models. Resolution is automatically determined by model version."

    @classmethod
    def INPUT_TYPES(s):
        config = {
            "required": {
                "ak": ("STRING", {"default": "", "tooltip": "Hitem3D API Access Key. Leave empty if configured in config.json or environment variables."}),
                "sk": ("STRING", {"default": "", "tooltip": "Hitem3D API Secret Key. Leave empty if configured in config.json or environment variables."}),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Front main image (Required) for portrait/scene 3D reconstruction."}),
                "image_back": ("IMAGE", {"tooltip": "Back reference image (Optional) for multi-view reconstruction."}),
                "image_left": ("IMAGE", {"tooltip": "Left reference image (Optional) for multi-view reconstruction."}),
                "image_right": ("IMAGE", {"tooltip": "Right reference image (Optional) for multi-view reconstruction."}),
                "texture": ("BOOLEAN", {"default": True, "tooltip": "Whether to generate textures. If enabled, the model will include vertex colors/textures."}),
                "model": (["scene-portraitv1.5", "scene-portraitv2.0","scene-portraitv2.1"], {"default": "scene-portraitv1.5", "tooltip": "Portrait/Scene model version. v1.5 uses 1536, v2.0/v2.1 uses 1536pro resolution."}),
                "face": ("INT", {"min": 100000, "max": 2000000, "default": 500000, "tooltip": "Output poly count. Higher count means finer detail but larger file size."}),
                "format": ([ "glb", "stl","fbx","usdz"], {"default": "glb", "tooltip": "Output 3D model file format."}),
            }
        }
        return config

    RETURN_TYPES = ("STRING", "HITMES3D_MODEL_TASK",)
    RETURN_NAMES = ("model_file", "model_task")
    OUTPUT_TOOLTIPS = ("Local path to the downloaded 3D model file", "Task information to be passed to the Texture node for re-texturing")
    FUNCTION = "generate_mesh"
    CATEGORY = "Hitems3D"

    async def generate_mesh(self, ak, sk, texture, image=None, image_back=None, image_left=None, image_right=None, model=None, face=None, format=None):
        if image is None:
            raise RuntimeError("image is required")
        if texture:
            request_type = 3
        else:
            request_type = 1
        if model == "scene-portraitv1.5":
            resolution = "1536"
        else:
            resolution = "1536pro"    
        format = convert_format(format)    
        image_path = toImagePath(image,"image")
        api, ak, sk = getHitem3dAPI(ak, sk)
        if image_back is None and image_left is None and image_right is None:
            result = await api.image_to_3d(
                image_path, request_type, face, model, format, resolution
            )
        else:
            multi_images = [image_path]
            image_dict = {
                "image_back": image_back,
                "image_left": image_left,
                "image_right": image_right
            }
            multi_images_bit="1";
            for image_name in ["image_back", "image_left", "image_right"]:
                image_ = image_dict[image_name]
                if image_ is not None:
                    image_filename = toImagePath(image_,image_name)
                    multi_images.append(image_filename)
                    multi_images_bit=multi_images_bit+"1"
                else:
                    multi_images_bit=multi_images_bit+"0"
                    multi_images.append(None)
            result = await api.multi_view_to_3d(multi_images,multi_images_bit,request_type, face, model, format, resolution)
               
        if result['status'] != 'success':
            raise RuntimeError(f"Failed to generate mesh: {result['message']}")
        task_id = result['task_id']
        model_url = result['model_url']
        model_file = download_model(model_url,task_id)
        print("model downloaded to", model_file)
        return model_file, {"task_id": task_id, "model_url": model_url, "ak": ak, "sk": sk}    
class TextrueNode:
    DESCRIPTION = "Regenerates texture maps for existing 3D models. Provide a reference image and the original model (via path/URL or upstream node) to generate new textures."

    @classmethod
    def INPUT_TYPES(s):
        config = {
            "required": {
                "ak": ("STRING", {"default": "", "tooltip": "Hitem3D API Access Key. Leave empty if configured in config.json or environment variables."}),
                "sk": ("STRING", {"default": "", "tooltip": "Hitem3D API Secret Key. Leave empty if configured in config.json or environment variables."}),
                # mesh_url 改为纯文本输入：既可以是本地路径，也可以是网址
                "mesh_url": ("STRING", {"default": "", "tooltip": "Local file path or network URL of the 3D model. Can be left empty if model_task is connected."}),
            },
            "optional": {
                # 可选：风格图，当前实现里没用到，保留扩展空间
                "image": ("IMAGE", {"tooltip": "Texture reference image (Required). The model will generate a new texture map based on this image."}),
                # 也可以直接传入前面节点输出的 model_task，做简单透传
                "model_task": ("HITMES3D_MODEL_TASK", {"tooltip": "Task output from ImageTo3D or PortraitImageTo3D nodes. Automatically uses that model's URL if connected."}),
                "model": (["hitem3dv1.5", "scene-portraitv1.5"], {"default": "hitem3dv1.5", "tooltip": "Model version used for texture generation."}),
                "format": ([ "glb", "stl","fbx","usdz"], {"default": "glb", "tooltip": "Output 3D model file format."}),
            },
        }
        return config

    RETURN_TYPES = ("STRING", "HITMES3D_MODEL_TASK")
    RETURN_NAMES = ("model_file", "model_task")
    OUTPUT_TOOLTIPS = ("Local path to the downloaded 3D model file", "Task information to be passed to subsequent nodes")
    FUNCTION = "generate_mesh"
    CATEGORY = "Hitems3D"

    async def generate_mesh(self, ak, sk, mesh_url, image=None, model_task=None, model=None,format=None):
        if image is None:
            raise RuntimeError("image is required")
        if model_task is not None:
            mesh_url = model_task["model_url"]
            api, ak, sk = getHitem3dAPI(ak, sk)
        else:  
            if mesh_url is None or mesh_url == "":
                raise RuntimeError("mesh_url 不能为空，可以输入本地路径或网络 URL")
            api, ak, sk = getHitem3dAPI(ak, sk)
            if mesh_url.startswith("http://") or mesh_url.startswith("https://"):
                mesh_url =mesh_url;
            else:
                mesh_url =await api.upload_file(mesh_url)     
        print("mesh_url:", mesh_url)    
        format = convert_format(format)    
        image_path = toImagePath(image,"image")
        result = await api.texture(image_path,mesh_url, format,model)
        if result['status'] != 'success':
            raise RuntimeError(f"Failed to generate mesh: {result['message']}")
        task_id = result['task_id']
        model_url = result['model_url']
        model_file = download_model(model_url,task_id) 
        return model_file, {"task_id": task_id, "model_url": model_url, "ak": ak, "sk": sk}    
NODE_CLASS_MAPPINGS = {
    "ImageTo3DNode": ImageTo3DNode,
    "PortraitImageTo3DNode": PortraitImageTo3DNode,
    "TextrueNode": TextrueNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageTo3DNode": "hi3d:ImageTo3D",
    "PortraitImageTo3DNode": "hi3d:PortraitImageTo3D",
    "TextrueNode": "hi3d:Textrue"

}