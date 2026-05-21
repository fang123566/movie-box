from db_config import get_connection

def get_ratings_count():
    conn = get_connection()
    if conn is None:
        print("数据库连接失败 - get_ratings_count")
        return 0

    cursor = conn.cursor()
    try:
        print("正在执行SQL: SELECT COUNT(*) as count FROM rating")
        cursor.execute("SELECT COUNT(*) as count FROM rating;")
        result = cursor.fetchone()
        print(f"评分数量查询结果: {result}")
        # 修复：使用字典键名 'count' 而不是数字索引 0
        return result['count'] if result else 0
    except Exception as e:
        print(f"获取评分数量错误: {e}")
        print(f"错误类型: {type(e)}")
        import traceback
        print("完整错误堆栈:")
        traceback.print_exc()
        return 0
    finally:
        cursor.close()
        conn.close()

def get_all_ratings():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username, u.nickname, m.title as movie_title 
            FROM rating r 
            LEFT JOIN [user] u ON r.user_id = u.user_id 
            LEFT JOIN movie m ON r.movie_id = m.movie_id
            ORDER BY r.rating_time DESC
        """)
        ratings = cursor.fetchall()

        # 处理日期格式
        for rating in ratings:
            if rating.get('rating_time'):
                rating['rating_time'] = rating['rating_time'].isoformat()

        return ratings
    except Exception as e:
        print(f"获取评分数据失败: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_rating_by_id(rating_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username, u.nickname, m.title as movie_title 
            FROM rating r 
            LEFT JOIN [user] u ON r.user_id = u.user_id 
            LEFT JOIN movie m ON r.movie_id = m.movie_id
            WHERE r.rating_id = ?
        """, (rating_id,))
        rating = cursor.fetchone()

        if rating and rating.get('rating_time'):
            rating['rating_time'] = rating['rating_time'].isoformat()

        return rating
    except Exception as e:
        print(f"获取评分失败: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def add_rating(user_id, movie_id, score):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO rating (user_id, movie_id, score) VALUES (?, ?, ?)",
            (user_id, movie_id, score)
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cursor.fetchone()
        conn.commit()
        return int(row["id"]) if row and row["id"] else None
    except Exception as e:
        print(f"添加评分失败: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_rating(rating_id, score):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE rating SET score=? WHERE rating_id=?", (score, rating_id))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"更新评分失败: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def delete_rating(rating_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM rating WHERE rating_id=?", (rating_id,))
        conn.commit()
        affected = cursor.rowcount
        return affected
    except Exception as e:
        print(f"删除评分失败: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def search_ratings(search_term=None, score=None, date=None, page=1, limit=10, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where = "WHERE 1=1"
        params = []

        if user_id is not None:
            where += " AND r.user_id = ?"
            params.append(user_id)

        if search_term:
            where += " AND (u.username LIKE ? OR u.nickname LIKE ? OR m.title LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])

        if score:
            where += " AND r.score = ?"
            params.append(score)

        if date:
            where += " AND CAST(r.rating_time AS DATE) = ?"
            params.append(date)

        base = f"""
        SELECT r.*, u.username, u.nickname, m.title as movie_title
        FROM rating r
        LEFT JOIN [user] u ON r.user_id = u.user_id
        LEFT JOIN movie m ON r.movie_id = m.movie_id
        {where}
        """

        cursor.execute(f"SELECT COUNT(*) AS total FROM ({base}) AS t", params)
        total = cursor.fetchone()["total"]

        offset = (page - 1) * limit
        cursor.execute(
            base + " ORDER BY r.rating_time DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            params + [offset, limit]
        )
        ratings = cursor.fetchall()

        for rating in ratings:
            if rating.get("rating_time"):
                rating["rating_time"] = rating["rating_time"].isoformat()

        return ratings, total
    except Exception as e:
        print(f"搜索评分错误: {e}")
        return [], 0
    finally:
        cursor.close()
        conn.close()

