"""加载 data/web_movies.json 中的真实网络电影数据。"""
from __future__ import annotations

import json
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent / "web_movies.json"


def load_catalog() -> dict:
    if not _DATA_FILE.exists():
        raise FileNotFoundError(
            f"未找到 {_DATA_FILE}，请先运行: python data/fetch_web_movies.py"
        )
    return json.loads(_DATA_FILE.read_text(encoding="utf-8"))


def load_movies() -> list[dict]:
    return load_catalog()["movies"]


def all_genres_zh() -> list[str]:
    genres: list[str] = []
    for movie in load_movies():
        for name in movie.get("genres_zh") or []:
            if name not in genres:
                genres.append(name)
    return genres


def all_genres_en() -> list[str]:
    genres: list[str] = []
    for movie in load_movies():
        for name in movie.get("genres_en") or []:
            if name not in genres:
                genres.append(name)
    return genres


def movies_for_sqlserver() -> list[tuple]:
    """(title, year, language, duration, director, description, poster_url, genres_zh)"""
    rows = []
    for m in load_movies():
        title = m.get("title_zh") or m["title"]
        year = m.get("release_year") or 2024
        genres = m.get("genres_zh") or ["剧情"]
        desc = m.get("description") or ""
        lang = m.get("language") or "英语"
        if lang in ("English", "english"):
            lang = "英语"
        if not desc or "None" in desc:
            genre_text = "、".join(genres[:3])
            desc = f"《{title}》（{year}）— {genre_text}类型影片。"
        rows.append(
            (
                title,
                year,
                lang,
                m.get("duration"),
                m.get("director"),
                desc,
                m.get("poster_url"),
                genres,
            )
        )
    return rows


def movies_for_mysql() -> list[tuple]:
    """(title, year, language, duration, director, description, avg_score, rating_count)"""
    import random

    random.seed(42)
    rows = []
    for m in load_movies():
        year = m.get("release_year") or 2024
        desc = m.get("description") or ""
        if "（None）" in desc:
            genre_text = ", ".join((m.get("genres_en") or ["Drama"])[:3])
            desc = f"{m['title']} ({year}) — {genre_text}."
        score = round(random.uniform(6.8, 9.2), 1)
        count = random.randint(50000, 250000)
        rows.append(
            (
                m["title"],
                year,
                m.get("language") or "English",
                m.get("duration") or random.randint(90, 165),
                m.get("director") or "—",
                desc,
                score,
                count,
            )
        )
    return rows


def movie_genres_for_mysql() -> list[tuple]:
    """(title, [genre_en, ...])"""
    return [(m["title"], m.get("genres_en") or ["Drama"]) for m in load_movies()]
