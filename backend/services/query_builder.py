"""
查询构建器 —— 把检索参数翻译成 Elasticsearch DSL。

★ 这个文件**不联网、不碰 ES、没有副作用**，全是纯函数。
  所以检索逻辑（权重怎么配、分面怎么算、排序怎么退化）全都可以离线自检，
  不需要先起 ES 再拿 curl 一点点试。

★ 三个核心设计：

1. **混合检索 = 召回 + 精度提升**
   只写一句 multi_match 的话，"流浪地球" 会被切成 流浪/地球 两个词分别匹配，
   一部叫《地球脉动》的纪录片可能排在《流浪地球》前面。
   所以这里用 bool.should 组合两段：
     · multi_match best_fields —— 负责**召回**（任一字段命中都算）
     · match_phrase 精确短语 —— 负责**精度**（整句命中额外加权，把真命中的顶上来）
   这就是"混合"的含义：不是只换一个查询类型，而是把两种信号叠加打分。

2. **分面用 post_filter，而不是塞进 query**
   塞进 query 的话，聚合只统计"筛选后"的文档 —— 用户点了「科幻」之后，
   类型分面里就再也看不到「喜剧」了，筛选器把自己锁死（facet self-locking）。
   放进 post_filter 后，聚合算的是"关键词命中的全集"，每个分面项都还能看到自己剩多少。

3. **分面之间互相排除（drill-down）**
   光有 post_filter 还不够：选了「科幻」之后，类型分面里「喜剧」的计数
   会被"必须含科幻"这个条件压掉，看不到"换成喜剧会有多少部"。
   所以每个分面在统计时，只应用**其它分面**的条件，排除它自己那条 ——
   `build_facet_aggs()` 就是干这个的。电商筛选栏的标准行为。
"""
from __future__ import annotations

from backend.schemas.search import (
    MovieSearchRequest,
    Order,
    ReviewSearchRequest,
    SortKey,
)

# ============================================================
# 字段权重：命中不同字段，贡献不同的分数
# ============================================================
# 权重的直觉：**越短越具体的字段越可信**。
# 片名里出现检索词，几乎一定相关；简介里出现，可能只是顺带提了一句。
# 中文片名和英文片名同权 —— 用户用哪种语言搜都该有一样的效果。
MOVIE_TEXT_FIELDS: list[tuple[str, float]] = [
    ("title", 6.0),
    ("title_zh", 6.0),
    ("title_en", 4.0),
    ("original_title", 3.0),
    ("director", 3.0),
    ("cast", 2.0),
    ("keywords", 2.0),
    ("genres_zh", 1.5),
    ("overview", 1.0),
    ("wikipedia_extract", 0.8),
    ("tagline", 0.5),
]


def _weighted_fields() -> list[str]:
    """转成 ES 认识的 "字段名^权重" 形式。"""
    return [f"{name}^{boost}" for name, boost in MOVIE_TEXT_FIELDS]


# ============================================================
# 关键词查询
# ============================================================

def build_keyword_query(q: str | None, mode: str = "best") -> dict:
    """构造关键词部分。q 为空则返回 match_all（浏览模式）。"""
    if not q or not q.strip():
        return {"match_all": {}}

    text = q.strip()
    fields = _weighted_fields()

    # phrase 模式：搜索框联想用。phrase_prefix 允许最后一个词只输一半
    # （输"流浪地"也能联想到《流浪地球》）。
    if mode == "phrase":
        return {
            "multi_match": {
                "query": text,
                "fields": fields,
                "type": "phrase_prefix",
                "max_expansions": 20,
            }
        }

    should: list[dict] = [
        # 召回层：任一字段命中即算，tie_breaker 让"多个字段都命中"的排更前
        {
            "multi_match": {
                "query": text,
                "fields": fields,
                "type": "best_fields",
                "operator": "or",
                "tie_breaker": 0.3,
            }
        },
        # 精度层：整句连续命中，大幅加权，把真正命中的顶到最前
        {"match_phrase": {"title": {"query": text, "boost": 5.0}}},
        {"match_phrase": {"title_zh": {"query": text, "boost": 5.0}}},
        {"match_phrase": {"title_en": {"query": text, "boost": 2.5}}},
        {"match_phrase": {"director": {"query": text, "boost": 2.0}}},
    ]

    if mode == "cross":
        # cross_fields：要求检索词**分散命中多个字段**才算（"诺兰 科幻" 这种组合词）。
        # 注意：各字段分析器不同时 ES 会退化成按分析器分组，效果打折 ——
        # 所以它是可选项而不是默认项。
        should.append({
            "multi_match": {
                "query": text,
                "fields": fields,
                "type": "cross_fields",
                "operator": "and",
                "boost": 0.5,
            }
        })

    return {"bool": {"should": should, "minimum_should_match": 1}}


