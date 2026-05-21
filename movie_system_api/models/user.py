from db_config import get_connection


def get_users_count():
    conn = get_connection()
    if conn is None:
        print("数据库连接失败 - get_users_count")
        return 0

    cursor = conn.cursor()
    try:
        print("正在执行SQL: SELECT COUNT(*) as count FROM user")
        cursor.execute("SELECT COUNT(*) as count FROM [user];")
        result = cursor.fetchone()
        print(f"用户数量查询结果: {result}")
        # 修复：使用字典键名 'count' 而不是数字索引 0
        return result['count'] if result else 0
    except Exception as e:
        print(f"获取用户数量错误: {e}")
        print(f"错误类型: {type(e)}")
        import traceback
        print("完整错误堆栈:")
        traceback.print_exc()
        return 0
    finally:
        cursor.close()
        conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 使用 LEFT JOIN 获取偏好类型名称
        sql = """
        SELECT u.*, g.genre_name as favorite_genre_name 
        FROM [user] u 
        LEFT JOIN genre g ON u.favorite_genre_id = g.genre_id
        ORDER BY u.register_date DESC
        """
        cursor.execute(sql)
        users = cursor.fetchall()

        # 处理日期格式
        for user in users:
            if user.get('register_date'):
                user['register_date'] = user['register_date'].isoformat()

        return users
    except Exception as e:
        print(f"获取用户列表错误: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        sql = """
        SELECT u.*, g.genre_name as favorite_genre_name 
        FROM [user] u 
        LEFT JOIN genre g ON u.favorite_genre_id = g.genre_id 
        WHERE u.user_id=?
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()

        if user and user.get('register_date'):
            user['register_date'] = user['register_date'].isoformat()

        return user
    except Exception as e:
        print(f"获取用户错误: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM [user] WHERE username=?;", (username,))
        user = cursor.fetchone()
        return user
    except Exception as e:
        print(f"通过用户名获取用户错误: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def add_user(username, password_hash, nickname=None, age=None, gender=None, favorite_genre_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO [user] (username, password_hash, nickname, age, gender, favorite_genre_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (username, password_hash, nickname, age, gender, favorite_genre_id)
        )
        cursor.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cursor.fetchone()
        conn.commit()
        return int(row["id"]) if row and row["id"] else None
    except Exception as e:
        print(f"添加用户错误: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_user(user_id, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key}=?")
                params.append(value)

        if not updates:
            return 0

        sql = "UPDATE [user] SET " + ", ".join(updates) + " WHERE user_id=?;"
        params.append(user_id)
        cursor.execute(sql, params)
        conn.commit()
        affected = cursor.rowcount
        return affected
    except Exception as e:
        print(f"更新用户错误: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM [user] WHERE user_id=?;", (user_id,))
        conn.commit()
        affected = cursor.rowcount
        return affected
    except Exception as e:
        print(f"删除用户错误: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def search_users(search_term=None, gender=None, favorite_genre=None, page=1, limit=10):
    conn = get_connection()
    if conn is None:
        print("数据库连接失败 - search_users")
        return [], 0

    cursor = conn.cursor()
    try:
        # 基础查询 - 确保所有必要字段都被选择
        where = "WHERE 1=1"
        params = []

        if search_term:
            where += " AND (u.username LIKE ? OR u.nickname LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])

        if gender:
            where += " AND u.gender = ?"
            params.append(gender)

        if favorite_genre:
            where += " AND u.favorite_genre_id = ?"
            params.append(int(favorite_genre))

        base_sql = f"""
        SELECT 
            u.user_id, u.username, u.nickname, u.age, u.gender,
            u.favorite_genre_id, u.register_date,
            g.genre_name as favorite_genre_name 
        FROM [user] u 
        LEFT JOIN genre g ON u.favorite_genre_id = g.genre_id
        {where}
        """

        cursor.execute(f"SELECT COUNT(*) as total FROM ({base_sql}) AS t", params)
        total = cursor.fetchone()["total"]

        offset = (page - 1) * limit
        cursor.execute(
            base_sql + " ORDER BY u.register_date DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            params + [offset, limit]
        )
        users = cursor.fetchall()

        print(f"查询到用户数量: {len(users)}")

        # 处理日期格式并确保字段存在
        for user in users:
            if user.get('register_date'):
                user['register_date'] = user['register_date'].isoformat()
            # 确保所有字段都存在
            user.setdefault('favorite_genre_name', None)
            user.setdefault('nickname', None)
            user.setdefault('age', None)
            user.setdefault('gender', None)

        return users, total
    except Exception as e:
        print(f"搜索用户错误: {e}")
        import traceback
        traceback.print_exc()
        return [], 0
    finally:
        cursor.close()
        conn.close()