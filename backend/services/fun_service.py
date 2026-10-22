"""
趣味功能服务：混搭器 / 随机盲盒 / 足迹地图。

这三个功能都不引入新算法，是已有能力的玩具化包装：
混搭器 = 检索（genre_op=and 强制AND）、盲盒 = 检索（random_score）、
地图 = 聚合（nested terms）。逻辑轻，但每个都踩过一个真坑，
注释里写清楚，免得后来人"优化"回去。
"""
from __future__ import annotations

import time

from backend.schemas.fun import (
    BlindBoxResponse,
    MapMoviesResponse,
    MapPoint,
    MapResponse,
)
from backend.schemas.search import MovieSearchRequest, MovieSearchResponse
from backend.services import country_coords
from backend.services.query_builder import build_locations_aggs, build_random_query
from backend.services.search_service import SearchUnavailable, _to_movie_hit, search_movies
from common.es_client import get_es
from common.settings import settings

# 盲盒默认只抽 7 分以上的 —— "随机"负责惊喜，"门槛"负责底线。
# 纯随机的盲盒会抽到 3 分烂片，demo 现场抽一次冷场一次。
BLIND_BOX_MIN_RATING = 7.0


async def mix_movies(req_genres: list[str], rating_min: float | None,
                     year_from: int | None, year_to: int | None,
                     size: int) -> MovieSearchResponse:
    """类型混搭器：同时具备所有类型的影片。

    直接复用检索服务，只做一件事：把 genre_op 硬编码成 "and"。
    ★ 为什么在服务层强制而不是信任客户端传 genre_op？
        混搭器的定义就是 AND。客户端传 "or" 上来，语义就成了普通筛选，
        页面标题却还写着"混搭"——接口要对得起自己的名字。
    """
    search_req = MovieSearchRequest(
        genres=req_genres,
        genre_op="and",
        rating_min=rating_min,
        year_from=year_from,
        year_to=year_to,
        size=size,
        with_facets=True,
    )
    resp = await search_movies(search_req)
    if resp.meta.total == 0:
        resp.note = (f"没有同时具备「{'、'.join(req_genres)}」全部类型的影片"
                     f"（可减少一个类型再试，或放宽评分/年代限制）")
    return resp


async def blind_box(
    seed: int | None = None,
    genres: list[str] | None = None,
    min_rating: float | None = BLIND_BOX_MIN_RATING,
) -> BlindBoxResponse:
    """随机盲盒：抽一部片。seed 缺省用当前毫秒时间戳。

    筛选（类型 / 最低分）作用于候选池：先圈定池子，再在池子里随机。
    顺序反了（先随机再筛）在 ES 里表达不了，而且结果分布也不对。
    """
    if seed is None:
        seed = int(time.time() * 1000) % (2**31)

    filters: list[dict] = []
    if genres:
        filters.append({"terms": {"genres_zh": genres}})
    if min_rating is not None:
        filters.append({"range": {"vote_average": {"gte": min_rating}}})

    try:
        es = get_es().options(request_timeout=10)
        resp = await es.search(index=settings.es_index_movies,
                               **build_random_query(seed, filters, 1))
    except Exception as exc:  # noqa: BLE001
        raise SearchUnavailable(f"{type(exc).__name__}: {exc}") from exc

    hits = resp["hits"]["hits"]
    if not hits:
        scope = "、".join(genres) + "类 " if genres else ""
        return BlindBoxResponse(
            movie=None, seed=seed,
            note=f"{scope}{min_rating} 分以上的影片一部都没抽到——条件太苛刻了，降降门槛试试",
        )
    return BlindBoxResponse(movie=_to_movie_hit(hits[0]), seed=seed)


