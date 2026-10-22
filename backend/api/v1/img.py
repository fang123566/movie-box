"""图片代理路由：`GET /api/v1/img?url=<图片完整URL>`。

为什么要有这个接口：
    海报图片存在 image.tmdb.org，这个域名直连不通（被墙）。
    用户浏览器没有代理时，前端所有 <img> 会全部裂图——数据再全也白搭。
    所以让后端代浏览器取图：服务端按 IMAGE_FETCH_PROXY 走代理出口，
    前端引用本地路径，对用户完全透明。

安全边界：
    只允许代理白名单域名（image.tmdb.org），防止被当成开放代理滥用。
    响应带 Cache-Control，浏览器缓存 1 天，TMDB 图片 URL 本身内容不变。
"""
from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from common.settings import settings

router = APIRouter()

# 允许代理的图片域名白名单（精确域名 + 后缀域名两种写法）
ALLOWED_IMAGE_HOSTS = {"image.tmdb.org"}
# 后缀匹配：豆瓣图床按 img1~img9.doubanio.com 分片，用后缀统一放行
ALLOWED_IMAGE_SUFFIXES = ("doubanio.com",)
# 部分图床校验防盗链 Referer（豆瓣 418），按后缀注入对应来源页
REFERER_BY_SUFFIX = {"doubanio.com": "https://movie.douban.com/"}


def _host_allowed(host: str) -> bool:
    return host in ALLOWED_IMAGE_HOSTS or host.endswith(ALLOWED_IMAGE_SUFFIXES)


def rewrite_poster_url(url: str | None) -> str | None:
    """把 TMDB 图片 URL 改写成本地代理路径，其他域名原样返回。

    在序列化层（_to_movie_hit）统一调用，前端拿到的 poster_url
    已经是 /api/v1/img?...，零改动兼容。
    """
    if not url:
        return url
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return url
    if _host_allowed(host):
        from urllib.parse import quote

        return f"/api/v1/img?url={quote(url, safe='')}"
    return url


@router.get("")
async def image_proxy(url: str = Query(..., description="要代理的图片完整 URL")) -> Response:
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    host = (parts.hostname or "").lower()
    if scheme not in ("http", "https") or not _host_allowed(host):
        raise HTTPException(status_code=400, detail=f"仅允许代理 {', '.join(sorted(ALLOWED_IMAGE_HOSTS))} 等白名单图床的图片")

    # 先走配置的代理出口，失败再试直连（机器有直连能力时不因代理挂了而裂图）
    candidates: list[str | None] = []
    if settings.image_fetch_proxy and settings.image_fetch_proxy.lower() != "direct":
        candidates.append(settings.image_fetch_proxy)
    candidates.append(None)

    last_exc: Exception | None = None
    # 防盗链：命中后缀规则的图床需要带来源页 Referer，否则 418
    headers = {}
    for suffix, ref in REFERER_BY_SUFFIX.items():
        if host.endswith(suffix):
            headers["Referer"] = ref
            break

    for proxy in candidates:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except (httpx.HTTPError, httpx.StreamError) as exc:  # noqa: PERF203
            last_exc = exc

    raise HTTPException(status_code=502, detail=f"图片源暂时不可用：{type(last_exc).__name__}")
