from db_config import get_connection

def get_history_count():
    conn = get_connection()
    if conn is None:
        print("数据库连接失败 - get_history_count")
        return 0

    cursor = conn.cursor()
    try:
        print("正在执行SQL: SELECT COUNT(*) as count FROM history")
        cursor.execute("SELECT COUNT(*) as count FROM history;")
        result = cursor.fetchone()
        print(f"历史记录数量查询结果: {result}")
        # 修复：使用字典键名 'count' 而不是数字索引 0
        return result['count'] if result else 0
    except Exception as e:
        print(f"获取历史记录数量错误: {e}")
        print(f"错误类型: {type(e)}")
        import traceback
        print("完整错误堆栈:")
        traceback.print_exc()
        return 0
    finally:
        cursor.close()
        conn.close()

def get_all_history():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.*, u.username, u.nickname, m.title as movie_title 
            FROM history h 
            LEFT JOIN [user] u ON h.user_id = u.user_id 
            LEFT JOIN movie m ON h.movie_id = m.movie_id
            ORDER BY h.watch_time DESC
        """)
        history = cursor.fetchall()

        # 处理日期格式
        for record in history:
            if record.get('watch_time'):
                record['watch_time'] = record['watch_time'].isoformat()

        return history
    except Exception as e:
        print(f"获取历史记录失败: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_history_by_id(history_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.*, u.username, u.nickname, m.title as movie_title 
            FROM history h 
            LEFT JOIN [user] u ON h.user_id = u.user_id 
            LEFT JOIN movie m ON h.movie_id = m.movie_id
            WHERE h.history_id = ?
        """, (history_id,))
        history = cursor.fetchone()

        if history and history.get('watch_time'):
            history['watch_time'] = history['watch_time'].isoformat()

        return history
    except Exception as e:
        print(f"获取历史记录失败: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def add_history(user_id, movie_id, duration_watched=None, completed=False):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO history (user_id, movie_id, duration_watched, completed) VALUES (?, ?, ?, ?)",
            (user_id, movie_id, duration_watched, 1 if completed else 0)
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cursor.fetchone()
        conn.commit()
        return int(row["id"]) if row and row["id"] else None
    except Exception as e:
        print(f"添加历史记录失败: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_history(history_id, duration_watched=None, completed=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if duration_watched is not None:
            updates.append("duration_watched=?")
            params.append(duration_watched)
        if completed is not None:
            updates.append("completed=?")
            params.append(1 if completed else 0)
        if not updates:
            return 0
        sql = "UPDATE history SET " + ", ".join(updates) + " WHERE history_id=?"
        params.append(history_id)
        cursor.execute(sql, params)
        conn.commit()
        affected = cursor.rowcount
        return affected
    except Exception as e:
        print(f"更新历史记录失败: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def delete_history(history_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM history WHERE history_id=?", (history_id,))
        conn.commit()
        affected = cursor.rowcount
        return affected
    except Exception as e:
        print(f"删除历史记录失败: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def search_history(search_term=None, completed=None, date=None, page=1, limit=10, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where = "WHERE 1=1"
        params = []

        if user_id is not None:
            where += " AND h.user_id = ?"
            params.append(user_id)

        if search_term:
            where += " AND (u.username LIKE ? OR u.nickname LIKE ? OR m.title LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])

        if completed is not None:
            where += " AND h.completed = ?"
            params.append(1 if completed else 0)

        if date:
            where += " AND CAST(h.watch_time AS DATE) = ?"
            params.append(date)

        base = f"""
        SELECT h.*, u.username, u.nickname, m.title as movie_title
        FROM history h
        LEFT JOIN [user] u ON h.user_id = u.user_id
        LEFT JOIN movie m ON h.movie_id = m.movie_id
        {where}
        """

        cursor.execute(f"SELECT COUNT(*) AS total FROM ({base}) AS t", params)
        total = cursor.fetchone()["total"]

        offset = (page - 1) * limit
        cursor.execute(
            base + " ORDER BY h.watch_time DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            params + [offset, limit]
        )
        history = cursor.fetchall()

        for record in history:
            if record.get("watch_time"):
                record["watch_time"] = record["watch_time"].isoformat()

        return history, total
    except Exception as e:
        print(f"搜索历史记录错误: {e}")
        return [], 0
    finally:
        cursor.close()
        conn.close()

