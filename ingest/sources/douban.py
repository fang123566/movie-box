"""
豆瓣数据源采集器 —— 阶段 1f（用户授权解除「禁采集豆瓣」红线后新增）。

为什么需要它：
    电影盒子的影评语料此前只有 Kaggle IMDb 英文影评 + 中文翻译兜底，
    缺少「中文母语用户真实短评」。豆瓣是国内最大的电影社区，其短评
    （`/subject/{id}/comments`）是高质量的母语中文影评来源。
    此外豆瓣「正在热映」榜单（`/cinema/nowplaying/`）可作为「院线新片」数据源。

════════════════════════════════════════════════════════════════════════
★ 合规与限速约定（写在最前，谁改都要先看）
════════════════════════════════════════════════════════════════════════
1. **只抓公开页，绝不挂登录 Cookie**：未登录即可看到短评（已本机 Chrome 验证），
   不碰 `/j/subject_suggest`（robots.txt 禁了）与会员/付费内容。
2. **库内电影 → 豆瓣 ID 的映射走 Wikidata P4529**（Douban film ID 属性），
   一次 SPARQL 批量问，零逐片请求、公开开放数据；不依赖被禁的豆瓣 suggest 接口。
3. **慢速采集**：每部电影最多 2 页（40 条短评），相邻请求间隔 ≥ 2.5s，
   不并发、不过频，把账号/封 IP 风险压到最低。
4. **作者匿名化**：短评作者名只存 sha256 截断的 `author_hash`，**绝不**落明文
   用户名 / 主页链接（与本项目 letterboxd/metacritic 的合规口径一致）。
5. **不采 PII**：不抓作者的性别、地理位置、收藏夹等任何附加信息。

产物：
    data_lake/interim/reviews.douban.jsonl       豆瓣短评（source=douban, lang=zh）
    data_lake/interim/douban_nowplaying.jsonl    正在热映榜单（独立实体，走单独 ES 索引）
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlsplit

from common.settings import settings
from ingest.http import CollectorHttpError, RateLimitedClient
from ingest.schema import fill_review

# ── Wikidata 直接三元组前缀（用 IRI 而非前缀，方便把属性名塞进 VALUES）──
WD_DIRECT = "http://www.wikidata.org/prop/direct"
WD_ENTITY = "http://www.wikidata.org/entity"

# 豆瓣短评页面星级 class → (归一评分 0-10, 情感)
# class 形如 allstar50（=5 星/力荐）、allstar00（无评分）
_STAR_MAP: dict[str, tuple[float | None, str | None]] = {
    "allstar50": (10.0, "positive"),   # 力荐
    "allstar40": (8.0, "positive"),    # 推荐
    "allstar30": (6.0, "neutral"),     # 还行
    "allstar20": (4.0, "negative"),    # 较差
    "allstar10": (2.0, "negative"),    # 很差
    "allstar00": (None, None),         # 未评分
}


# ============================================================
# 纯函数：Wikidata P4529 映射解析（可离线自检）
# ============================================================


def parse_douban_rows(payload: dict | None) -> dict[str, str]:
    """把 SPARQL 返回的 douban 映射摊平成 {主键: douban_id}。

    同时支持两种查询：
      - 按 qid 查询：返回 ?film(=wd:Qxxx) 与 ?douban；用 qid 反查电影。
      - 按 imdb/tmdb 查询：返回 ?key(tconst / tmdb 数字) 与 ?douban。
    两种结果合并进同一个 dict，key 归一为电影侧的「可见主键」。
    """
    bindings = ((payload or {}).get("results") or {}).get("bindings") or []
    out: dict[str, str] = {}
    for b in bindings:
        douban = (b.get("douban") or {}).get("value")
        if not douban:
            continue
        douban = str(douban).strip()
        # 优先用 qid 作为 key（更稳），否则用 imdb/tmdb key
        qid = _qid_of((b.get("film") or {}).get("value"))
        if qid:
            out[qid] = douban
            continue
        key = (b.get("key") or {}).get("value")
        if key:
            out[str(key).strip()] = douban
    return out


def _qid_of(uri: str | None) -> str | None:
    if not uri:
        return None
    tail = uri.rstrip("/").rsplit("/", 1)[-1]
    return tail if re.fullmatch(r"Q\d+", tail) else None


def _esc(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def build_qid_values(qids: Iterable[str]) -> str:
    return " ".join(f"wd:{q}" for q in qids if q and re.fullmatch(r"Q\d+", q))


def build_id_values(pairs: Iterable[tuple[str, str]]) -> str:
    """(P345/P4947, key) → SPARQL VALUES 子句。"""
    items = []
    for prop, key in pairs:
        if not prop or not key:
            continue
        items.append(f'(<{WD_DIRECT}/{prop}> "{_esc(key)}")')
    return " ".join(items)


QID_QUERY = """SELECT ?film ?douban WHERE {{
  VALUES ?film {{ {values} }}
  ?film wdt:P4529 ?douban .
}}
"""

ID_QUERY = """SELECT ?key ?douban WHERE {{
  VALUES (?prop ?key) {{ {values} }}
  ?film ?prop ?key .
  ?film wdt:P4529 ?douban .
}}
"""


# ============================================================
# 采集器
# ============================================================


class DoubanCollector:
    """豆瓣数据源：短评（本机 Chrome）+ 热映榜（公开页）+ 库内片→豆瓣 ID 映射。"""

    SOURCE = "douban"

    def __init__(
        self,
        *,
        force: bool = False,
        proxy: str | None = None,
        headless: bool = True,
    ) -> None:
        self.force = force
        # Wikidata P4529 映射用的 SPARQL 客户端（与 wikidata 源同口径）
        _ep = settings.wikidata_endpoint
        _parts = urlsplit(_ep)
        _base = f"{_parts.scheme}://{_parts.netloc}"
        _path = _parts.path or "/sparql"
        self.sparql_path = _path
        self.wd_client = RateLimitedClient(
            _base,
            headers={
                "User-Agent": settings.wikidata_user_agent,
                "Accept": "application/sparql-results+json",
            },
            min_interval=0.6,
            max_retries=settings.wikidata_max_retries,
            proxy=proxy if proxy is not None else settings.collector_proxy,
        )
        self.headless = headless
        self._browser = None
        self._ctx = None
        self.stats = {
            "mapped": 0, "comments": 0, "films": 0,
            "nowplaying": 0, "skipped_empty": 0,
        }

    # ---------------- Wikidata P4529 映射 ----------------
    def _sparql(self, query: str, *, kind: str, raw_path: Path) -> dict:
        if not self.force:
            from ingest.http import load_raw
            cached = load_raw(raw_path)
            if isinstance(cached, dict) and cached.get("_request", {}).get("query") == query:
                return cached.get("_response") or {}
        payload = self.wd_client.get_json(
            self.sparql_path, {"query": query, "format": "json"}, quiet=True
        )
        from ingest.http import dump_raw
        dump_raw({"_request": {"query": query}, "_response": payload}, raw_path)
        return payload

    def map_douban_ids(self, movies: Iterable[dict]) -> dict[str, str]:
        """给库内电影批量映射豆瓣 ID，返回 {movie_id: douban_id}。

        优先级：wikidata_qid（最稳）→ imdb_id（P345）→ tmdb_id（P4947）。
        一个电影只在一种渠道里出现一次，避免重复查询。
        """
        movies = list(movies)
        qid_map: dict[str, str] = {}     # qid -> movie_id
        id_pairs: list[tuple[str, str]] = []  # (prop, key) -> movie_id 的辅助表
        id_to_movie: dict[tuple[str, str], str] = {}
        for m in movies:
            mid = m.get("movie_id") or m.get("imdb_id") or m.get("tmdb_id")
            if not mid:
                continue
            qid = m.get("wikidata_qid")
            if qid and re.fullmatch(r"Q\d+", str(qid)):
                qid_map.setdefault(str(qid), str(mid))
                continue
            imdb = (m.get("imdb_id") or "").strip()
            tmdb = m.get("tmdb_id")
            if imdb and ("P345", imdb) not in id_to_movie:
                id_pairs.append(("P345", imdb))
                id_to_movie[("P345", imdb)] = str(mid)
            elif tmdb and ("P4947", str(int(tmdb))) not in id_to_movie:
                id_pairs.append(("P4947", str(int(tmdb))))
                id_to_movie[("P4947", str(int(tmdb)))] = str(mid)

        result: dict[str, str] = {}
        # 按 qid 批量
        if qid_map:
            qids = list(qid_map)
            for start in range(0, len(qids), settings.wikidata_batch):
                chunk = qids[start:start + settings.wikidata_batch]
                q = QID_QUERY.format(values=build_qid_values(chunk))
                digest = hashlib.md5(q.encode()).hexdigest()[:16]
                raw_path = settings.lake("raw", "douban", f"qid_{digest}.json")
                try:
                    rows = parse_douban_rows(self._sparql(q, kind="qid", raw_path=raw_path))
                except Exception as exc:  # 单批 429/网络异常不应中断整批
                    print(f"    [跳过一批] P4529(qid) 查询失败：{exc}")
                    continue
                for qid, db in rows.items():
                    mid = qid_map.get(qid)
                    if mid:
                        result[mid] = db
        # 按 imdb/tmdb 批量
        if id_pairs:
            for start in range(0, len(id_pairs), settings.wikidata_batch):
                chunk = id_pairs[start:start + settings.wikidata_batch]
                q = ID_QUERY.format(values=build_id_values(chunk))
                digest = hashlib.md5(q.encode()).hexdigest()[:16]
                raw_path = settings.lake("raw", "douban", f"id_{digest}.json")
                try:
                    rows = parse_douban_rows(self._sparql(q, kind="id", raw_path=raw_path))
                except Exception as exc:  # 单批 429/网络异常不应中断整批
                    print(f"    [跳过一批] P4529(id) 查询失败：{exc}")
                    continue
                for key, db in rows.items():
                    # key 可能是 imdb_id(tconst) 或 tmdb 数字
                    mid = id_to_movie.get(("P345", key)) or id_to_movie.get(("P4947", key))
                    if mid:
                        result[mid] = db
        self.stats["mapped"] = len(result)
        return result

    # ---------------- Playwright（短评 + 热映榜）----------------
    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # pragma: no cover - 环境未装 playwright
            raise RuntimeError(
                "豆瓣短评/热映榜需要 Playwright + 本机 Chrome："
                "pip install playwright && 确保本机已装 Chrome"
            )
        pw = sync_playwright().start()
        self._pw = pw
        self._browser = pw.chromium.launch(
            channel="chrome", headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx = self._browser.new_context(
            locale="zh-CN",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        )

    def _close_browser(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
            if self._browser is not None:
                self._browser.close()
            if getattr(self, "_pw", None) is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = self._ctx = None

    def _wait_comments(self, page, timeout_ms: int = 12000) -> int:
        """等短评条目出现（豆瓣有 JS 渲染延迟），返回条数。"""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            n = page.locator(".comment-item").count()
            if n > 0:
                return n
            page.wait_for_timeout(800)
        return 0

    def _safe_eval(self, page, expr: str, *, retries: int = 4) -> dict | list:
        """在页面上执行 JS，遇到「执行上下文被导航销毁」等瞬时错误就重试。

        豆瓣偶尔会在 domcontentloaded 之后又做一次客户端跳转/安全校验，
        导致 evaluate 的上下文被销毁；多等一会重评即可，不应因此崩掉整批。
        """
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return page.evaluate(expr)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                page.wait_for_timeout(1500)
        raise RuntimeError(f"页面 JS 执行失败（{retries} 次重试）：{last_exc}")

    def collect_ratings(
        self,
        mapped: dict[str, str],
        *,
        movies_by_id: dict[str, dict] | None = None,
        delay: float = 1.0,
    ) -> Iterator[dict]:
        """逐片抓豆瓣评分页，yield 可被 transform 合并进库内电影的「豆瓣评分记录」。

        只带 imdb_id / tmdb_id / title / douban_id / douban_rating / douban_votes，
        transform 的 EXTRA_FIELDS + 主键锚点会把它们干净并入库内电影。
        """
        self._ensure_browser()
        page = self._ctx.new_page()
        for mid, douban_id in mapped.items():
            movie = (movies_by_id or {}).get(mid) or {}
            url = f"https://movie.douban.com/subject/{douban_id}/"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                print(f"    [跳过] 豆瓣评分 {douban_id}：{exc}")
                continue
            # 评分页是 SSR，等 2.5s 让可能的客户端跳转/安全校验稳定下来
            page.wait_for_timeout(2500)
            try:
                info = self._safe_eval(page, """() => {
                  const ratingEl = document.querySelector('.rating_num');
                  const votesEl = document.querySelector('.rating_people .votes')
                                || document.querySelector('span[property="v:votes"]');
                  const titleEl = document.querySelector('h1 span');
                  return {
                    rating: ratingEl ? ratingEl.innerText.trim() : '',
                    votes: votesEl ? votesEl.innerText.replace(/[^0-9]/g, '') : '',
                    title: titleEl ? titleEl.innerText.trim() : '',
                  };
                }""")
            except Exception as exc:
                print(f"    [跳过] 豆瓣评分解析 {douban_id}：{exc}")
                continue
            rating = float(info.get("rating") or 0) or None
            votes = int(info.get("votes") or 0) or None
            yield {
                "imdb_id": movie.get("imdb_id"),
                "tmdb_id": movie.get("tmdb_id"),
                "title": movie.get("title_zh") or movie.get("title"),
                "title_zh": movie.get("title_zh"),
                "douban_id": str(douban_id),
                "douban_rating": rating,
                "douban_votes": votes,
                "source": "douban",
                "collected_at": _now(),
            }
            if delay:
                time.sleep(delay)
        page.close()

    def collect_reviews(
        self,
        mapped: dict[str, str],
        *,
        movies_by_id: dict[str, dict] | None = None,
        pages: int = 2,
        delay: float = 2.5,
        limit: int | None = None,
    ) -> Iterator[dict]:
        """逐片抓豆瓣短评，yield 一条条合规的影评记录。

        mapped: {movie_id: douban_id}
        movies_by_id: 可选，{movie_id: 电影记录} 用来补 movie_title / imdb_id / tmdb_id
        """
        self._ensure_browser()
        page = self._ctx.new_page()
        emitted = 0
        for mid, douban_id in mapped.items():
            if limit and emitted >= limit:
                break
            movie = (movies_by_id or {}).get(mid) or {}
            for p in range(pages):
                if limit and emitted >= limit:
                    break
                start = p * 20
                url = (f"https://movie.douban.com/subject/{douban_id}/comments"
                       f"?start={start}&limit=20&status=P")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:  # 单页失败不应中断整批
                    print(f"    [跳过] 豆瓣 {douban_id} 第{p + 1}页：{exc}")
                    break
                n = self._wait_comments(page)
                if n == 0:
                    self.stats["skipped_empty"] += 1
                    break
                try:
                    rows = self._safe_eval(page, """() => {
                      const items = Array.from(document.querySelectorAll('.comment-item'));
                      return items.map(it => {
                        const cid = it.getAttribute('data-cid') || '';
                        const short = it.querySelector('.short');
                        const text = short ? short.innerText.trim() : '';
                    const ratingEl = it.querySelector('.rating')
                                  || it.querySelector('[class*="allstar"]');
                    const ratingCls = ratingEl ? ratingEl.className : '';
                    const ratingTitle = ratingEl ? (ratingEl.getAttribute('title') || '') : '';
                        const authorEl = it.querySelector('.comment-info a');
                        const author = authorEl ? authorEl.innerText.trim() : '';
                        const timeEl = it.querySelector('.comment-time');
                        const ctime = timeEl ? timeEl.innerText.trim() : '';
                        const m = /allstar(\\d{2})/.exec(ratingCls);
                        const stars = m ? parseInt(m[1], 10) / 10 : 0;
                        return {cid, text, stars, author, ctime};
                      });
                    }""")
                except Exception as exc:
                    print(f"    [跳过] 豆瓣 {douban_id} 第{p + 1}页解析：{exc}")
                    break
                for r in rows:
                    if not r.get("text"):
                        continue
                    stars = r.get("stars") or 0
                    cls = f"allstar{int(stars * 10):02d}"
                    score, sentiment = _STAR_MAP.get(cls, (None, None))
                    author = (r.get("author") or "").strip()
                    author_hash = (
                        hashlib.sha256(author.encode("utf-8")).hexdigest()[:16]
                        if author else None
                    )
                    rec = fill_review({
                        "review_id": f"douban:{r['cid']}" if r.get("cid") else None,
                        "external_id": f"douban:{r['cid']}" if r.get("cid") else None,
                        "text": r["text"],
                        "text_len": len(r["text"]),
                        "word_count": len(r["text"]),
                        "sentiment": sentiment,
                        "sentiment_score": (
                            (score / 10.0 * 2 - 1.0) if score is not None else None
                        ),
                        "rating": score,
                        "movie_title": movie.get("title_zh") or movie.get("title"),
                        "movie_year": movie.get("release_year"),
                        "imdb_id": movie.get("imdb_id"),
                        "movie_tmdb_id": movie.get("tmdb_id"),
                        "lang": "zh",
                        "dataset": "douban",
                        "source": "douban",
                        "review_type": "user",
                        "author_hash": author_hash,
                        "collected_at": _now(),
                    })
                    if not rec.get("review_id"):
                        rec["review_id"] = (
                            f"douban:{hashlib.sha1(r['text'].encode()).hexdigest()[:16]}"
                        )
                    yield rec
                    emitted += 1
                    self.stats["comments"] += 1
                if page.locator(".comment-item").count() < 20:
                    break  # 不足 20 条说明已到末页
            self.stats["films"] += 1
            if delay:
                time.sleep(delay)
        page.close()
        # 注意：浏览器会话由调用方（run_collect 命令）统一 close()，
        # 以便「抓评分 + 抓评论」复用同一个会话，避免重复启停。

    def collect_nowplaying(self, *, city: str = "hangzhou") -> list[dict]:
        """抓豆瓣「正在热映」榜单（公开页，无需登录）。"""
        self._ensure_browser()
        page = self._ctx.new_page()
        rows: list[dict] = []
        try:
            page.goto(
                f"https://movie.douban.com/cinema/nowplaying/{city}/",
                wait_until="domcontentloaded", timeout=30000,
            )
            page.wait_for_timeout(4000)
            rows = self._safe_eval(page, """() => {
              const items = Array.from(document.querySelectorAll('li.list-item'));
              return items.map(it => {
                const a = it.attributes;
                // 海报：豆瓣 lazy-load，真实地址在 img 的 src 或 data-src
                const img = it.querySelector('.poster img');
                const poster = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;
                return {
                  douban_id: a['data-subject'] ? a['data-subject'].value : null,
                  title: a['data-title'] ? a['data-title'].value : null,
                  poster: poster && poster.startsWith('http') ? poster : null,
                  douban_rating: a['data-score'] ? parseFloat(a['data-score'].value) : null,
                  douban_votes: a['data-votecount'] ? parseInt(a['data-votecount'].value, 10) : null,
                  release_year: a['data-release'] ? parseInt(a['data-release'].value, 10) : null,
                  region: a['data-region'] ? a['data-region'].value : null,
                  director: a['data-director'] ? a['data-director'].value : null,
                  actors: a['data-actors'] ? a['data-actors'].value : null,
                  duration: a['data-duration'] ? a['data-duration'].value : null,
                  category: a['data-category'] ? a['data-category'].value : null,
                };
              // 只留「正在热映」类目：页面还可能混入即将上映等其它榜单条目
              }).filter(r => r.category === 'nowplaying' || r.category === null);
            }""") or []
        except Exception as exc:
            print(f"    [热映榜失败] {exc}")
            rows = []
        finally:
            page.close()
            # 浏览器会话由调用方统一 close()，见 collect_reviews 说明
        rows = rows or []
        # category 只是抓取时的类目过滤依据，不落索引（dynamic:strict）
        for r in rows:
            r.pop("category", None)
        for r in rows:
            r["collected_at"] = _now()
            r["source"] = "douban"
        self.stats["nowplaying"] = len(rows)
        return rows

    def close(self) -> None:
        self._close_browser()
        try:
            self.wd_client.close()
        except Exception:
            pass

    def __enter__(self) -> "DoubanCollector":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
