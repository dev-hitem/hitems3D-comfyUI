from math import e
import requests
import base64
import time
import uuid
import os
import mimetypes
from datetime import datetime
import tos

class Hitem3dAPI:
    def __init__(self, ak, sk):
        self.ak = ak
        self.sk = sk

    async def get_access_token(self):
        token = f"{self.ak}:{self.sk}".encode("utf-8")
        auth = "Basic " + base64.b64encode(token).decode("ascii")

        url = "https://api.hitem3d.ai/open-api/v1/auth/token"

        payload={}
        headers = {
        'Authorization': auth,
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.hitem3d.ai',
        'Connection': 'keep-alive'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        try:
            body = response.json()
        except Exception:
             raise RuntimeError("get access token failed")
        if body.get("code") != 200:
            msg = body.get("msg") or "Unknown error"
            raise RuntimeError("get access token failed：" + msg)
        data = body.get("data", {}) if isinstance(body, dict) else {}
        return data.get("accessToken")
      
    async def image_to_3d(self, image_path, request_type, face, model, format, resolution):
        access_token = await self.get_access_token()
        authorization = "Bearer " + access_token
      
        files = {
            "images": (os.path.basename(image_path), open(image_path, "rb"), "image/jpeg")
        }
        data = {
            "request_type": request_type,
            "face": face,
            "resolution":resolution,
            "model": model,
            "format":format,
        }
        response = await self.submit_task(files, data, authorization)
        return await self.handle_task_response(response, authorization)
    async def multi_view_to_3d(self, multi_images, multi_images_bit, request_type, face, model, format, resolution):
        access_token = await self.get_access_token()
        authorization = "Bearer " + access_token
        # multi_images 是一个路径列表，这里构造 requests 所需的 files 列表
        files = []
        for img_path in multi_images:
            if img_path is None:
                continue
            filename = os.path.basename(img_path)
            mime, _ = mimetypes.guess_type(img_path)
            if mime is None:
                mime = "image/jpeg"
            files.append(
                (
                    "multi_images",
                    (filename, open(img_path, "rb"), mime),
                )
            )
        data = {
            "request_type": request_type,
            "face": face,
            "resolution": resolution,
            "model": model,
            "format": format,
            "multi_images_bit": multi_images_bit,
        }
        print(files)
        response = await self.submit_task(files, data, authorization)
        return await self.handle_task_response(response, authorization)    
    async def texture(self, image_path, mesh_url,format,model):
        access_token = await self.get_access_token()
        authorization = "Bearer " + access_token
        files = {
            "images": (os.path.basename(image_path), open(image_path, "rb"), "image/jpeg")
        }
        data = {
            "request_type": 2,
            "face": None,
            "resolution": 512,
            "model": model,
            "format": format,
            "mesh_url": mesh_url,
        }
        response = await self.submit_task(files, data, authorization)
        return await self.handle_task_response(response, authorization)         
    async def upload_file(self, mesh_path):
        base_name = os.path.basename(mesh_path)
        base, ext = os.path.splitext(base_name)
        if ext not in [".glb", ".usdz",".obj",".fbx",".stl"]:
            raise ValueError("Invalid mesh file format")
        access_token = await self.get_access_token()
        authorization = "Bearer " + access_token
        url = "https://api.hitem3d.ai/open-api/v1/upload/token"
        headers = {
            "Authorization": authorization,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Accept": "*/*",
            "Host": "api.hitem3d.ai",
            "Connection": "keep-alive"
        }
        response = requests.get(url=url,headers=headers)
        print(response.json())
        code = response.json().get("code")
        if code != 200:
            raise RuntimeError("Upload model failed")
        data = response.json().get('data', {})   
        accessKeyId = data.get('accessKeyId', None)
        secretAccessKey = data.get('secretAccessKey', None)
        sessionKey = data.get('sessionKey', None) 
        endpoint = "tos-ap-southeast-1.volces.com"
        region = "ap-southeast-1"
        now_str = datetime.now().strftime("%Y-%m-%d")
        bucket_name = "mm-sparc3d-prod"
        obj_id = str(uuid.uuid4())
        object_key = "comfyui/mesh/"+now_str+"/"+obj_id+ext;
        client = tos.TosClientV2(accessKeyId, secretAccessKey, endpoint, region, security_token=sessionKey)
        print("Initialized TOS client. ")
        out = client.pre_signed_url(tos.HttpMethodType.Http_Method_Put, bucket = bucket_name, key = object_key, expires = 3600)
        print(f"Pre-signed URL: {out.signed_url}")
        out = client.put_object_from_file(bucket_name, object_key, mesh_path)
        mesh_url = "https://hitem3dstatic.zaohaowu.net/" + object_key
        return mesh_url
    async def submit_task(self, files, data, authorization):
        url = "https://api.hitem3d.ai/open-api/v1/submit-task"
        headers = {
            "Authorization": authorization,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Accept": "*/*",
            "Host": "api.hitem3d.ai",
            "Connection": "keep-alive"
        }
        data["plug_type"]="COMFYUI",
        data["plug_task_id"]=uuid.uuid4().hex,
        response = requests.post(
                url=url,
                headers=headers,
                files=files,
                data=data
            )
        return response
    async def handle_task_response(self, response, authorization):
        if response.status_code == 200:
            code = response.json().get("code")
            if code != 200:
                return {
                    'status': 'error',
                    'message': response.json().get('msg', 'An unexpected error occurred'),
                    'task_id': None
                }
            task_id = response.json().get("data", {}).get("task_id")
            print(f"Task ID: {task_id}")
            result = await self.task_status(task_id, authorization)
            if isinstance(result, str):
                return {
                    'status': 'error',
                    'message': result,
                    'task_id': task_id
                }
            # 优先使用 GLB，其次 OBJ / STL / FBX / USDZ / url
            data = result
            model_url = data.get('url')
            if not model_url:
                return {
                    'status': 'error',
                    'message': 'No downloadable model URL found in task result',
                    'task_id': task_id
                }
            return {'status': 'success', 'model_url': model_url, 'task_id': task_id}
        else:
            return {
                'status': 'error',
                'message': response.json().get('message', 'An unexpected error occurred'),
                'task_id': None
            }
    async def task_status(self, task_id, authorization):
        status_url = "https://api.hitem3d.ai/open-api/v1/query-task?task_id=" + task_id
        headers = {
            "Authorization": authorization,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Accept": "*/*",
            "Host": "api.hitem3d.ai",
            "Connection": "keep-alive",
            "Accept-Language": "en-US"
        }
        for _ in range(200):
            resp = requests.get(status_url, headers=headers)
            print(resp.text)
            try:
                obj = resp.json()
            except Exception:
                return "Failed to get task."
            if obj.get("code") != 200:
                return "Failed to get task."
            data_obj = obj.get("data")
            state = data_obj.get("state")
            if state == "created":
                time.sleep(10)
                continue
            elif state == "queueing":
                time.sleep(10)
                continue
            elif state == "processing":
                time.sleep(10)
                continue
            elif state == "success":
                return data_obj
            else:
                return "Failed to get task."
          