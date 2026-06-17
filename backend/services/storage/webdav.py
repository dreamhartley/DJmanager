"""WebDAV 存储后端（基于 httpx 自前实现）

实现的 WebDAV 动词：PROPFIND / MKCOL / PUT / GET(+Range) / DELETE / MOVE / COPY。
适配 nginx、Apache(mod_dav)、rclone serve webdav、Nextcloud 等常见服务。
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit

import aiofiles
import httpx
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse, Response

from .base import Storage

# PROPFIND 请求体：只取我们需要的属性
_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop>'
    "<d:resourcetype/><d:getcontentlength/>"
    "</d:prop></d:propfind>"
)

_DAV_NS = "{DAV:}"


class WebDAVError(Exception):
    """WebDAV 操作失败"""


class WebDAVStorage(Storage):
    """WebDAV 存储后端。

    base_path 为 WebDAV 服务上对应 `data/works` 的目录（前端通过浏览器选择）。
    relpath 含 rj_code 前缀，相对于该 base_path。
    """

    name = "webdav"

    def __init__(self, url: str, username: str = "", password: str = "", base_path: str = ""):
        self.base_url = url.rstrip("/")
        self.base_path = base_path.strip("/")
        auth = httpx.BasicAuth(username, password) if username else None
        self._client = httpx.AsyncClient(auth=auth, timeout=30.0, follow_redirects=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---------- URL / 路径工具 ----------

    @staticmethod
    def _segments(*parts: str) -> list[str]:
        segs: list[str] = []
        for p in parts:
            for s in str(p).replace("\\", "/").split("/"):
                if s:
                    segs.append(s)
        return segs

    def _url(self, rel: str = "", is_dir: bool = False) -> str:
        """构建某个相对路径（含 base_path、rj_code）的完整 URL"""
        segs = self._segments(self.base_path, rel)
        path = "/".join(quote(s) for s in segs)
        url = f"{self.base_url}/{path}" if path else self.base_url
        if is_dir and not url.endswith("/"):
            url += "/"
        return url

    def _raw_url(self, rel: str = "", is_dir: bool = False) -> str:
        """构建相对 WebDAV 服务根（不含 base_path）的完整 URL，供目录浏览器使用"""
        segs = self._segments(rel)
        path = "/".join(quote(s) for s in segs)
        url = f"{self.base_url}/{path}" if path else self.base_url
        if is_dir and not url.endswith("/"):
            url += "/"
        return url

    def _server_dir_path(self, rel: str = "") -> str:
        """某相对路径在服务器上的绝对路径（未编码，无尾部斜杠），用于 PROPFIND 比对"""
        segs = self._segments(self.base_path, rel)
        return "/" + "/".join(segs)

    @staticmethod
    def _raw_server_dir_path(rel: str = "") -> str:
        """相对 WebDAV 服务根的某路径在服务器上的绝对路径（不含 base_path，未编码，无尾部斜杠）"""
        segs: list[str] = []
        for s in str(rel).replace("\\", "/").split("/"):
            if s:
                segs.append(s)
        return "/" + "/".join(segs)

    @staticmethod
    def _self_path_variants(request_url) -> set[str]:
        """根据 PROPFIND 的实际请求 URL（httpx 会把重定向后的最终 URL 放在 resp.url）
        推导"目录自身"可能的 href 形式，用于在 multistatus 响应中过滤掉自身条目。

        服务器返回的 href 写法各异：
        - 可能带或不带尾部斜杠
        - 可能以绝对路径形式（/dav/foo）或完整 URL（https://host/dav/foo）
        - 可能编码或未编码
        - 根目录的 href（如 "/"）经 _parse_multistatus 的 rstrip("/") 后变成空串 ""

        因此返回多种规范化形态的集合，逐一比对。
        """
        variants: set[str] = {""}  # 兼容根目录 href 被解析成空串的情况
        for u in (request_url, str(request_url)):
            try:
                split = urlsplit(str(u))
            except ValueError:
                continue
            path = unquote(split.path)
            # 去尾部斜杠 + 同时保留带尾部斜杠的版本
            for p in (path, path.rstrip("/"), path.rstrip("/") + "/"):
                if p:
                    variants.add(p)
                    variants.add(p.rstrip("/"))
        return variants

    # ---------- 底层请求 ----------

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise WebDAVError(f"WebDAV 请求失败 ({method} {url}): {e}") from e

    async def _propfind(self, rel: str, depth: str) -> httpx.Response:
        return await self._request(
            "PROPFIND",
            self._url(rel, is_dir=True),
            headers={"Depth": depth, "Content-Type": "application/xml"},
            content=_PROPFIND_BODY,
        )

    async def _exists_rel(self, rel: str) -> bool:
        resp = await self._propfind(rel, "0")
        return resp.status_code in (200, 207)

    async def _mkcol(self, rel: str) -> bool:
        """对 rel 执行 MKCOL 创建目录。

        返回 True 表示目录已创建或已存在；返回 False 表示 MKCOL 不被支持/被拒绝
        （如 403/405/501），调用方应回退到"依赖 PUT 自动建父目录"的策略。
        Alist/OpenList、rclone serve webdav 等实现支持 PUT 到不存在的路径自动建目录，
        因此即使 MKCOL 失败也仍有机会上传成功。

        注意：404 视为父目录确实不存在（真正的错误），仍抛出异常。
        """
        resp = await self._request("MKCOL", self._url(rel, is_dir=True))
        if resp.status_code in (200, 201):
            return True
        if resp.status_code == 405:
            # 405 Method Not Allowed：目录已存在（部分实现）或根路径不可创建
            return True
        if resp.status_code in (403, 409, 415, 501):
            # 403 Forbidden：权限不足或服务端禁用 MKCOL（Alist 仅开启上传权限时常返回此码）
            # 409 Conflict：父目录不存在（标准含义，但许多实现也会自动建父目录）
            # 415/501：不支持的媒体类型/方法
            # 以上情形一律回退到 PUT 自动建目录策略
            return False
        # 其它非预期状态码（如 404、5xx）视为真正的错误
        raise WebDAVError(f"创建目录失败 ({rel}): HTTP {resp.status_code}")

    async def _ensure_collection(self, rel: str) -> None:
        """逐级尝试创建 rel 指向的目录（base_path 视为已存在）。

        对 MKCOL 失败的路径段不报错——Alist/OpenList、rclone serve webdav 等服务端
        支持 PUT 到不存在的路径时自动创建父目录，因此 MKCOL 失败仍可通过 PUT 完成上传。
        """
        segs = self._segments(rel)
        acc = ""
        for s in segs:
            acc = f"{acc}/{s}" if acc else s
            if await self._exists_rel(acc):
                continue
            # MKCOL 可能因权限/不支持而失败，忽略错误继续尝试下一段
            try:
                await self._mkcol(acc)
            except WebDAVError:
                # 仅当请求本身异常（如网络错误）时才向上抛；HTTP 状态码已在 _mkcol 内处理
                raise

    async def _unique_name(self, rel_dir: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        name = filename
        counter = 1
        while await self._exists_rel(f"{rel_dir}/{name}" if rel_dir else name):
            name = f"{base}_{counter}{ext}"
            counter += 1
        return name

    # ---------- 作品级 ----------

    async def work_exists(self, rj_code: str) -> bool:
        return await self._exists_rel(rj_code)

    async def ensure_work_dir(self, rj_code: str) -> None:
        await self._ensure_collection(rj_code)

    async def delete_work_dir(self, rj_code: str) -> None:
        resp = await self._request("DELETE", self._url(rj_code, is_dir=True))
        if resp.status_code not in (200, 202, 204, 404):
            raise WebDAVError(f"删除作品目录失败 ({rj_code}): HTTP {resp.status_code}")

    # ---------- 文件 ----------

    async def _put(self, rel: str, content) -> None:
        resp = await self._request("PUT", self._url(rel), content=content)
        if resp.status_code not in (200, 201, 204):
            raise WebDAVError(f"上传文件失败 ({rel}): HTTP {resp.status_code}")

    async def save_file(self, rj_code: str, filename: str, content: bytes, subfolder: str = "") -> tuple[str, int]:
        rel_dir = "/".join(self._segments(rj_code, subfolder))
        await self._ensure_collection(rel_dir)
        name = await self._unique_name(rel_dir, filename)
        rel = f"{rel_dir}/{name}"
        await self._put(rel, content)
        return rel, len(content)

    async def save_file_from_path(self, rj_code: str, filename: str, local_path: str, subfolder: str = "") -> tuple[str, int]:
        rel_dir = "/".join(self._segments(rj_code, subfolder))
        await self._ensure_collection(rel_dir)
        name = await self._unique_name(rel_dir, filename)
        rel = f"{rel_dir}/{name}"
        size = os.path.getsize(local_path)

        async def _aiter():
            async with aiofiles.open(local_path, "rb") as f:
                while True:
                    chunk = await f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        resp = await self._request(
            "PUT", self._url(rel),
            content=_aiter(),
            headers={"Content-Length": str(size)},
        )
        if resp.status_code not in (200, 201, 204):
            raise WebDAVError(f"上传文件失败 ({rel}): HTTP {resp.status_code}")
        return rel, size

    async def delete_file(self, rj_code: str, relpath: str) -> bool:
        resp = await self._request("DELETE", self._url(relpath))
        if resp.status_code in (200, 202, 204):
            return True
        if resp.status_code == 404:
            return False
        raise WebDAVError(f"删除文件失败 ({relpath}): HTTP {resp.status_code}")

    async def rename_file(self, rj_code: str, old_relpath: str, new_name: str) -> tuple[str, str]:
        if not await self._exists_rel(old_relpath):
            raise FileNotFoundError(f"文件不存在: {old_relpath}")
        parent = "/".join(self._segments(old_relpath)[:-1])
        new_rel = f"{parent}/{new_name}" if parent else new_name
        if await self._exists_rel(new_rel):
            raise FileExistsError(f"目标文件已存在: {new_name}")
        await self._move(old_relpath, new_rel)
        return new_rel, new_name

    async def read_bytes(self, rj_code: str, relpath: str) -> bytes:
        resp = await self._request("GET", self._url(relpath))
        if resp.status_code != 200:
            raise FileNotFoundError(f"物理文件不存在: {relpath}")
        return resp.content

    async def exists(self, rj_code: str, relpath: str) -> bool:
        return await self._exists_rel(relpath)

    async def stat_size(self, rj_code: str, relpath: str) -> int:
        resp = await self._propfind(relpath, "0")
        if resp.status_code not in (200, 207):
            raise FileNotFoundError(f"物理文件不存在: {relpath}")
        for _, _, is_dir, size in self._parse_multistatus(resp.text):
            if not is_dir:
                return size
        return 0

    async def open_stream(self, rj_code: str, relpath: str, range_header: str | None,
                          filename: str, media_type: str) -> Response:
        headers = {}
        if range_header:
            headers["Range"] = range_header
        req = self._client.build_request("GET", self._url(relpath), headers=headers)
        try:
            upstream = await self._client.send(req, stream=True)
        except httpx.HTTPError as e:
            raise WebDAVError(f"读取文件失败 ({relpath}): {e}") from e

        if upstream.status_code == 404:
            await upstream.aclose()
            raise FileNotFoundError(f"物理文件不存在: {relpath}")

        # 透传与 Range / 流媒体相关的响应头
        passthrough = {}
        for h in ("content-length", "content-range", "accept-ranges", "last-modified", "etag"):
            if h in upstream.headers:
                passthrough[h] = upstream.headers[h]
        passthrough.setdefault("accept-ranges", "bytes")

        return StreamingResponse(
            upstream.aiter_bytes(),
            status_code=upstream.status_code,
            media_type=media_type,
            headers=passthrough,
            background=BackgroundTask(upstream.aclose),
        )

    # ---------- 跨作品复制/移动 ----------

    async def _move(self, src_rel: str, dst_rel: str, is_dir: bool = False) -> None:
        resp = await self._request(
            "MOVE", self._url(src_rel, is_dir=is_dir),
            headers={"Destination": self._url(dst_rel, is_dir=is_dir), "Overwrite": "F"},
        )
        if resp.status_code not in (200, 201, 204):
            raise WebDAVError(f"移动失败 ({src_rel} -> {dst_rel}): HTTP {resp.status_code}")

    async def _copy(self, src_rel: str, dst_rel: str) -> None:
        resp = await self._request(
            "COPY", self._url(src_rel),
            headers={"Destination": self._url(dst_rel), "Overwrite": "F"},
        )
        if resp.status_code not in (200, 201, 204):
            raise WebDAVError(f"复制失败 ({src_rel} -> {dst_rel}): HTTP {resp.status_code}")

    async def copy_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        if not await self._exists_rel(src_relpath):
            raise FileNotFoundError(f"源文件不存在: {src_relpath}")
        await self._ensure_collection(target_rj_code)
        src_name = self._segments(src_relpath)[-1]
        name = await self._unique_name(target_rj_code, src_name)
        dst_rel = f"{target_rj_code}/{name}"
        await self._copy(src_relpath, dst_rel)
        return dst_rel, name, await self.stat_size(target_rj_code, dst_rel)

    async def move_within(self, src_relpath: str, target_rj_code: str) -> tuple[str, str, int]:
        if not await self._exists_rel(src_relpath):
            raise FileNotFoundError(f"源文件不存在: {src_relpath}")
        await self._ensure_collection(target_rj_code)
        src_name = self._segments(src_relpath)[-1]
        name = await self._unique_name(target_rj_code, src_name)
        dst_rel = f"{target_rj_code}/{name}"
        await self._move(src_relpath, dst_rel)
        return dst_rel, name, await self.stat_size(target_rj_code, dst_rel)

    # ---------- 文件夹 ----------

    def _parse_multistatus(self, xml_text: str) -> list[tuple[str, str, bool, int]]:
        """解析 PROPFIND 响应，返回 [(href_path, name, is_dir, size), ...]
        href_path 为去除编码后的服务器绝对路径（无尾部斜杠）。
        """
        out: list[tuple[str, str, bool, int]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        for resp in root.findall(f"{_DAV_NS}response"):
            href_el = resp.find(f"{_DAV_NS}href")
            if href_el is None or not href_el.text:
                continue
            href_path = unquote(urlsplit(href_el.text).path).rstrip("/")
            is_dir = resp.find(f".//{_DAV_NS}resourcetype/{_DAV_NS}collection") is not None
            size_el = resp.find(f".//{_DAV_NS}getcontentlength")
            try:
                size = int(size_el.text) if size_el is not None and size_el.text else 0
            except ValueError:
                size = 0
            name = href_path.rsplit("/", 1)[-1]
            out.append((href_path, name, is_dir, size))
        return out

    async def list_directory(self, rj_code: str, subpath: str = "") -> tuple[list[tuple[str, int]], list[str]]:
        rel_dir = "/".join(self._segments(rj_code, subpath))
        resp = await self._propfind(rel_dir, "1")
        if resp.status_code == 404:
            return [], []
        if resp.status_code not in (200, 207):
            raise WebDAVError(f"列目录失败 ({rel_dir}): HTTP {resp.status_code}")

        # 用实际请求 URL（含重定向后的最终 URL）推导目录自身路径，
        # 避免服务器返回的 href 带额外路径前缀（如 URL 中的 /dav）时过滤失败。
        self_paths = self._self_path_variants(resp.url)
        files: list[tuple[str, int]] = []
        folders: list[str] = []
        for href_path, name, is_dir, size in self._parse_multistatus(resp.text):
            if href_path in self_paths or not name:
                continue  # 跳过目录自身
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if is_dir:
                folders.append(rel)
            else:
                files.append((rel, size))
        # 文件夹在前、文件在后，各自按名称排序
        folders.sort(key=lambda p: p.rsplit("/", 1)[-1].lower())
        files.sort(key=lambda f: f[0].rsplit("/", 1)[-1].lower())
        return files, folders

    async def create_folder(self, rj_code: str, subpath: str, folder_name: str) -> str:
        parent = "/".join(self._segments(rj_code, subpath))
        await self._ensure_collection(parent)
        rel = f"{parent}/{folder_name}"
        if await self._exists_rel(rel):
            raise FileExistsError(f"文件夹已存在: {folder_name}")
        await self._mkcol(rel)
        return rel

    async def delete_folder(self, rj_code: str, folder_path: str) -> None:
        rel = "/".join(self._segments(rj_code, folder_path))
        if not folder_path:
            raise ValueError("不允许删除作品根目录")
        if not await self._exists_rel(rel):
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        resp = await self._request("DELETE", self._url(rel, is_dir=True))
        if resp.status_code not in (200, 202, 204):
            raise WebDAVError(f"删除文件夹失败 ({folder_path}): HTTP {resp.status_code}")

    async def rename_folder(self, rj_code: str, folder_path: str, new_name: str) -> str:
        rel = "/".join(self._segments(rj_code, folder_path))
        if not await self._exists_rel(rel):
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        parent = "/".join(self._segments(rel)[:-1])
        new_rel = f"{parent}/{new_name}" if parent else new_name
        if await self._exists_rel(new_rel):
            raise FileExistsError(f"目标已存在: {new_name}")
        await self._move(rel, new_rel, is_dir=True)
        return new_rel

    # ---------- 连接测试 / 目录浏览（供设置页使用）----------

    async def test_connection(self) -> None:
        """验证连通性与 base_path 是否存在；失败抛出 WebDAVError"""
        resp = await self._propfind("", "0")
        if resp.status_code in (401, 403):
            raise WebDAVError("认证失败：用户名或密码错误")
        if resp.status_code == 404:
            raise WebDAVError("指定的目录不存在")
        if resp.status_code not in (200, 207):
            raise WebDAVError(f"连接失败：HTTP {resp.status_code}")

    async def browse(self, rel: str = "") -> list[dict]:
        """浏览 WebDAV 服务根下某目录的子目录（供前端选择作品根目录）。

        rel 为相对 *WebDAV 服务根* 的路径（不含 base_path 前缀），以便用户能浏览到
        base_path 之上/之外的目录。返回 [{name, path}]，path 同样相对 WebDAV 服务根。
        """
        rel = "/".join(self._segments(rel))
        resp = await self._request(
            "PROPFIND",
            self._raw_url(rel, is_dir=True),
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=_PROPFIND_BODY,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code not in (200, 207):
            raise WebDAVError(f"浏览失败：HTTP {resp.status_code}")
        # 用实际请求 URL（含重定向后的最终 URL）推导目录自身路径，
        # 避免服务器返回的 href 带额外路径前缀（如 URL 中的 /dav）时过滤失败。
        self_paths = self._self_path_variants(resp.url)
        dirs: list[dict] = []
        for href_path, name, is_dir, _ in self._parse_multistatus(resp.text):
            if not is_dir or not name:
                continue
            if href_path in self_paths:
                continue  # 跳过目录自身
            path = f"{rel}/{name}" if rel else name
            dirs.append({"name": name, "path": path})
        dirs.sort(key=lambda d: d["name"].lower())
        return dirs
