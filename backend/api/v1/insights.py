"""
阶段 4 · 洞察接口。

| 接口 | 用途 |
|---|---|
| `POST /api/v1/insights/sentiment` | 任意文本情感打分（返回每个命中词，可解释） |
| `GET  /api/v1/insights/sentiment` | 全局情感分布 + 各类型均分（大屏用） |
| `GET  /api/v1/insights/topics` | 主题词榜：观众在夸什么 / 骂什么 |
| `GET  /api/v1/insights/lexicon` | 学出来的情感词典本身（答辩演示用） |
| `GET  /api/v1/insights/trends` | 年代趋势：每十年影片数与均分（折线图） |
| `GET  /api/v1/insights/matrix` | 类型×年代矩阵：大屏动态图表（竞赛/排名/流向）数据源 |
| `GET  /api/v1/insights/box-office` | 票房分析：TOP 影片画廊 + 年度票房趋势 |
| `GET  /api/v1/insights/movies/{id}` | 单片画像：关键词 + 类型口碑参考 |

★ 这些接口的数据从哪来？
    情感分布走 Elasticsearch 聚合（实时、真数据）；
    主题榜 / 词典 / 单片关键词走**分析层产物文件**
    （data_lake/analysis/*.json），带 mtime 缓存，不会每个请求都重读一遍。
    产物缺失时返回 503 并告诉用户该跑哪条命令 —— 不返回空数组假装正常。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.api.v1.errors import es_unavailable as _guard
from backend.api.v1.img import rewrite_poster_url
from backend.schemas.insights import (
    GenreRating,
    BoxOfficeItem,
    BoxOfficeResponse,
    BoxOfficeYearBucket,
    KeywordItem,
    MatrixCell,
    MatrixResponse,
    MatrixRow,
    MovieInsight,
    PolarizingItem,
    PolarizingResponse,
    Quote,
    RegionItem,
    RegionsResponse,
    ScoreRequest,
    ScoreResponse,
    SentimentBucket,
    SentimentStats,
    StoryCard,
    StoryFact,
    StoryResponse,
    TopicItem,
    TopicsResponse,
    TrendBucket,
    TrendsResponse,
    WordHit,
)
from backend.services.query_builder import (
    build_box_office_years,
    build_decade_aggs,
    build_genre_decade_matrix,
    build_polarizing,
    build_regions,
)
from backend.services.search_service import SearchUnavailable, get_movie
from common.es_client import get_es
from common.settings import settings
from common.ttl_cache import cache

router = APIRouter()


def _artifact(name: str) -> Path:
    return settings.lake("analysis", name)


# ============================================================
# 产物文件缓存
# ============================================================

# 产物是"跑一次分析就固定"的文件，没必要每个请求都解析一遍 JSON。
# 缓存键 = (路径, mtime, size)：文件被重新生成后 mtime 变化，缓存自动失效。
_CACHE: dict[str, tuple[tuple, Any]] = {}


def _load_artifact(name: str, what: str) -> Any:
    path = _artifact(name)
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"分析产物 {name} 不存在，{what}需要先跑分析层",
                "hint": "python -m analysis.run_analysis lexicon && "
                        "python -m analysis.run_analysis topics",
            },
        )
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"读取 {name} 失败：{exc}") from exc

    hit = _CACHE.get(name)
    if hit and hit[0] == key:
        return hit[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"解析 {name} 失败：{exc}") from exc
    _CACHE[name] = (key, data)
    return data


def _load_lexicon():
    """读情感词典，返回 analysis.lexicon.Lexicon 对象。"""
    from analysis.lexicon import Lexicon

    data = _load_artifact("lexicon.json", "情感打分")
    return Lexicon(
        scores={str(k): float(v) for k, v in (data.get("scores") or {}).items()},
        lang=str(data.get("lang") or "en"),
        meta=data.get("meta") or {},
    )


# ============================================================
# 情感打分
# ============================================================


@router.post("/sentiment", response_model=ScoreResponse, summary="任意文本情感打分")
async def score_text(req: ScoreRequest) -> ScoreResponse:
    """给一段文本打情感分，并返回**每个命中的词**。

    这是阶段 4 的核心卖点：黑盒模型只能告诉你"这是负面"，
    我们能把"因为出现了 waste(-2.45)、poorly(-1.90) 所以判负面"摊开给人看。
    前端把 hits 渲染成高亮词，答辩时现场粘一条影评就能演示。
    """
    from analysis.sentiment import label_of, score_text as _score

    lex = _load_lexicon()
    lang = None if req.lang == "auto" else req.lang
    res = _score(req.text, lex, lang=lang)

    # ★ 只回报"有分量"的命中词。
    #   词典是从语料里归纳的，the / of / and 这类功能词也会入典（分数≈0）。
    #   全量返回的话，一句 "a total waste of time" 会报 19 个命中词，
    #   其中 12 个是虚词 —— 解释性反而变差。
    #   阈值 0.05 与 sentiment.py 的 neutral 判定阈值保持一致：
    #   一个词连 neutral 都判不出来，就没必要拿出来解释。
    hits = [
        WordHit(word=w, weight=weight, lexicon_score=round(lex.scores.get(w, 0.0), 4))
        for w, weight in res.hits
        if abs(weight) >= 0.05
    ]
    note = None
    if not hits:
        note = "文本里没有命中词典中有分量的情感词，分数接近 0 属正常结果"
    return ScoreResponse(
        score=res.score,
        label=label_of(res.score),
        lang=req.lang,
        hits=hits,
        matched_words=len(hits),
        note=note,
    )


@router.get("/sentiment", response_model=SentimentStats, summary="全局情感分布与类型口碑")
async def sentiment_stats() -> SentimentStats:
    """影评情感分布（ES 聚合）+ 各类型均分（电影侧）。

    ★ 缓存：这是大屏的心脏接口，两个 ES 聚合（reviews 情感分面 +
      movies 类型口碑）不随用户变，进 TTL 缓存（默认 5 分钟）。
      单片画像（/movies/{id}）内部也调它，顺带受益。
    """
    async def _produce() -> SentimentStats:
        try:
            es = get_es().options(request_timeout=15)
            # 影评情感分面：reviews 索引上的 terms 聚合。
            # ★ track_total_hits=True 不能省 —— ES 7+ 默认只精确统计到 1 万条，
            #   影评有 4.99 万条，不写这个 hits.total 会停在 10000，
            #   正面率直接算成 250%（25078/10000）。阶段 3 在影评检索上踩过一次。
            rev = await es.search(
                index=settings.es_index_reviews,
                size=0,
                track_total_hits=True,
                aggs={"sentiment": {"terms": {"field": "sentiment", "size": 10,
                                              "missing": "unknown"}}},
            )
            # 类型口碑：movies 索引上按类型分组求均分
            mov = await es.search(
                index=settings.es_index_movies,
                size=0,
                aggs={"genres": {
                    "terms": {"field": "genres_zh", "size": 12, "min_doc_count": 5},
                    "aggs": {
                        "avg_rating": {"avg": {"field": "vote_average"}},
                        "avg_votes": {"avg": {"field": "vote_count"}},
                    },
                }},
            )
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        rev_total = int((rev["hits"]["total"] or {}).get("value") or 0)
        buckets = [SentimentBucket(key=str(b["key"]), count=int(b["doc_count"]))
                   for b in rev["aggregations"]["sentiment"]["buckets"]]
        pos = sum(b.count for b in buckets if b.key == "positive")

        by_genre = []
        for b in mov.get("aggregations", {}).get("genres", {}).get("buckets", []):
            by_genre.append(GenreRating(
                genre=str(b["key"]),
                movies=int(b["doc_count"]),
                avg_rating=(round(b["avg_rating"]["value"], 2)
                            if b.get("avg_rating", {}).get("value") is not None else None),
                avg_votes=(int(b["avg_votes"]["value"])
                           if b.get("avg_votes", {}).get("value") is not None else None),
            ))
        by_genre.sort(key=lambda g: -(g.avg_rating or 0))

        return SentimentStats(
            total=rev_total,
            buckets=buckets,
            positive_ratio=round(pos / rev_total, 4) if rev_total else 0.0,
            by_genre=by_genre,
        )

    try:
        return await cache.get_or_set("insights:sentiment", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/trends", response_model=TrendsResponse, summary="年代趋势（影片数与均分）")
async def trends() -> TrendsResponse:
    """按十年一桶统计影片数与平均评分，替代原系统的「数据趋势分析」图位。

    聚合构造在 query_builder.build_decade_aggs()（纯函数，可离线自检），
    这里只负责执行 + 把 ES 的浮点桶 key 转成 int 年代。
    ★ 缓存：histogram 聚合扫全库，结果不随用户变，进 TTL 缓存。
    """
    async def _produce() -> TrendsResponse:
        try:
            es = get_es().options(request_timeout=15)
            resp = await es.search(
                index=settings.es_index_movies,
                size=0,
                track_total_hits=True,
                aggs=build_decade_aggs(),
            )
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        total = int((resp["hits"]["total"] or {}).get("value") or 0)
        buckets = [
            TrendBucket(
                decade=int(b["key"]),
                movies=int(b["doc_count"]),
                avg_rating=(round(b["avg_rating"]["value"], 2)
                            if b.get("avg_rating", {}).get("value") is not None else None),
            )
            for b in resp.get("aggregations", {}).get("by_decade", {}).get("buckets", [])
        ]
        with_year = sum(b.movies for b in buckets)
        note = None
        if total and with_year < total:
            note = f"{total - with_year} 部影片缺年份字段，未计入趋势"
        return TrendsResponse(total_movies=total, with_year=with_year,
                              buckets=buckets, note=note)

    try:
        return await cache.get_or_set("insights:trends", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/matrix", response_model=MatrixResponse, summary="类型×年代矩阵（动态图表数据源）")
async def genre_decade_matrix() -> MatrixResponse:
    """类型 × 年代二维矩阵，供大屏的 Flourish 式动态图表（条形竞赛 / 排名变化 / 桑基流向）。

    聚合构造在 query_builder.build_genre_decade_matrix()（纯函数，可离线自检），
    这里只负责执行 + 把嵌套桶摊平成行。
    ★ 缓存：与 trends 同性质的聚合，进 TTL 缓存（默认 5 分钟）。
    """
    async def _produce() -> MatrixResponse:
        try:
            es = get_es().options(request_timeout=15)
            resp = await es.search(
                index=settings.es_index_movies,
                size=0,
                track_total_hits=True,
                aggs=build_genre_decade_matrix(),
            )
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        rows: list[MatrixRow] = []
        decades: set[int] = set()
        for b in resp.get("aggregations", {}).get("by_genre", {}).get("buckets", []):
            cells: list[MatrixCell] = []
            for d in b.get("by_decade", {}).get("buckets", []):
                decade = int(d["key"])
                decades.add(decade)
                cells.append(MatrixCell(
                    decade=decade,
                    movies=int(d["doc_count"]),
                    avg_rating=(round(d["avg_rating"]["value"], 2)
                                if d.get("avg_rating", {}).get("value") is not None else None),
                ))
            rows.append(MatrixRow(genre=str(b["key"]), total=int(b["doc_count"]), cells=cells))
        # 按总片数倒序：竞赛图里强者在前，弱类型自然沉底
        rows.sort(key=lambda r: -r.total)
        return MatrixResponse(decades=sorted(decades), rows=rows)

    try:
        return await cache.get_or_set("insights:matrix", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


# ============================================================
# 票房分析（2026-10-22 新增展厅，替代原「类型竞赛」）
# ============================================================


@router.get("/box-office", response_model=BoxOfficeResponse, summary="票房分析（画廊相框 + 年度趋势）")
async def box_office(
    top: int = Query(default=24, ge=6, le=60, description="画廊相框取票房前多少部"),
) -> BoxOfficeResponse:
    """票房分析展厅数据源：TOP 影片画廊（相框）+ 年度票房趋势（右翼图）。

    数据口径：仅统计 TMDB 给出 revenue 的影片（当前库约 242 部）。
    roi = revenue / budget —— 缺预算的老片留 None，不编数。
    ★ 缓存：与 matrix 同性质的 ES 聚合，进 TTL 缓存（默认 5 分钟）。
    """
    async def _produce() -> BoxOfficeResponse:
        es = get_es().options(request_timeout=15)
        # 1) 票房 TOP N：画廊相框内容
        try:
            top_resp = await es.search(
                index=settings.es_index_movies,
                size=top,
                track_total_hits=True,
                query={"bool": {"filter": [{"exists": {"field": "revenue"}}]}},
                sort=[{"revenue": "desc"}],
                _source=[
                    "title", "title_zh", "title_en", "release_year",
                    "poster_url", "revenue", "budget", "vote_average", "genres_zh",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        gallery: list[BoxOfficeItem] = []
        for hit in top_resp.get("hits", {}).get("hits", []):
            s = hit["_source"]
            revenue = int(s.get("revenue") or 0)
            budget = int(s["budget"]) if s.get("budget") else None
            roi = round(revenue / budget, 2) if budget else None
            gallery.append(BoxOfficeItem(
                movie_id=str(hit["_id"]),
                title=str(s.get("title_zh") or s.get("title") or ""),
                title_en=s.get("title_en"),
                year=s.get("release_year"),
                poster_url=s.get("poster_url"),
                revenue=revenue,
                budget=budget,
                roi=roi,
                vote_average=s.get("vote_average"),
                genres=list(s.get("genres_zh") or []),
            ))

        # 2) 年度票房趋势 + 总览（聚合构造在 query_builder，纯函数可离线自检）
        try:
            agg_resp = await es.search(
                index=settings.es_index_movies,
                **build_box_office_years(),
            )
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        aggs = agg_resp.get("aggregations", {})
        years: list[BoxOfficeYearBucket] = []
        for b in aggs.get("by_year", {}).get("buckets", []):
            key = b.get("key")
            if key is None or key == "":  # 缺年份的影片进 null 键桶，趋势图不画
                continue
            years.append(BoxOfficeYearBucket(
                year=int(key),
                revenue=int(b.get("rev", {}).get("value") or 0),
                movies=int(b.get("doc_count") or 0),
            ))
        years.sort(key=lambda y: y.year)

        total_movies = int(
            agg_resp.get("hits", {}).get("total", {}).get("value")
            or top_resp.get("hits", {}).get("total", {}).get("value")
            or 0
        )
        total_revenue = int(aggs.get("total_rev", {}).get("value") or 0)
        top_year = max(years, key=lambda y: y.revenue).year if years else None

        # 桶合计 vs 全局合计的差额 = 缺年份影片的票房，如实写进 note
        bucketed = sum(y.revenue for y in years)
        note = None
        if total_revenue and bucketed < total_revenue:
            no_year = total_revenue - bucketed
            note = (f"有 {no_year / 1e8:.2f} 亿美元票房来自缺年份字段的影片，"
                    f"未计入年度趋势图")

        return BoxOfficeResponse(
            total_movies=total_movies,
            total_revenue=total_revenue,
            top_year=top_year,
            gallery=gallery,
            years=years,
            note=note,
        )

    try:
        return await cache.get_or_set("insights:box-office", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


# ============================================================
# 主题 / 词典
# ============================================================


@router.get("/topics", response_model=TopicsResponse, summary="主题词榜")
async def topics(
    top: int = Query(default=20, ge=1, le=100, description="返回前多少个词"),
) -> TopicsResponse:
    """全局主题词榜：按"收缩后的对数提升度 × 证据量"排序。

    排序键的用意见 analysis/topics.py 的说明 —— 单纯按 lift 排，
    榜首会被只出现几十次的角色名霸占。
    """
    data = _load_artifact("topics.json", "主题统计")
    keywords = [
        TopicItem(
            word=str(d["word"]), df=int(d.get("df", 0)),
            df_positive=int(d.get("df_positive", 0)),
            df_negative=int(d.get("df_negative", 0)),
            lift=float(d.get("lift", 1.0)), side=str(d.get("side", "neutral")),
            weight=float(d.get("weight", 0.0)),
        )
        for d in (data.get("keywords") or [])[:top]
    ]
    return TopicsResponse(
        docs=int(data.get("docs", 0)),
        positive_docs=int(data.get("positive_docs", 0)),
        negative_docs=int(data.get("negative_docs", 0)),
        keywords=keywords,
        positive_vocabulary=list(data.get("positive_vocabulary") or []),
        negative_vocabulary=list(data.get("negative_vocabulary") or []),
    )


@router.get("/lexicon", summary="学出来的情感词典")
async def lexicon(
    top: int = Query(default=30, ge=1, le=200, description="正/负各取多少个词"),
) -> dict:
    """返回词典本身：最正面 / 最负面的各 top 个词 + 归纳时的统计信息。

    答辩时直接打开这个接口的返回，就能讲清"这部词典是从哪来的、
    学到了什么、有多少词"。
    """
    lex = _load_lexicon()
    return {
        "meta": lex.meta,
        "size": len(lex),
        "top_positive": [{"word": w, "score": s} for w, s in lex.top(top, positive=True)],
        "top_negative": [{"word": w, "score": s} for w, s in lex.top(top, positive=False)],
    }


@router.get("/movies/{movie_id}", response_model=MovieInsight, summary="单片画像")
async def movie_insight(movie_id: str) -> MovieInsight:
    """单片画像：电影自身信息 + 从它文本里提的关键词。"""
    try:
        movie = await get_movie(movie_id)
    except SearchUnavailable as exc:
        raise _guard(exc) from exc
    if movie is None:
        raise HTTPException(status_code=404, detail=f"找不到 movie_id={movie_id} 的电影")

    data = _load_artifact("movie_keywords.json", "单片画像")
    raw_kw = (data.get("movies") or {}).get(movie_id) or []
    keywords = [
        KeywordItem(word=str(d["word"]), tf=int(d.get("tf", 0)),
                    df=int(d.get("df", 0)), score=float(d.get("tfidf", 0.0)))
        for d in raw_kw
    ]

    # 口碑参考：该片所属类型的全局均分。一部片常有多个类型，
    # 只取匹配到的第一个做参考，字段名也写明是"参考"而不是该片的口碑。
    hint = None
    if movie.genres_zh:
        try:
            stats = await sentiment_stats()
        except HTTPException:
            stats = None
        for g in (stats.by_genre if stats else []):
            if g.genre in movie.genres_zh and g.avg_rating is not None:
                hint = f"「{g.genre}」类影片全局均分 {g.avg_rating}（{g.movies} 部）"
                break

    return MovieInsight(
        movie_id=movie.movie_id,
        title=movie.title,
        title_zh=movie.title_zh,
        year=movie.year,
        genres_zh=movie.genres_zh,
        director=movie.director,
        rating=movie.rating,
        votes=movie.votes,
        sources=movie.sources,
        keywords=keywords,
        sentiment_hint=hint,
    )


# ============================================================
# 口碑分化 / 地区画像 / 馆长洞察（2026-11-01 新增展厅分析）
# ============================================================

# 引文清洗：影评原文常带 markdown  emphasis / 链接推广，直接上大屏很脏。
_MD = re.compile(r"[*_>#`~]+")
_URL = re.compile(r"https?://\S+", re.I)
_SPAM = re.compile(r"check out my (full )?review|read my (full )?review|full review @", re.I)
_WS = re.compile(r"\s+")


def _clean_quote(text: str | None) -> str | None:
    """把一条影评原文洗成可上大屏的引文；太短则放弃。"""
    if not text:
        return None
    t = _MD.sub("", text)
    t = _URL.sub("", t)                 # 链接删掉（留着是一串乱码域名）
    t = _WS.sub(" ", t).strip(" .,;:!—-\t")
    if len(t) < 20:                      # 洗完后太短，不构成引文
        return None
    return t[:220]


def _pick_quote(hits: list[dict]) -> Quote | None:
    """top_hits 给了 3 条候选，挑第一条"干净"的（非推广文、清洗后够长）。"""
    for h in hits:
        s = h.get("_source") or {}
        if _SPAM.search(s.get("text") or ""):
            continue
        t = _clean_quote(s.get("text"))
        if t:
            return Quote(text=t, rating=s.get("rating"))
    return None


async def _movie_titles(ids: list[str]) -> dict[str, dict]:
    """按 movie_id 批量回 movies 索引取中英文名（分化榜的 id 是 IMDb tt 号）。"""
    if not ids:
        return {}
    try:
        es = get_es().options(request_timeout=15)
        resp = await es.search(
            index=settings.es_index_movies,
            size=len(ids),
            query={"terms": {"movie_id": ids}},
            _source=["movie_id", "title", "title_zh", "title_en", "release_year",
                     "director", "poster_url", "vote_average"],
        )
    except Exception:  # noqa: BLE001 —— 取名失败不致命，退回用 movie_id 显示
        return {}
    out: dict[str, dict] = {}
    for h in resp.get("hits", {}).get("hits", []):
        s = h.get("_source") or {}
        if s.get("movie_id"):
            out[s["movie_id"]] = s
    return out


@router.get("/polarizing", response_model=PolarizingResponse, summary="口碑分化榜（评分标准差 + 真实引文）")
async def polarizing() -> PolarizingResponse:
    """观众内部的分歧：同一部片，有人打满分有人打最低分。

    按评分标准差排序取前 10；每部附"评分最高的真实影评"（好评引文）与
    "评分最低的真实影评"（差评引文）——引文来自本片真实语料，非模板。
    ★ 缓存：扫全量关联影评的聚合，进 TTL 缓存（默认 5 分钟）。
    """
    async def _produce() -> PolarizingResponse:
        es = get_es().options(request_timeout=20)
        try:
            resp = await es.search(
                index=settings.es_index_reviews, **build_polarizing())
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        cand: list[dict] = []
        for b in resp.get("aggregations", {}).get("by_movie", {}).get("buckets", []):
            st = b.get("stats") or {}
            sd = st.get("std_deviation")
            cnt = int(st.get("count") or 0)
            if not sd or cnt < 8:
                continue
            pos_hits = (b.get("pos", {}).get("hit", {}).get("hits", {}).get("hits")) or []
            neg_hits = (b.get("neg", {}).get("hit", {}).get("hits", {}).get("hits")) or []
            cand.append({
                "movie_id": str(b["key"]), "review_count": cnt,
                "avg_rating": st.get("avg"), "std_dev": sd,
                "pos": _pick_quote(pos_hits), "neg": _pick_quote(neg_hits),
            })
        cand.sort(key=lambda c: -(c["std_dev"] or 0))

        total_qualified = len(cand)
        cand = cand[:10]
        titles = await _movie_titles([c["movie_id"] for c in cand])
        items = []
        for c in cand:
            t = titles.get(c["movie_id"]) or {}
            items.append(PolarizingItem(
                movie_id=c["movie_id"],
                title=str(t.get("title_zh") or t.get("title") or c["movie_id"]),
                title_en=t.get("title_en"),
                year=t.get("release_year"),
                director=t.get("director"),
                poster_url=rewrite_poster_url(t.get("poster_url")),
                vote_average=t.get("vote_average"),
                review_count=c["review_count"],
                avg_rating=(round(c["avg_rating"], 2)
                            if c["avg_rating"] is not None else None),
                std_dev=(round(c["std_dev"], 2)
                         if c["std_dev"] is not None else None),
                pos_quote=c["pos"], neg_quote=c["neg"],
            ))
        return PolarizingResponse(total_qualified=total_qualified, items=items)

    try:
        return await cache.get_or_set("insights:polarizing", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/regions", response_model=RegionsResponse, summary="地区画像（主出品国产量与口碑）")
async def regions() -> RegionsResponse:
    """各主出品国的影片数与均分对照（产量王 ≠ 口碑王的数据源）。

    ★ 缓存：全库 terms 聚合，进 TTL 缓存。
    """
    async def _produce() -> RegionsResponse:
        es = get_es().options(request_timeout=15)
        try:
            resp = await es.search(
                index=settings.es_index_movies, **build_regions())
        except Exception as exc:  # noqa: BLE001
            raise _guard(SearchUnavailable(f"{type(exc).__name__}: {exc}")) from exc

        items = [
            RegionItem(
                country=str(b["key"]),
                movies=int(b["doc_count"]),
                avg_rating=(round(b["avg_rating"]["value"], 2)
                            if b.get("avg_rating", {}).get("value") is not None else None),
                avg_votes=(int(b["avg_votes"]["value"])
                           if b.get("avg_votes", {}).get("value") is not None else None),
            )
            for b in resp.get("aggregations", {}).get("by_country", {}).get("buckets", [])
        ]
        items.sort(key=lambda i: -i.movies)
        return RegionsResponse(items=items)

    try:
        return await cache.get_or_set("insights:regions", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc


@router.get("/story", response_model=StoryResponse, summary="馆长洞察卡（大厅结论卡叠）")
async def story() -> StoryResponse:
    """大厅入口的三张结论卡：每卡一个分析发现，数据全部由各分析接口实时算出。

    设计成"容错组合"：某一路分析挂了只跳过那张卡，不让整叠卡消失。
    ★ 缓存：依赖的 polarizing/regions/sentiment 都是缓存的，这里再包一层短缓存。
    """
    async def _produce() -> StoryResponse:
        cards: list[StoryCard] = []

        try:
            pol = await polarizing()
            if pol.items:
                top = pol.items[0]
                cards.append(StoryCard(
                    kind="polarizing", kicker="口碑分化",
                    question="观众吵得最凶的一部片",
                    answer="同一部片，有人打满分，有人打最低分",
                    facts=[
                        StoryFact(k="影片", v=top.title),
                        StoryFact(k="评分波动", v=f"{top.std_dev:.2f}", big=True),
                        StoryFact(k="样本评价", v=f"{top.review_count} 条"),
                    ],
                    room="diverge",
                ))
        except HTTPException:
            pass

        try:
            reg = await regions()
            rated = [r for r in reg.items if r.avg_rating is not None]
            # 口碑王要有像样样本（>=8 部），否则 4 部小样本的 9.2 分没有说服力
            rated_sig = [r for r in rated if r.movies >= 8] or rated
            if reg.items and rated_sig:
                by_count = max(reg.items, key=lambda r: r.movies)
                by_rating = max(rated_sig, key=lambda r: r.avg_rating or 0)
                cards.append(StoryCard(
                    kind="regions", kicker="地区画像",
                    question="产量王 ≠ 口碑王",
                    answer="片子最多的国家，均分并不是最高",
                    facts=[
                        StoryFact(k="产量王", v=f"{by_count.country} · {by_count.movies} 部"),
                        StoryFact(k="口碑王", v=f"{by_rating.country} · {by_rating.avg_rating:.1f} 分",
                                  big=True),
                        StoryFact(k=f"{by_count.country}均分",
                                  v=f"{by_count.avg_rating:.2f} 分"),
                    ],
                    room="flow",
                ))
        except HTTPException:
            pass

        try:
            stats = await sentiment_stats()
            topics_data = _load_artifact("topics.json", "主题统计")
            pos_vocab = list(topics_data.get("positive_vocabulary") or [])
            neg_vocab = list(topics_data.get("negative_vocabulary") or [])
            cards.append(StoryCard(
                kind="sentiment", kicker="好评风向",
                question="观众最常说的好评词",
                answer="归纳式情感分析 · 5 万条真实语料",
                facts=[
                    StoryFact(k="正面率", v=f"{stats.positive_ratio * 100:.0f}%", big=True),
                    StoryFact(k="最热好评词", v=pos_vocab[0] if pos_vocab else "—"),
                    StoryFact(k="最热差评词", v=neg_vocab[0] if neg_vocab else "—"),
                ],
                room="galaxy",
            ))
        except HTTPException:
            pass

        return StoryResponse(cards=cards)

    try:
        return await cache.get_or_set("insights:story", _produce)
    except SearchUnavailable as exc:
        raise es_unavailable(exc) from exc
