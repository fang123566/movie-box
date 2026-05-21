import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "movie_system_api"))

from data.web_movie_data import all_genres_zh, load_movies, movies_for_sqlserver
from ops.crypto import hash_password

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=movie_system;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# 40 个测试用户（密码均为 123456）
USERS = [
    ("alice", "123456", "爱电影的艾丽丝", 22, "female", "爱情"),
    ("bob", "123456", "科幻迷小王", 25, "male", "科幻"),
    ("cindy", "123456", "悬疑观察员", 28, "female", "悬疑"),
    ("david", "123456", "动作片达人", 31, "male", "动作"),
    ("emma", "123456", "动画收藏家", 20, "female", "动画"),
    ("frank", "123456", "剧情研究者", 35, "male", "剧情"),
    ("grace", "123456", "喜剧爱好者", 24, "female", "喜剧"),
    ("henry", "123456", "犯罪片粉丝", 29, "male", "犯罪"),
    ("iris", "123456", "音乐电影迷", 26, "female", "音乐"),
    ("jack", "123456", "冒险家杰克", 27, "male", "冒险"),
    ("karen", "123456", "剧情控", 33, "female", "剧情"),
    ("leo", "123456", "经典影迷", 19, "male", "科幻"),
    ("mike", "123456", "漫威铁粉", 23, "male", "动作"),
    ("nina", "123456", "文艺片少女", 21, "female", "剧情"),
    ("oscar", "123456", "恐怖片勇士", 30, "male", "恐怖"),
    ("pearl", "123456", "爱情片达人", 27, "female", "爱情"),
    ("quinn", "123456", "纪录片爱好者", 34, "male", "纪录片"),
    ("rose", "123456", "家庭观影团", 36, "female", "家庭"),
    ("sam", "123456", "战争片迷", 40, "male", "战争"),
    ("tina", "123456", "奇幻世界", 18, "female", "奇幻"),
    ("user21", "123456", "影迷小陈", 22, "male", "喜剧"),
    ("user22", "123456", "影迷小李", 24, "female", "爱情"),
    ("user23", "123456", "影迷小张", 26, "male", "悬疑"),
    ("user24", "123456", "影迷小刘", 28, "female", "动画"),
    ("user25", "123456", "影迷小赵", 30, "male", "科幻"),
    ("user26", "123456", "影迷小周", 32, "female", "剧情"),
    ("user27", "123456", "影迷小吴", 20, "male", "动作"),
    ("user28", "123456", "影迷小郑", 22, "female", "犯罪"),
    ("user29", "123456", "影迷小孙", 24, "male", "冒险"),
    ("user30", "123456", "影迷小钱", 26, "female", "音乐"),
    ("user31", "123456", "周末观影", 29, "male", "喜剧"),
    ("user32", "123456", "夜班影院", 31, "female", "恐怖"),
    ("user33", "123456", "豆瓣九级", 27, "male", "剧情"),
    ("user34", "123456", "院线常客", 25, "female", "爱情"),
    ("user35", "123456", "独立电影", 33, "male", "纪录片"),
    ("user36", "123456", "港片情怀", 38, "male", "犯罪"),
    ("user37", "123456", "国产支持", 24, "female", "剧情"),
    ("user38", "123456", "好莱坞通", 28, "male", "动作"),
    ("user39", "123456", "日韩剧场", 23, "female", "爱情"),
    ("user40", "123456", "动画天堂", 19, "female", "动画"),
]


def scalar(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return row[0] if row else None


def main():
    random.seed(20260519)
    movies = movies_for_sqlserver()
    genres = all_genres_zh()

    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    # 清空旧数据（保留表结构）
    cursor.execute("DELETE FROM dbo.rating")
    cursor.execute("DELETE FROM dbo.history")
    cursor.execute("DELETE FROM dbo.movie_genre")
    cursor.execute("DELETE FROM dbo.movie")
    print("已清空旧电影/评分/观看记录")

    for genre in genres:
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.genre WHERE genre_name=?) INSERT INTO dbo.genre (genre_name) VALUES (?)",
            genre,
            genre,
        )

    for title, year, language, duration, director, description, poster_url, movie_genres in movies:
        cursor.execute(
            "INSERT INTO dbo.movie (title, release_year, language, duration, director, description, poster_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            title,
            year,
            language,
            duration,
            director,
            description,
            poster_url,
        )
        movie_id = scalar(cursor, "SELECT movie_id FROM dbo.movie WHERE title=?", (title,))
        for genre in movie_genres:
            genre_id = scalar(cursor, "SELECT genre_id FROM dbo.genre WHERE genre_name=?", (genre,))
            if genre_id:
                cursor.execute(
                    "INSERT INTO dbo.movie_genre (movie_id, genre_id) VALUES (?, ?)",
                    movie_id,
                    genre_id,
                )

    # 写入默认管理员（已存在则更新密码）
    admin_hash = hash_password("admin123")
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.admin WHERE username=?) "
        "INSERT INTO dbo.admin (username, password_hash) VALUES (?,?)",
        "admin", "admin", admin_hash,
    )
    cursor.execute(
        "UPDATE dbo.admin SET password_hash=? WHERE username=?",
        admin_hash, "admin",
    )
    print("管理员账号已就绪（用户名: admin，密码: admin123）")

    for username, password, nickname, age, gender, favorite_genre in USERS:
        favorite_genre_id = scalar(cursor, "SELECT genre_id FROM dbo.genre WHERE genre_name=?", (favorite_genre,))
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.[user] WHERE username=?) "
            "INSERT INTO dbo.[user] (username, password_hash, nickname, age, gender, favorite_genre_id) VALUES (?, ?, ?, ?, ?, ?)",
            username,
            username,
            hash_password(password),
            nickname,
            age,
            gender,
            favorite_genre_id,
        )
        cursor.execute(
            "UPDATE dbo.[user] SET nickname=?, age=?, gender=?, favorite_genre_id=? WHERE username=?",
            nickname,
            age,
            gender,
            favorite_genre_id,
            username,
        )

    user_ids = [row[0] for row in cursor.execute("SELECT user_id FROM dbo.[user]").fetchall()]
    movie_ids = [row[0] for row in cursor.execute("SELECT movie_id FROM dbo.movie").fetchall()]

    now = datetime.now()
    rating_total = 0
    history_total = 0
    for user_id in user_ids:
        rated_count = random.randint(28, min(45, len(movie_ids)))
        rated_movies = random.sample(movie_ids, rated_count)
        for movie_id in rated_movies:
            score = random.choice([2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
            rating_time = now - timedelta(days=random.randint(1, 540), hours=random.randint(0, 23))
            cursor.execute(
                "INSERT INTO dbo.rating (user_id, movie_id, score, rating_time) VALUES (?, ?, ?, ?)",
                user_id,
                movie_id,
                score,
                rating_time,
            )
            rating_total += 1

        watched_count = random.randint(32, min(55, len(movie_ids)))
        watched_movies = random.sample(movie_ids, watched_count)
        for movie_id in watched_movies:
            watch_time = now - timedelta(days=random.randint(1, 600), hours=random.randint(0, 23))
            duration_watched = random.randint(30, 165)
            completed = random.choice([0, 1, 1, 1])
            cursor.execute(
                "INSERT INTO dbo.history (user_id, movie_id, watch_time, duration_watched, completed) VALUES (?, ?, ?, ?, ?)",
                user_id,
                movie_id,
                watch_time,
                duration_watched,
                completed,
            )
            history_total += 1

    conn.commit()

    catalog = load_movies()
    print(f"中文电影数据: {len(catalog)} 部")
    print(f"评分记录: {rating_total} 条 | 观看记录: {history_total} 条")
    for table in ["genre", "movie", "[user]", "rating", "history", "movie_genre"]:
        print(table, scalar(cursor, f"SELECT COUNT(*) FROM dbo.{table}"))

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