async def location_map() -> MapResponse:
    """足迹地图：全库带坐标的拍摄地/故事发生地。

    ★ 这里有一个 ES 的经典坑，测试时踩了：
        `exists: {field: filming_locations}` 在 **nested** 字段上返回 0 命中，
        即使数据明明白白在那里。exists 不看 nested 子文档，
        要查必须写 nested 查询包一层 exists。所以本接口不做
        "先 exists 判空再聚合"的优化，直接聚合一发入魂。
    """
    try:
        es = get_es().options(request_timeout=15)
        resp = await es.search(index=settings.es_index_movies, size=0,
                               aggs=build_locations_aggs())
    except Exception as exc:  # noqa: BLE001
        raise SearchUnavailable(f"{type(exc).__name__}: {exc}") from exc

    buckets = (resp.get("aggregations", {}).get("locations", {})
               .get("by_name", {}).get("buckets") or [])
    points: list[MapPoint] = []
    skipped = 0
    for b in buckets:
        lat = (b.get("lat") or {}).get("value")
        lon = (b.get("lon") or {}).get("value")
        if lat is None or lon is None:
            skipped += 1          # 有地名没坐标，地图画不出来，但要计数说明
            continue
        kinds = [k["key"] for k in (b.get("kinds", {}).get("buckets") or [])]
        points.append(MapPoint(
            name=str(b["key"]),
            kind=kinds[0] if kinds else None,
            lat=round(float(lat), 4),
            lon=round(float(lon), 4),
            movies=int(b["doc_count"]),
        ))
    points.sort(key=lambda p: -p.movies)

    # ---- 兜底层：拍摄地 0 点位时，退到「制作国家」聚合 ----
    # 优先级见需求清单：Wikidata P915 拍摄地 > 故事发生地 > TMDB 制作国家。
    # Wikidata 被限流（429）或未采集时，地图不该是全空的。
    country_fallback = False
    if not points:
        country_fallback = True
        try:
            resp2 = await es.search(
                index=settings.es_index_movies, size=0,
                aggs={"countries": {"terms": {"field": "production_countries", "size": 60}}},
            )
        except Exception:  # noqa: BLE001 - 兜底失败也返回空点位，不掩盖主流程
            resp2 = {}
        for b in (resp2.get("aggregations", {}).get("countries", {}).get("buckets") or []):
            hit = country_coords.lookup(str(b["key"]))
            if not hit:
                continue
            lat, lon, zh = hit
            points.append(MapPoint(
                name=zh, kind="country",
                lat=round(lat, 4), lon=round(lon, 4),
                movies=int(b["doc_count"]),
            ))
        points.sort(key=lambda p: -p.movies)

    note = None
    if country_fallback and points:
        note = ("当前展示的是【制作国家】点位（Wikidata 拍摄地暂缺：采集时被限流，"
                "重新跑 ingest.run_collect wiki 后可点亮精确拍摄地）")
    elif not points:
        note = ("库里还没有带坐标的拍摄地。坐标在 ingest 阶段从 Wikidata 取，"
                "重新跑 ingest 并确认 wikidata_coords 产物后即可点亮地图")
    elif skipped:
        note = f"另有 {skipped} 个地点缺少坐标，未出现在地图上"
    return MapResponse(points=points, total_points=len(points),
                       skipped_no_coords=skipped, note=note)


async def location_movies(name: str, size: int = 10) -> MapMoviesResponse:
    """某个地点关联的影片列表（地图信息窗用）。

    查询走 nested term 精确匹配 filming_locations.name.kw：
    · keyword 子字段不分词，「伦敦」不会误命中「伦敦桥」；
    · 按评分倒序取前 size 部 —— 信息窗寸土寸金，先给好看的。
    total 用 track_total_hits 拿真实总数（默认 10000 封顶对 488 部片库够用，
    但显式要真的更诚实）。
    """
    query = {
        "bool": {
            "filter": [{
                "nested": {
                    "path": "filming_locations",
                    "query": {"term": {"filming_locations.name.kw": name}},
                },
            }],
        }
    }
    body = {
        "size": size,
        "track_total_hits": True,
        "query": query,
        "sort": [{"vote_average": {"order": "desc", "missing": "_last"}}],
    }
    try:
        es = get_es().options(request_timeout=10)
        resp = await es.search(index=settings.es_index_movies, **body)
    except Exception as exc:  # noqa: BLE001
        raise SearchUnavailable(f"{type(exc).__name__}: {exc}") from exc

    total = resp.get("hits", {}).get("total", {}).get("value", 0)
    hits = [_to_movie_hit(h) for h in resp.get("hits", {}).get("hits", [])]
    return MapMoviesResponse(name=name, total=total, hits=hits)
