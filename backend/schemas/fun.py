"""
趣味功能接口的请求 / 响应模型。

三个功能都是"检索能力的玩具化"——同样的 ES 查询，
换一个打开方式就是demo现场的记忆点：

| 模型 | 对应接口 |
|---|---|
| MixRequest | POST /fun/mix 类型混搭器 |
| BlindBoxResponse | GET /fun/box 随机盲盒 |
| MapPoint / MapResponse | GET /fun/map 足迹地图 |
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.search import MovieHit


class MixRequest(BaseModel):
    """类型混搭器：找出**同时具备**所有指定类型的影片。

    至少 2 个类型才有"混搭"的意义（1 个类型就是普通筛选）。
    上限 5 个是防手滑：真实片库里同时命中 5 个类型的影片约等于不存在，
    放太多只会得到一个空结果和一句解释。
    """

    genres: list[str] = Field(..., min_length=2, max_length=5,
                              description="必须同时具备的类型，如 ['科幻', '喜剧']")
    rating_min: float | None = Field(default=None, ge=0, le=10)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    size: int = Field(default=20, ge=1, le=50)


class BlindBoxResponse(BaseModel):
    """随机盲盒：一部随机影片 + 用来抽它的种子。

    seed 回传给前端：用户觉得"这部有意思"时，可以把种子分享出去，
    别人用同一个种子抽到同一部 —— 社交裂变的小钩子。
    movie 为 None 表示当前筛选下一部都没抽到（如"8 分以上的科幻片"不存在）。
    """

    movie: MovieHit | None = None
    seed: int = Field(..., description="本次抽签使用的随机种子")
    note: str | None = None


class MapPoint(BaseModel):
    """地图上的一个取景/叙事地点。"""

    name: str
    kind: str | None = Field(default=None, description="filming=取景地 / narrative=故事发生地")
    lat: float
    lon: float
    movies: int = Field(default=0, description="在此地取景/叙事的影片数（嵌套文档数）")


class MapResponse(BaseModel):
    """足迹地图：全部带坐标的地点 + 诚实的数据说明。

    skipped_no_coords：库里有地名但没有坐标的条目数 ——
    地图画不出来，但要在响应里说清楚"少了几个、为什么"，
    不然后端看着像丢了数据。
    """

    points: list[MapPoint] = Field(default_factory=list)
    total_points: int = 0
    skipped_no_coords: int = 0
    note: str | None = None


class MapMoviesResponse(BaseModel):
    """某个地点拍/叙事的影片列表（信息窗点开标记后展示）。

    为什么单独一个接口而不是塞进 MapResponse：
    地图接口一次拉全量点位（60 个），如果每个点位再挂 10 部影片，
    响应体积翻几倍，而用户同一时刻只点开一个标记 —— 按需拉取。
    total 可能大于 hits 长度：接口按评分取前 size 部，
    剩下多少在 total 里交代，页面显示"还有 N 部"。
    """

    name: str = Field(..., description="查询的地点名（与点位 name 完全一致）")
    total: int = 0
    hits: list[MovieHit] = Field(default_factory=list)
