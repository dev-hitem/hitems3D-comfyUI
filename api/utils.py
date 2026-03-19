import asyncio
import base64
from contextlib import ExitStack
from datetime import datetime
import json
import mimetypes
import os
import uuid

import aiohttp
import tos
from comfy.model_management import throw_exception_if_processing_interrupted


class Hitem3dAPI:
    API_BASE_URL = "https://api.hitem3d.ai/open-api/v1"
    API_HOST = "api.hitem3d.ai"
    USER_AGENT = "Apifox/1.0.0 (https://apifox.com)"
    REQUEST_TIMEOUT_SECONDS = 30
    TASK_POLL_INTERVAL_SECONDS = 10
    TASK_POLL_TIMEOUT_SECONDS = 60 * 60
    TASK_POLL_REQUEST_TIMEOUT_SECONDS = 30
    TOS_ENDPOINT = "tos-ap-southeast-1.volces.com"
    TOS_REGION = "ap-southeast-1"
    TOS_BUCKET_NAME = "mm-sparc3d-prod"
    TOS_PUBLIC_BASE_URL = "https://hitem3dstatic.zaohaowu.net/"
    VALID_MESH_FORMATS = {".glb", ".usdz", ".obj", ".fbx", ".stl"}
    TASK_PENDING_STATES = {"created", "queueing", "processing"}

    def __init__(self, ak, sk):
        self.ak = ak
        self.sk = sk

    def _build_headers(self, authorization=None, extra_headers=None):
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "*/*",
            "Host": self.API_HOST,
            "Connection": "keep-alive",
        }
        if authorization:
            headers["Authorization"] = authorization
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _guess_mime_type(self, file_path):
        mime, _ = mimetypes.guess_type(file_path)
        return mime or "image/jpeg"

    def _extract_error_message(self, body, fallback):
        if isinstance(body, dict):
            for key in ("msg", "message", "detail", "error"):
                value = body.get(key)
                if value:
                    return str(value)
        return fallback

    def _build_form_data(self, files, data):
        form_data = aiohttp.FormData()
        for key, value in data.items():
            if value is None:
                continue
            form_data.add_field(key, str(value))

        file_items = files.items() if isinstance(files, dict) else files
        for field_name, file_info in file_items:
            filename, file_obj, content_type = file_info
            form_data.add_field(
                field_name,
                file_obj,
                filename=filename,
                content_type=content_type,
            )
        return form_data

    async def _parse_json_response(self, response, error_message):
        text = await response.text()
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            compact_text = " ".join(text.strip().split())[:300]
            raise RuntimeError(
                f"{error_message}: invalid JSON response: {compact_text or '<empty>'}"
            ) from exc

    async def _request_json(
        self,
        session,
        method,
        path,
        authorization=None,
        *,
        params=None,
        data=None,
        timeout_seconds=None,
        extra_headers=None,
        error_message=None,
    ):
        timeout = aiohttp.ClientTimeout(
            total=timeout_seconds or self.REQUEST_TIMEOUT_SECONDS
        )
        url = f"{self.API_BASE_URL}/{path.lstrip('/')}"
        request_error = error_message or f"{method} {path} failed"

        try:
            async with session.request(
                method,
                url,
                headers=self._build_headers(
                    authorization=authorization,
                    extra_headers=extra_headers,
                ),
                params=params,
                data=data,
                timeout=timeout,
            ) as response:
                body = await self._parse_json_response(response, request_error)
                return response.status, body
        except asyncio.TimeoutError as exc:
            raise RuntimeError(f"{request_error}: request timed out") from exc
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"{request_error}: {exc}") from exc

    async def _fetch_access_token(self, session):
        token = f"{self.ak}:{self.sk}".encode("utf-8")
        auth = "Basic " + base64.b64encode(token).decode("ascii")
        status_code, body = await self._request_json(
            session,
            "POST",
            "auth/token",
            authorization=auth,
            extra_headers={"Content-Type": "application/json"},
            data={},
            error_message="get access token failed",
        )
        if status_code != 200 or body.get("code") != 200:
            msg = self._extract_error_message(body, "Unknown error")
            raise RuntimeError(f"get access token failed: {msg}")

        data = body.get("data") or {}
        access_token = data.get("accessToken")
        if not access_token:
            raise RuntimeError("get access token failed: accessToken is missing")
        return access_token

    async def _get_authorization(self, session):
        access_token = await self._fetch_access_token(session)
        return "Bearer " + access_token

    async def _submit_and_wait(self, session, files, data, authorization):
        status_code, body = await self.submit_task(session, files, data, authorization)
        return await self.handle_task_response(
            session,
            status_code,
            body,
            authorization,
        )

    async def get_access_token(self):
        async with aiohttp.ClientSession() as session:
            return await self._fetch_access_token(session)

    async def image_to_3d(self, image_path, request_type, face, model, resolution):
        async with aiohttp.ClientSession() as session:
            authorization = await self._get_authorization(session)
            data = {
                "request_type": request_type,
                "face": face,
                "resolution": resolution,
                "model": model,
                "format": 2,
            }
            with open(image_path, "rb") as image_file:
                files = {
                    "images": (
                        os.path.basename(image_path),
                        image_file,
                        self._guess_mime_type(image_path),
                    )
                }
                return await self._submit_and_wait(session, files, data, authorization)

    async def multi_view_to_3d(
        self,
        multi_images,
        multi_images_bit,
        request_type,
        face,
        model,
        resolution,
    ):
        async with aiohttp.ClientSession() as session:
            authorization = await self._get_authorization(session)
            data = {
                "request_type": request_type,
                "face": face,
                "resolution": resolution,
                "model": model,
                "format": 2,
                "multi_images_bit": multi_images_bit,
            }
            with ExitStack() as stack:
                files = []
                for img_path in multi_images:
                    if img_path is None:
                        continue
                    filename = os.path.basename(img_path)
                    image_file = stack.enter_context(open(img_path, "rb"))
                    files.append(
                        (
                            "multi_images",
                            (filename, image_file, self._guess_mime_type(img_path)),
                        )
                    )

                if not files:
                    raise ValueError("At least one image is required")

                return await self._submit_and_wait(session, files, data, authorization)

    async def texture(self, image_path, mesh_url, model):
        async with aiohttp.ClientSession() as session:
            authorization = await self._get_authorization(session)
            data = {
                "request_type": 2,
                "resolution": 512,
                "model": model,
                "format": 2,
                "mesh_url": mesh_url,
            }
            with open(image_path, "rb") as image_file:
                files = {
                    "images": (
                        os.path.basename(image_path),
                        image_file,
                        self._guess_mime_type(image_path),
                    )
                }
                return await self._submit_and_wait(session, files, data, authorization)

    async def upload_file(self, mesh_path):
        _, ext = os.path.splitext(os.path.basename(mesh_path))
        ext = ext.lower()
        if ext not in self.VALID_MESH_FORMATS:
            raise ValueError("Invalid mesh file format")

        async with aiohttp.ClientSession() as session:
            authorization = await self._get_authorization(session)
            status_code, body = await self._request_json(
                session,
                "GET",
                "upload/token",
                authorization=authorization,
                error_message="get upload token failed",
            )
            if status_code != 200 or body.get("code") != 200:
                msg = self._extract_error_message(body, "Unknown error")
                raise RuntimeError(f"Upload model failed: {msg}")

        data = body.get("data") or {}
        access_key_id = data.get("accessKeyId")
        secret_access_key = data.get("secretAccessKey")
        session_key = data.get("sessionKey")
        if not access_key_id or not secret_access_key or not session_key:
            raise RuntimeError("Upload model failed: upload credentials are incomplete")

        object_key = f"comfyui/mesh/{datetime.now().strftime('%Y-%m-%d')}/{uuid.uuid4()}{ext}"
        client = tos.TosClientV2(
            access_key_id,
            secret_access_key,
            self.TOS_ENDPOINT,
            self.TOS_REGION,
            security_token=session_key,
        )
        await asyncio.to_thread(
            client.put_object_from_file,
            self.TOS_BUCKET_NAME,
            object_key,
            mesh_path,
        )
        return self.TOS_PUBLIC_BASE_URL + object_key

    async def submit_task(self, session, files, data, authorization):
        payload = dict(data)
        payload["plug_type"] = "COMFYUI"
        payload["plug_task_id"] = uuid.uuid4().hex
        return await self._request_json(
            session,
            "POST",
            "submit-task",
            authorization=authorization,
            data=self._build_form_data(files, payload),
            error_message="submit task failed",
        )

    async def handle_task_response(self, session, status_code, body, authorization):
        if status_code != 200:
            return {
                "status": "error",
                "message": self._extract_error_message(
                    body,
                    f"submit task failed with status code {status_code}",
                ),
                "task_id": None,
            }

        if body.get("code") != 200:
            return {
                "status": "error",
                "message": self._extract_error_message(
                    body,
                    "An unexpected error occurred",
                ),
                "task_id": None,
            }

        task_id = (body.get("data") or {}).get("task_id")
        if not task_id:
            return {
                "status": "error",
                "message": "submit task failed: task_id is missing",
                "task_id": None,
            }

        result = await self.task_status(session, task_id, authorization)
        if isinstance(result, str):
            return {
                "status": "error",
                "message": result,
                "task_id": task_id,
            }

        model_url = result.get("url")
        if not model_url:
            return {
                "status": "error",
                "message": "No downloadable model URL found in task result",
                "task_id": task_id,
            }
        return {"status": "success", "model_url": model_url, "task_id": task_id}

    async def task_status(self, session, task_id, authorization):
        start_time = asyncio.get_running_loop().time()
        last_state = None

        while True:
            throw_exception_if_processing_interrupted()

            if asyncio.get_running_loop().time() - start_time > self.TASK_POLL_TIMEOUT_SECONDS:
                return "Task polling timed out."

            try:
                status_code, body = await self._request_json(
                    session,
                    "GET",
                    "query-task",
                    authorization=authorization,
                    params={"task_id": task_id},
                    timeout_seconds=self.TASK_POLL_REQUEST_TIMEOUT_SECONDS,
                    extra_headers={"Accept-Language": "en-US"},
                    error_message="query task failed",
                )
            except RuntimeError as exc:
                print(f"Polling task retry because of temporary error: {exc}")
                await asyncio.sleep(self.TASK_POLL_INTERVAL_SECONDS)
                continue

            if status_code != 200:
                print(f"Polling task returned unexpected status code: {status_code}")
                await asyncio.sleep(self.TASK_POLL_INTERVAL_SECONDS)
                continue

            if body.get("code") != 200:
                msg = self._extract_error_message(body, "Unknown error")
                return f"Task query failed: {msg}"

            data_obj = body.get("data") or {}
            state = data_obj.get("state")
            if state != last_state:
                print(f"Task {task_id} state: {state}")
                last_state = state

            if state in self.TASK_PENDING_STATES:
                await asyncio.sleep(self.TASK_POLL_INTERVAL_SECONDS)
                continue
            if state == "success":
                return data_obj
            if state == "failed":
                return self._extract_error_message(data_obj, "Task failed.")

            print(f"Polling task returned unexpected state: {state}")
            await asyncio.sleep(self.TASK_POLL_INTERVAL_SECONDS)
          