# ============================================================
# 筛选条件：按"分面"分组
# ============================================================
# 返回 {分面名: [ES 子句, ...]}。按分面分组是为了后面做"分面互相排除"——
# 统计某个分面时，要把它自己那组子句拿掉。

def build_filter_clauses(req: MovieSearchRequest) -> dict[str, list[dict]]:
    clauses: dict[str, list[dict]] = {}

    if req.genres:
        if req.genre_op == "and" and len(req.genres) > 1:
            # 必须同时具备所有类型 —— 阶段 6「类型混搭器」就是这个条件
            clauses["genres"] = [{"term": {"genres_zh": g}} for g in req.genres]
        else:
            clauses["genres"] = [{"terms": {"genres_zh": req.genres}}]

    if req.countries:
        # 国家筛选只按主出品国算（不带合拍国）——
        # 《毒液》制片国含中国（腾讯联合出品），但用户语义上它是美国片。
        # 分面口径与 FACET_COUNTRIES 字段一致，见 MOVIE_FACETS 注释。
        clauses["countries"] = [{"terms": {"primary_country": req.countries}}]
    if req.languages:
        clauses["languages"] = [{"terms": {"spoken_languages": req.languages}}]

    if getattr(req, "sources", None):
        # 数据来源分面的筛选条件。分面名与 MOVIE_FACETS 里的 "sources" 对齐，
        # build_facet_aggs 才会在统计时正确排除它自己（分面互相排除）。
        clauses["sources"] = [{"terms": {"sources": req.sources}}]

    if req.year_from is not None or req.year_to is not None:
        rng: dict = {}
        if req.year_from is not None:
            rng["gte"] = req.year_from
        if req.year_to is not None:
            rng["lte"] = req.year_to
        clauses["years"] = [{"range": {"release_year": rng}}]

    if req.rating_min is not None or req.rating_max is not None:
        rng = {}
        if req.rating_min is not None:
            rng["gte"] = req.rating_min
        if req.rating_max is not None:
            rng["lte"] = req.rating_max
        clauses["rating"] = [{"range": {"vote_average": rng}}]

    if req.runtime_min is not None or req.runtime_max is not None:
        rng = {}
        if req.runtime_min is not None:
            rng["gte"] = req.runtime_min
        if req.runtime_max is not None:
            rng["lte"] = req.runtime_max
        clauses["runtime"] = [{"range": {"runtime": rng}}]

    # 数据质量筛选：前端不想展示没海报/没简介的卡片
    quality: list[dict] = []
    if req.require_poster:
        quality.append({"exists": {"field": "poster_url"}})
    if req.require_overview:
        quality.append({"exists": {"field": "overview"}})
    if req.multi_source_only:
        quality.append({"term": {"is_multi_source": True}})
    if quality:
        clauses["quality"] = quality

    return clauses


def _flatten(clauses: dict[str, list[dict]], *, exclude: str | None = None) -> list[dict]:
    """把分组子句摊平成一维列表；exclude 用于排除某个分面自己的条件。"""
    out: list[dict] = []
    for name, items in clauses.items():
        if name == exclude:
            continue
        out.extend(items)
    return out


def build_post_filter(clauses: dict[str, list[dict]]) -> dict | None:
    """全部筛选条件（用于筛结果）。无条件时返回 None，让 DSL 更干净。"""
    flat = _flatten(clauses)
    if not flat:
        return None
    return {"bool": {"filter": flat}}


# ============================================================
# 分面聚合
# ============================================================

# (分面名, ES 字段, 中文标签, 桶数量, 类型)
# 注意：这里**不放**「数据来源（sources）」分面 —— legacy/tmdb/wikidata 是内部血缘
# 术语，对检索用户是噪音（阶段 7 走查用户反馈后移除）；筛选能力仍在 API 层保留。
MOVIE_FACETS: list[tuple[str, str, str, int, str]] = [
    ("genres", "genres_zh", "类型", 20, "terms"),
    # countries 用 primary_country（主出品国口径，2026-10-20 定调）：
    # 合拍片只在主出品国下出现一次，避免《毒液》这类片同时挂中美两国
    ("countries", "primary_country", "出品国家/地区", 15, "terms"),
    ("languages", "spoken_languages", "语言", 10, "terms"),
    ("years", "release_year", "年份", 30, "terms_desc"),
    ("rating", "vote_average", "评分", 6, "range"),
]

REVIEW_FACETS: list[tuple[str, str, str, int, str]] = [
    ("sentiment", "sentiment", "情感倾向", 5, "terms"),
    ("dataset", "dataset", "数据集", 5, "terms"),
    ("length", "word_count", "篇幅", 4, "range"),
]

# 评分区间：不能用 terms（浮点数值千奇百怪，分面会碎成几百个桶）
RATING_RANGES: list[dict] = [
    {"key": "9 分以上", "from": 9.0},
    {"key": "8 ~ 9 分", "from": 8.0, "to": 9.0},
    {"key": "7 ~ 8 分", "from": 7.0, "to": 8.0},
    {"key": "6 ~ 7 分", "from": 6.0, "to": 7.0},
    {"key": "6 分以下", "to": 6.0},
]

# 影评篇幅区间
LENGTH_RANGES: list[dict] = [
    {"key": "长评（500 词以上）", "from": 500},
    {"key": "中评（200 ~ 500 词）", "from": 200, "to": 500},
    {"key": "短评（50 ~ 200 词）", "from": 50, "to": 200},
    {"key": "微评（50 词以内）", "to": 50},
]

RANGES_BY_FACET = {"rating": RATING_RANGES, "length": LENGTH_RANGES}


def build_facet_aggs(
    clauses: dict[str, list[dict]],
    facets: list[tuple[str, str, str, int, str]],
) -> dict:
    """构造分面聚合。

    每个分面都被包在一个 filter 聚合里，filter 的内容是**其它分面**的条件，
    唯独排除它自己 —— 这就是"分面互相排除"：
    选了「科幻」之后，类型分面里依然能看到「喜剧：42 部」。

    即使没有任何筛选条件，也统一包一层 match_all 的 filter，
    这样读结果时路径固定是 `aggs[name].top.buckets`，不用分情况。
    """
    aggs: dict = {}
    for name, field, _label, size, kind in facets:
        others = _flatten(clauses, exclude=name)
        wrapper: dict = (
            {"bool": {"filter": others}} if others else {"match_all": {}}
        )

        if kind == "range":
            sub = {"range": {"field": field, "ranges": RANGES_BY_FACET[name]}}
        elif kind == "terms_desc":
            # 年份按年份倒序（新的在前），而不是按数量 —— 按数量会把年份顺序打乱
            sub = {"terms": {"field": field, "size": size, "order": {"_key": "desc"}}}
        else:
            sub = {"terms": {"field": field, "size": size}}

        aggs[f"facet_{name}"] = {"filter": wrapper, "aggs": {"top": sub}}
    return aggs


# ============================================================
# 排序
# ============================================================

SORT_FIELDS: dict[SortKey, str] = {
    "rating": "vote_average",
    "votes": "vote_count",
    "year": "release_year",
    "title": "title.kw",
    "popularity": "popularity",
}

# 主排序相同时用什么兜底。评分相同的片子，票数多的应该排前面 ——
# 否则《肖申克》(250 万人) 可能被一部 3 人打 9.9 分的片压过去。
SECONDARY_SORT: dict[str, str] = {
    "vote_average": "vote_count",
    "release_year": "vote_count",
    "popularity": "vote_count",
    "vote_count": "vote_average",
}


def build_sort(sort: SortKey, order: Order, *, has_query: bool) -> tuple[list[dict], str]:
    """构造排序，返回 (sort 列表, 实际使用的排序字段)。

    ★ 为什么要退化？
        没有关键词时所有文档的 _score 都是 1.0，按"相关性"排序等于随机排序。
        这时候应该按热度排 —— 用户浏览时想看的是热门片，不是数据库里的物理顺序。
        返回的第二个值会写进响应 meta.sort_used，让前端如实展示，不装作在按相关性排。
    """
    if sort == "relevance" and not has_query:
        sort, order = "votes", "desc"

    if sort == "relevance":
        return [{"_score": {"order": "desc"}}], "relevance"

    field = SORT_FIELDS[sort]
    out: list[dict] = [{field: {"order": order, "missing": "_last"}}]

    # 兜底排序，让结果稳定（ES 不保证同分文档的顺序）
    secondary = SECONDARY_SORT.get(field)
    if secondary:
        out.append({secondary: {"order": "desc", "missing": "_last"}})
    out.append({"_score": {"order": "desc"}})
    return out, sort


# ============================================================
# 高亮
# ============================================================

def build_highlight(fields: dict) -> dict:
    """高亮配置。

    `encoder: html` 是**必须**的：默认不转义，影评正文里若带有 HTML 片段，
    前端用 v-html 渲染高亮时就是个 XSS 口子。
    开了 html 编码器后，ES 会先把片段内容转义再加 <em> 标签，
    前端 v-html 就安全了。
    """
    return {
        "encoder": "html",
        "pre_tags": ["<em>"],
        "post_tags": ["</em>"],
        "fields": fields,
        # 关掉"字段必须匹配才高亮"：multi_match 命中的字段可能不是高亮字段列表里的，
        # 比如检索词命中了 keywords 但没命中 overview，此时仍希望 overview 里的词被标出来
        "require_field_match": False,
    }


MOVIE_HIGHLIGHT_FIELDS = {
    "title": {"number_of_fragments": 0},
    "title_zh": {"number_of_fragments": 0},
    "title_en": {"number_of_fragments": 0},
    "director": {"number_of_fragments": 0},
    "cast": {"number_of_fragments": 0},
    # 简介只截两段：整篇塞回前端太大，用户要看的是"命中词周围的那几句"
    "overview": {"fragment_size": 120, "number_of_fragments": 2},
}

REVIEW_HIGHLIGHT_FIELDS = {
    "text": {"fragment_size": 220, "number_of_fragments": 3},
}


# ============================================================
# 完整 DSL
# ============================================================

def build_movie_query(req: MovieSearchRequest) -> dict:
    """把检索请求拼成完整的 ES 搜索体。"""
    clauses = build_filter_clauses(req)
    has_query = bool(req.q and req.q.strip())
    sort_list, _sort_used = build_sort(req.sort, req.order, has_query=has_query)

    body: dict = {
        # ES 7+ 默认只精确统计到 1 万条，超出后 total 显示 "gte 10000"。
        # 影评有 5 万条，必须显式打开，否则分页页数会算错。
        "track_total_hits": True,
        "query": build_keyword_query(req.q, req.mode),
        "sort": sort_list,
        "from": (req.page - 1) * req.size,
        "size": req.size,
        "highlight": build_highlight(MOVIE_HIGHLIGHT_FIELDS),
    }

    post = build_post_filter(clauses)
    if post:
        body["post_filter"] = post
    if req.with_facets:
        body["aggs"] = build_facet_aggs(clauses, MOVIE_FACETS)
    return body


def build_review_query(req: ReviewSearchRequest) -> dict:
    """影评检索 DSL。结构与电影一致，只是字段和分面不同。"""
    clauses: dict[str, list[dict]] = {}
    if req.sentiment:
        clauses["sentiment"] = [{"terms": {"sentiment": req.sentiment}}]

    if getattr(req, "dataset", None):
        clauses["dataset"] = [{"terms": {"dataset": req.dataset}}]
    if getattr(req, "source", None):
        clauses["source"] = [{"terms": {"source": req.source}}]
    if getattr(req, "lang", None):
        clauses["lang"] = [{"term": {"lang": req.lang}}]
    if req.movie_id:
        clauses["movie"] = [{"term": {"movie_id": req.movie_id}}]
    if req.min_words is not None or req.max_words is not None:
        rng: dict = {}
        if req.min_words is not None:
            rng["gte"] = req.min_words
        if req.max_words is not None:
            rng["lte"] = req.max_words
        clauses["length"] = [{"range": {"word_count": rng}}]

    has_query = bool(req.q and req.q.strip())
    query = (
        {"match": {"text": {"query": req.q, "operator": "and"}}}
        if has_query else {"match_all": {}}
    )

    if req.sort == "length":
        sort_list = [{"word_count": {"order": req.order, "missing": "_last"}}]
    elif req.sort == "sentiment":
        sort_list = [{"sentiment_score": {"order": req.order, "missing": "_last"}}]
    else:
        sort_list = [{"_score": {"order": "desc"}}]
        if not has_query:
            sort_list = [{"word_count": {"order": "desc", "missing": "_last"}}]

    body: dict = {
        "track_total_hits": True,
        "query": query,
        "sort": sort_list,
        "from": (req.page - 1) * req.size,
        "size": req.size,
        "highlight": build_highlight(REVIEW_HIGHLIGHT_FIELDS),
    }
    post = build_post_filter(clauses)
    if post:
        body["post_filter"] = post
    if req.with_facets:
        body["aggs"] = build_facet_aggs(clauses, REVIEW_FACETS)
    return body


def build_suggest_query(q: str, size: int = 8) -> dict:
    """搜索框联想：只匹配片名，要求前缀连续，不参与简介等长文本。

    为什么单独一个查询而不是复用检索？
        联想要的是"打字打一半就能出结果"，所以要 phrase_prefix + 只搜片名；
        而正式检索要召回更多。两者目标不同，混在一起两头都不讨好。
    """
    fields = ["title^3", "title_zh^3", "title_en^2", "original_title^2"]
    return {
        "size": size,
        "query": {
            "multi_match": {
                "query": q,
                "fields": fields,
                "type": "phrase_prefix",
                "max_expansions": 20,
            }
        },
        "_source": ["movie_id", "title", "title_zh", "title_en",
                    "release_year", "genres_zh", "vote_average", "poster_url"],
    }


# ============================================================
# 洞察聚合（阶段 5 前的功能补全，前端洞察页折线图用）
# ============================================================

def build_decade_aggs() -> dict:
    """年代趋势聚合：按十年一桶统计影片数与平均分。

    为什么用 histogram 而不是 date_histogram？
        release_year 是**整数字段**（1998），不是日期。
        date_histogram 只能作用于 date 字段，硬上会直接报错。
        histogram 的 interval=10 天然就是"年代"语义，桶 key 即年代起始年。

    min_doc_count=0：把数据区间内的空年代也补成 0 桶 ——
        折线图中间断档会出现"跳变"，观感像数据丢失；
        补零之后曲线连续，前端判 null 均分不断线即可。
    """
    return {
        "by_decade": {
            "histogram": {
                "field": "release_year",
                "interval": 10,
                "min_doc_count": 0,
            },
            "aggs": {
                "avg_rating": {"avg": {"field": "vote_average"}},
            },
        }
    }


def build_genre_decade_matrix(genre_size: int = 10) -> dict:
    """类型 × 年代矩阵聚合： Flourish 式动态图表（条形竞赛 / 排名变化 / 流向图）的数据源。

    为什么是两层嵌套 terms → histogram 而不是前端拼？
        类型与年代都是**多对多**的：一部电影挂多个类型，
         ES 对 array 字段的 terms 聚合天然把一片计入多个类型桶，
         这正是"混搭类型"语义；前端要自己算就得先拉全库，量级完全不同。

    min_doc_count=0 补零年代桶：竞赛图某一类型在某年代没片，
        补零才能让排名"空一段"，而不是被前端误当成断线数据。
    """
    return {
        "by_genre": {
            "terms": {
                "field": "genres_zh",
                "size": genre_size,
                "min_doc_count": 5,
            },
            "aggs": {
                "by_decade": {
                    "histogram": {
                        "field": "release_year",
                        "interval": 10,
                        "min_doc_count": 0,
                    },
                    "aggs": {
                        "avg_rating": {"avg": {"field": "vote_average"}},
                    },
                }
            },
        }
    }


# ============================================================
# 票房分析（2026-10-22）：年度票房趋势聚合
# ============================================================

def build_box_office_years() -> dict:
    """年度票房趋势：按 release_year 分桶合计票房（仅统计有票房的影片）。

    设计说明：
    · 用 terms + order _key 而不是 histogram —— release_year 是整数字段，
      histogram 的 interval 语义对"年份"是巧合可用但对齐口径容易歧义；
      terms 直接给真实年份键，order 升序后前端省一道排序。
    · size=200 足够覆盖片库年份跨度（1938~2026）；
      超出部分会被 ES 静默丢弃，故调用方按桶数复核对。
    · total_rev 是全局票房合计（独立于分桶），用于总览数字；
      与各桶相加的差异 = 缺年份影片的票房，如实体现在接口 note 里。
    """
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": [{"exists": {"field": "revenue"}}]}},
        "aggs": {
            "by_year": {
                "terms": {
                    "field": "release_year",
                    "size": 200,
                    "order": {"_key": "asc"},
                },
                "aggs": {
                    "rev": {"sum": {"field": "revenue"}},
                },
            },
            "total_rev": {"sum": {"field": "revenue"}},
        },
    }


# ============================================================
# 趣味功能（阶段 5 前功能补全）：盲盒 / 足迹地图
# ============================================================

def build_random_query(seed: int, filters: list[dict] | None = None, size: int = 1) -> dict:
    """随机盲盒：random_score 给每部片一个"抽签分"，取最高的一部。

    两个设计决定：

    1. **seed 可传**。同一个 seed + 同一批文档 → 永远抽到同一部片。
       演示时"导演先抽、观众再抽"能抽到同一部，是可控的戏剧效果；
       不传则由调用方用时间戳生成，每次不同。
    2. **field 用 movie_id 而不是 _id**。_id 默认关闭 fielddata，
       random_score 直接引用它会 400（实测：Fielddata access on the _id
       field is disallowed）。movie_id 是 keyword 字段（doc_values 默认开）
       且与 _id 同值 —— 一样稳定，还能过 fielddata 这一关。
       （也试过默认的 _seq_no：能跑，但它随文档更新漂移，
        "同一个种子永远抽到同一部"跨重启就不成立了。）

    ★ 为什么必须包 function_score：ES **没有独立的 random_score 查询**
      （实测直接写 {"random_score": ...} 会 400：unknown query）。
      random_score 只是 function_score 家族里的一个打分函数，
      所以套一层 function_score + boost_mode=replace，让抽签分直接当相关性分。
      筛选条件放在内层 query 里 —— 先圈池子，再在池子里抽签。
    """
    inner: dict = {"bool": {"filter": filters}} if filters else {"match_all": {}}
    return {
        "size": size,
        "query": {
            "function_score": {
                "query": inner,
                "functions": [{"random_score": {"seed": seed, "field": "movie_id"}}],
                "boost_mode": "replace",
            }
        },
    }


def build_locations_aggs(path: str = "filming_locations", size: int = 60) -> dict:
    """足迹地图聚合：nested terms 按地名分组，max(lat/lon) 取坐标。

    为什么坐标用 max 而不是 top_hits：
        nested 聚合里的 top_hits 返回的是**根文档**的 _source，
        还要再手动剥一层 nested 路径；而同一个地名（同一个 qid）
        在各部电影里的坐标本就一致，max 一步到位。
        副作用还很贴心：缺坐标的地点 max 出来是 null，API 层过滤掉即可。

    doc_count 的含义要说清：它是 nested 文档数（电影×地点对），
    不是 DISTINCT 电影数。同一部片重复列同一地点才会虚高，实际数据里没有。
    """
    return {
        "locations": {
            "nested": {"path": path},
            "aggs": {
                "by_name": {
                    "terms": {"field": f"{path}.name.kw", "size": size},
                    "aggs": {
                        "lat": {"max": {"field": f"{path}.lat"}},
                        "lon": {"max": {"field": f"{path}.lon"}},
                        "kinds": {"terms": {"field": f"{path}.kind", "size": 3}},
                    },
                }
            },
        }
    }


