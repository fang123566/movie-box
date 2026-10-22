"""
阶段 5 前 · 趣味功能接口。

| 接口 | 玩法 |
|---|---|
| `POST /api/v1/fun/mix` | 类型混搭器：同时具备 N 种类型的影片（科幻+喜剧=科幻喜剧） |
| `GET  /api/v1/fun/box` | 随机盲盒：抽一部 ≥7 分的片，种子可复现 |
| `GET  /api/v1/fun/map` | 足迹地图：全库取景地/故事发生地坐标 |
| `GET  /api/v1/fun/map/movies` | 地点对应的影片列表（地图信息窗按需拉取） |

这三个是"检索能力的玩具化"——查询都不新，新的是打开方式。
答辩演示动线：混搭器展示筛选深度 → 盲盒展示随机性 → 地图展示数据维度。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.v1.errors import es_unavailable
from backend.schemas.fun import (
    BlindBoxResponse,
    MapMoviesResponse,
    MapResponse,
    MixRequest,
)
from backend.schemas.search import MovieSearchResponse
from backend.services.fun_service import (
    blind_box,
    location_map,
    location_movies,
    mix_movies,
)
from backend.services.search_service import SearchUnavailable
from common.ttl_cache import cache

router = APIRouter()


@router.post("/mix", response_model=MovieSearchResponse, summary="类型混搭器")
async def mix(req: MixRequest) -> MovieSearchResponse:
    """找出**同时具备**所有指定类型的影片。

    服务层把 genre_op 硬编码为 "and"：混搭器的定义就是 AND，
    不信任客户端传上来的 op（传 "or" 就名不副实了）。
    结果为空时 note 会说明"没有同时命中的影片"并建议放宽条件。
    """
    try:
        return await mix_movies(req.genres, req.rating_min, req.year_from,
                                req.year_to, req.size)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/box", response_model=BlindBoxResponse, summary="随机盲盒")
async def box(
    seed: int | None = Query(default=None, description="随机种子；同一个种子抽同一部片"),
    genres: list[str] = Query(default=[], description="限定类型池，如 ?genres=科幻&genres=喜剧"),
    min_rating: float | None = Query(default=7.0, ge=0, le=10,
                                     description="候选池最低分；null 表示不设门槛"),
) -> BlindBoxResponse:
    """抽一部随机影片。候选池 = 全部影片（可按类型/最低分圈定），
    在池子里用 random_score 抽签。

    seed 的设计意图：演示时导演先抽、观众再抽，同一个 seed 出同一部片，
    "我们的随机是可复现的随机"本身就是个讲解点。
    """
    try:
        return await blind_box(seed=seed, genres=genres or None,
                               min_rating=min_rating)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/map", response_model=MapResponse, summary="足迹地图")
async def map_locations() -> MapResponse:
    """全库带坐标的拍摄地 / 故事发生地（nested 聚合）。

    前端拿 points 直接往地图上打点，kind 区分取景地（filming）和
    故事发生地（narrative）。缺坐标的地点不计入 points，
    但数量会在 skipped_no_coords 里如实交代。
    ★ 缓存：nested 聚合扫全库 locations，数据不随用户变，进 TTL 缓存。
    """
    try:
        return await cache.get_or_set("fun:map", location_map)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/map/movies", response_model=MapMoviesResponse, summary="地点对应的影片")
async def map_movies(
    name: str = Query(..., description="地点名，与 /fun/map 返回的 point.name 完全一致"),
    size: int = Query(default=10, ge=1, le=50, description="返回影片数（按评分倒序）"),
) -> MapMoviesResponse:
    """地图信息窗点开标记后拉这个地点的影片列表。

    为什么不并进 /fun/map：地图接口一次拉全量点位，每点再挂 10 部
    影片响应体积翻几倍，而用户同一时刻只点开一个标记 —— 按需拉取。
    不进 TTL 缓存：查询随 name 变化，且 nested term 是轻查询。
    """
    try:
        return await location_movies(name, size)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc
