"""
从公开网络数据源拉取真实电影元数据，生成中文片名的 data/web_movies.json。

数据源：MovieLens、popular-movies、国产片补充库、可选 TMDB（TMDB_API_KEY）
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from chinese_domestic_movies import CHINESE_DOMESTIC_MOVIES
from chinese_title_map import to_chinese_title

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = DATA_DIR / "web_movies.json"
MOVIELENS_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
POPULAR_URL = "https://popular-movies-data.stevenlu.com/movies.json"
TARGET_COUNT = 120
MIN_YEAR = 2005
MIN_RATINGS = 2

GENRE_EN_TO_ZH = {
    "Action": "动作",
    "Adventure": "冒险",
    "Animation": "动画",
    "Children": "家庭",
    "Comedy": "喜剧",
    "Crime": "犯罪",
    "Documentary": "纪录片",
    "Drama": "剧情",
    "Fantasy": "奇幻",
    "Horror": "恐怖",
    "Musical": "音乐",
    "Mystery": "悬疑",
    "Romance": "爱情",
    "Sci-Fi": "科幻",
    "Thriller": "悬疑",
    "War": "战争",
    "Western": "西部",
    "Film-Noir": "犯罪",
    "IMAX": "冒险",
    "Family": "家庭",
    "science_fiction": "科幻",
    "animation": "动画",
    "comedy": "喜剧",
    "adventure": "冒险",
    "family": "家庭",
    "mystery": "悬疑",
    "drama": "剧情",
    "thriller": "悬疑",
    "fantasy": "奇幻",
}


def _request_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "MovieRecommendationSystem/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_title(title: str) -> str:
    title = re.sub(r", The$", "", title)
    title = re.sub(r", A$", "", title)
    title = re.sub(r", An$", "", title)
    return title.strip().lower()


def _parse_movielens_title(raw: str) -> tuple[str, int | None]:
    match = re.match(r"^(.*)\s*\((\d{4})\)\s*$", raw.strip())
    if match:
        return match.group(1).strip(), int(match.group(2))
    return raw.strip(), None


def _map_genres_en(genres: list[str]) -> list[str]:
    result = []
    for g in genres:
        g = g.strip()
        if not g or g == "(no genres listed)":
            continue
        mapped = GENRE_EN_TO_ZH.get(g, GENRE_EN_TO_ZH.get(g.replace("_", " ").title()))
        if mapped and mapped not in result:
            result.append(mapped)
    return result or ["剧情"]


def _map_genres_popular(genres: list[str]) -> list[str]:
    result = []
    for g in genres:
        key = g.replace("_", " ")
        mapped = GENRE_EN_TO_ZH.get(g) or GENRE_EN_TO_ZH.get(key.title()) or GENRE_EN_TO_ZH.get(g.title())
        if mapped and mapped not in result:
            result.append(mapped)
    return result or ["剧情"]


def _apply_chinese_title(movie: dict) -> dict:
    en = movie.get("title_en") or movie.get("title") or ""
    zh = movie.get("title_zh") or to_chinese_title(en)
    if not zh:
        zh = en
    movie["title_en"] = en
    movie["title_zh"] = zh
    movie["title"] = zh
    return movie


def load_movielens():
    req = urllib.request.Request(MOVIELENS_URL, headers={"User-Agent": "MovieRecommendationSystem/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        zdata = resp.read()
    with zipfile.ZipFile(BytesIO(zdata)) as zf:
        import csv
        from io import TextIOWrapper

        movies = list(csv.DictReader(TextIOWrapper(zf.open("ml-latest-small/movies.csv"), encoding="utf-8")))
        links = {
            row["movieId"]: row
            for row in csv.DictReader(TextIOWrapper(zf.open("ml-latest-small/links.csv"), encoding="utf-8"))
        }
        ratings = csv.DictReader(TextIOWrapper(zf.open("ml-latest-small/ratings.csv"), encoding="utf-8"))
        rating_counts: dict[str, int] = defaultdict(int)
        for row in ratings:
            rating_counts[row["movieId"]] += 1

    candidates = []
    for row in movies:
        title, year = _parse_movielens_title(row["title"])
        if not year or year < MIN_YEAR:
            continue
        mid = row["movieId"]
        if rating_counts[mid] < MIN_RATINGS:
            continue
        genres_en = [g for g in row["genres"].split("|") if g != "(no genres listed)"]
        link = links.get(mid, {})
        imdb = link.get("imdbId", "")
        imdb_id = f"tt{imdb.zfill(7)}" if imdb else None
        candidates.append(
            {
                "title_en": title,
                "title": title,
                "release_year": year,
                "language": "英语",
                "genres_en": genres_en,
                "genres_zh": _map_genres_en(genres_en),
                "tmdb_id": int(link["tmdbId"]) if link.get("tmdbId") else None,
                "imdb_id": imdb_id,
                "rating_count": rating_counts[mid],
                "source": "movielens",
            }
        )
    candidates.sort(key=lambda x: (-x["rating_count"], -x["release_year"]))
    return candidates


def load_popular():
    data = _request_json(POPULAR_URL, timeout=30)
    items = []
    for row in data:
        genres_raw = row.get("genres") or []
        genres_en = [g.replace("_", " ").title().replace("Science Fiction", "Sci-Fi") for g in genres_raw]
        poster = row.get("poster_url") or ""
        if poster.startswith("http://"):
            poster = "https://" + poster[len("http://") :]
        en_title = row["title"]
        items.append(
            {
                "title_en": en_title,
                "title": en_title,
                "release_year": row.get("year"),
                "language": "英语",
                "genres_en": genres_en,
                "genres_zh": _map_genres_popular(genres_raw),
                "tmdb_id": row.get("tmdb_id"),
                "imdb_id": row.get("imdb_id"),
                "poster_url": poster or None,
                "source": "popular-movies",
            }
        )
    return items


def load_domestic():
    items = []
    for row in CHINESE_DOMESTIC_MOVIES:
        genres_zh = row.get("genres_zh") or ["剧情"]
        items.append(
            {
                "title_en": row["title"],
                "title": row["title"],
                "title_zh": row["title"],
                "release_year": row["release_year"],
                "language": row.get("language") or "中文",
                "duration": row.get("duration"),
                "director": row.get("director"),
                "description": row.get("description"),
                "poster_url": row.get("poster_url"),
                "genres_en": [],
                "genres_zh": genres_zh,
                "source": "chinese-domestic",
            }
        )
    return items


def enrich_tmdb(movie: dict, api_key: str) -> dict:
    tmdb_id = movie.get("tmdb_id")
    if not tmdb_id:
        return movie
    url = (
        f"https://api.themoviedb.org/3/movie/{tmdb_id}"
        f"?api_key={api_key}&language=zh-CN&append_to_response=credits"
    )
    try:
        data = _request_json(url, timeout=20)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return movie

    if data.get("title"):
        movie["title_zh"] = data["title"]
        movie["title"] = data["title"]
    movie["title_en"] = data.get("original_title") or movie.get("title_en")
    movie["release_year"] = movie.get("release_year") or (
        int(data["release_date"][:4]) if data.get("release_date") else None
    )
    movie["duration"] = data.get("runtime") or movie.get("duration")
    overview = (data.get("overview") or "").strip()
    if overview:
        movie["description"] = overview
    if data.get("poster_path"):
        movie["poster_url"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
    credits = data.get("credits") or {}
    crew = credits.get("crew") or []
    directors = [c["name"] for c in crew if c.get("job") == "Director"]
    if directors:
        movie["director"] = ", ".join(directors[:2])
    genres_api = [g["name"] for g in data.get("genres") or []]
    if genres_api:
        movie["genres_en"] = genres_api
        movie["genres_zh"] = _map_genres_en(genres_api)
    return movie


def merge_movies(domestic: list[dict], popular: list[dict], movielens: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []

    def add(item: dict):
        item = _apply_chinese_title(item)
        key = _normalize_title(item["title"])
        if key in merged:
            merged[key] = {**merged[key], **{k: v for k, v in item.items() if v}}
            return
        merged[key] = item
        order.append(key)

    for item in domestic:
        add(item)
    for item in popular:
        add(item)
        if len(order) >= TARGET_COUNT:
            break
    for item in movielens:
        if len(order) >= TARGET_COUNT:
            break
        add(item)

    return [merged[k] for k in order[:TARGET_COUNT]]


def finalize(movie: dict) -> dict:
    movie = _apply_chinese_title(movie)
    year = movie.get("release_year")
    if not year and movie.get("source") == "popular-movies":
        year = 2025
    genres_zh = movie.get("genres_zh") or ["剧情"]
    genres_en = movie.get("genres_en") or []
    genre_text = "、".join(genres_zh[:3])
    title = movie["title"]
    description = movie.get("description")
    if not description or description.endswith("None）"):
        director = movie.get("director") or "未知"
        description = (
            f"《{title}》({year or '未知年份'})，{genre_text}类型。"
            f"导演：{director}。"
            f"本片数据来自公开电影数据库（MovieLens / 热门榜单）。"
        )
    language = movie.get("language") or "英语"
    if language in ("English", "english"):
        language = "英语"
    return {
        "title": title,
        "title_en": movie.get("title_en"),
        "title_zh": title,
        "release_year": year,
        "language": language,
        "duration": movie.get("duration"),
        "director": movie.get("director"),
        "description": description,
        "poster_url": movie.get("poster_url"),
        "genres_en": genres_en,
        "genres_zh": genres_zh,
        "tmdb_id": movie.get("tmdb_id"),
        "imdb_id": movie.get("imdb_id"),
        "source": movie.get("source"),
    }


def main():
    print("Loading 国产/华语电影 …")
    domestic = load_domestic()
    print(f"  {len(domestic)} titles")

    print("Loading popular-movies …")
    popular = load_popular()
    print(f"  {len(popular)} titles")

    print("Loading MovieLens …")
    movielens = load_movielens()
    print(f"  {len(movielens)} candidates ({MIN_YEAR}+)")

    movies = merge_movies(domestic, popular, movielens)
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if api_key:
        print("Enriching via TMDB (zh-CN) …")
        for i, movie in enumerate(movies):
            movies[i] = enrich_tmdb(movie, api_key)
            movies[i] = _apply_chinese_title(movies[i])
            time.sleep(0.25)
    else:
        print("TMDB_API_KEY not set — using本地中文译名映射")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [
            "chinese-domestic",
            "popular-movies-data.stevenlu.com",
            "grouplens.org/movielens",
        ],
        "count": len(movies),
        "movies": [finalize(m) for m in movies],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(movies)} Chinese-title movies -> {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