# ============================================================
# 推荐查询（阶段 5 前功能补全）
# ============================================================

def build_similar_query(movie_id: str, index: str, size: int = 10) -> dict:
    """相似影片：more_like_this，拿该片自己的简介/片名/类型找"气质相近"的片。

    like 用 _index/_id 形式而不是拼文本 —— 让 ES 自己取原文、
    按各字段的分析器切词，避免我们在 Python 里重复实现一套分词。
    index 由调用方传（settings.es_index_movies）：本模块是纯函数，
    不读配置，离线测试传字面量即可。
    min_doc_freq=1：片库只有百余部，默认的 3 会把多数词滤掉，结果反而稀烂。
    must_not ids：相似结果里绝不能出现它自己（最常见的推荐事故）。
    """
    return {
        "size": size,
        "query": {
            "bool": {
                "must": [{
                    "more_like_this": {
                        "fields": ["overview", "title", "genres_zh"],
                        "like": [{"_index": index, "_id": movie_id}],
                        "min_term_freq": 1,
                        "min_doc_freq": 1,
                        "max_query_terms": 20,
                        "minimum_should_match": "20%",
                    }
                }],
                "must_not": [{"ids": {"values": [movie_id]}}],
            }
        },
    }


def build_popular_query(m: float, c: float, size: int = 20) -> dict:
    """热门榜单：贝叶斯加权分（IMDb Top 250 的同款公式）。

        WR = (v/(v+m))·R + (m/(v+m))·C

    v=该片票数，R=该片均分，m=进榜门槛票数，C=全局均分。
    为什么不能直接按均分排？一部 9.9 分但 3 人投过的片会霸榜 ——
    小众片在高分区扎堆，公式用 m 把"证据不足"的片往全局均分校准。

    script 里对缺字段做 size() 守卫：vote_average 缺失的文档
    直接取 .value 会让 Painless 抛异常，整个查询 500。
    """
    return {
        "size": size,
        "query": {
            "function_score": {
                "query": {"match_all": {}},
                "functions": [{
                    "script_score": {
                        "script": {
                            "source": (
                                "double v = doc['vote_count'].size() == 0 ? 0 : doc['vote_count'].value;"
                                "double r = doc['vote_average'].size() == 0 ? 0 : doc['vote_average'].value;"
                                "return (v / (v + params.m)) * r + (params.m / (v + params.m)) * params.c;"
                            ),
                            "params": {"m": m, "c": c},
                        }
                    }
                }],
                "boost_mode": "replace",
            }
        },
    }


def build_for_you_query(
    top_genres: list[str],
    top_directors: list[str],
    exclude_ids: list[str],
    size: int = 20,
) -> dict:
    """个性化推荐候选：按用户口味（类型 + 导演）召回，排除已看过的。

    口味从哪来：用户打过分（≥8）的影片里统计类型频次与导演，
    见 recommend_service.build_taste_profile。类型 boost 2 / 导演 boost 3 ——
    导演是比类型更强的身份信号（诺兰粉会为诺兰看任何类型）。
    minimum_should_match=1：至少中一个口味信号，但不要求全中。
    """
    should: list[dict] = []
    if top_genres:
        should.append({"terms": {"genres_zh": top_genres, "boost": 2.0}})
    for director in top_directors:
        should.append({"term": {"director.kw": {"value": director, "boost": 3.0}}})

    must_not: list[dict] = []
    if exclude_ids:
        must_not.append({"ids": {"values": exclude_ids}})

    return {
        "size": size,
        "query": {
            "bool": {
                "should": should,
                "minimum_should_match": 1,
                **({"must_not": must_not} if must_not else {}),
            }
        },
    }
