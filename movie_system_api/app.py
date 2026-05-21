import functools
import os
import time

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS

from db_config import get_connection, ping_database, pool_stats
from ops.crypto import hash_password, verify_password
from ops.rate_limit import limiter

try:
    from models import recommendation as recommendation_model
except ImportError:
    import sys

    sys.path.append("models")
    import recommendation as recommendation_model
from models import history as history_model
from models import movie as movie_model
from models import rating as rating_model
from models import user as user_model

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")
CORS(app)

LOGIN_RATE_LIMIT = int(os.environ.get("LOGIN_RATE_LIMIT", "10"))
LOGIN_RATE_WINDOW = int(os.environ.get("LOGIN_RATE_WINDOW", "60"))


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit_auth(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        key = f"auth:{_client_ip()}:{request.path}"
        if not limiter.allow(key, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW):
            retry = limiter.retry_after(key, LOGIN_RATE_WINDOW)
            return jsonify({"success": False, "message": f"请求过于频繁，请 {retry} 秒后重试"}), 429
        return view(*args, **kwargs)

    return wrapper


def get_admin_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM admin WHERE username=%s;", (username,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


# 添加缓存装饰器
def cache_response(timeout=300):  # 5分钟缓存
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(kwargs)}"

            # 检查缓存
            cache = getattr(g, '_cache', {})
            if cache_key in cache:
                cached_data, timestamp = cache[cache_key]
                if time.time() - timestamp < timeout:
                    return cached_data

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            if not hasattr(g, '_cache'):
                g._cache = {}
            g._cache[cache_key] = (result, time.time())

            return result

        return wrapper

    return decorator

# =======================
# 页面路由
# =======================
@app.route("/")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=['GET'])
def register_page():
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/index.html")


@app.route("/movies")
def movies_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/movies.html")


@app.route("/users")
def users_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))
    return render_template("dashboard/users.html")


@app.route("/ratings")
def ratings_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/ratings.html")


@app.route("/history")
def history_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/history.html")


@app.route("/profile")
def profile_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/profile.html")


@app.route("/settings")
def settings_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("dashboard/settings.html")


@app.route("/ops")
def ops_page():
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("dashboard"))
    return render_template("dashboard/ops.html")


# =======================
# 个人资料 API
# =======================
@app.route("/api/profile", methods=["GET"])
def get_profile():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        role = session.get("role", "user")
        if role == "admin":
            admin = get_admin_by_username(session.get("username", ""))
            if not admin:
                return jsonify({"error": "找不到管理员信息"}), 404
            return jsonify({
                "user_id": admin["admin_id"],
                "username": admin["username"],
                "nickname": admin.get("nickname") or admin["username"],
                "role": "admin",
                "register_date": None,
            })
        user = user_model.get_user_by_id(session["user_id"])
        if not user:
            return jsonify({"error": "找不到用户"}), 404
        user.pop("password_hash", None)
        user["role"] = "user"
        return jsonify(user)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profile", methods=["PUT"])
def update_profile():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "未授权"}), 401
    try:
        data = request.get_json() or {}
        role = session.get("role", "user")
        if role == "admin":
            return jsonify({"success": False, "message": "管理员暂不支持修改资料"}), 403
        allowed = {k: v for k, v in data.items() if k in ("nickname", "age", "gender", "favorite_genre_id")}
        if not allowed:
            return jsonify({"success": False, "message": "无有效字段"}), 400
        rows = user_model.update_user(session["user_id"], **allowed)
        if rows:
            return jsonify({"success": True, "message": "资料已更新"})
        return jsonify({"success": False, "message": "未作任何修改"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/change-password", methods=["POST"])
def change_password():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "未授权"}), 401
    try:
        data = request.get_json() or {}
        old_pwd = data.get("old_password", "")
        new_pwd = data.get("new_password", "")
        if not old_pwd or not new_pwd:
            return jsonify({"success": False, "message": "密码不能为空"}), 400
        if len(new_pwd) < 8:
            return jsonify({"success": False, "message": "新密码至少 8 位"}), 400
        role = session.get("role", "user")
        if role == "admin":
            admin = get_admin_by_username(session.get("username", ""))
            if not admin or not verify_password(old_pwd, admin.get("password_hash")):
                return jsonify({"success": False, "message": "当前密码不正确"}), 401
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE admin SET password_hash=%s WHERE admin_id=%s", (hash_password(new_pwd), admin["admin_id"]))
                conn.commit()
            finally:
                cursor.close(); conn.close()
        else:
            user = user_model.get_user_by_id(session["user_id"])
            if not user or not verify_password(old_pwd, user.get("password_hash")):
                return jsonify({"success": False, "message": "当前密码不正确"}), 401
            user_model.update_user(session["user_id"], password_hash=hash_password(new_pwd))
        return jsonify({"success": True, "message": "密码已更新，请重新登录"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =======================
# 运维 Ops API
# =======================
@app.route("/api/ops/status", methods=["GET"])
def ops_status():
    if not session.get("user_id") or session.get("role") != "admin":
        return jsonify({"error": "仅管理员可访问"}), 403
    import os as _os
    from ops.crypto import Fernet
    enc_enabled = bool(Fernet and _os.environ.get("APP_ENCRYPTION_KEY", "").strip())
    return jsonify({
        "encryption_key_set": enc_enabled,
        "login_rate_limit": int(_os.environ.get("LOGIN_RATE_LIMIT", "10")),
        "login_rate_window": int(_os.environ.get("LOGIN_RATE_WINDOW", "60")),
        "pool": pool_stats(),
        "db_alive": ping_database(),
        "backup_keep_count": int(_os.environ.get("BACKUP_KEEP_COUNT", "7")),
        "backup_dir": _os.environ.get("BACKUP_DIR", "./backups"),
        "waitress_threads": int(_os.environ.get("WAITRESS_THREADS", "8")),
    })


@app.route("/api/ops/backup", methods=["POST"])
def ops_backup():
    if not session.get("user_id") or session.get("role") != "admin":
        return jsonify({"success": False, "message": "仅管理员可操作"}), 403
    import os as _os
    from ops.backup import backup_full_database, export_tables_json
    server = _os.environ.get("SQL_SERVER", "localhost")
    database = _os.environ.get("SQL_DATABASE", "movie_system")
    backup_dir = _os.environ.get("BACKUP_DIR", "./backups")
    data = request.get_json() or {}
    btype = data.get("type", "full")
    try:
        if btype == "json":
            path = export_tables_json(server, database, backup_dir)
            return jsonify({"success": True, "json_file": str(path)})
        # 全库备份：先尝试 T-SQL .bak，权限不足时自动降级为 JSON 导出
        try:
            path = backup_full_database(server, database, backup_dir)
            return jsonify({"success": True, "bak_file": str(path)})
        except Exception:
            path = export_tables_json(server, database, backup_dir)
            return jsonify({"success": True, "bak_file": str(path),
                            "note": "已降级为JSON导出（SQL Server服务账号无写入权限）"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/ops/export-download", methods=["GET"])
def ops_export_download():
    """直接将数据库全量数据导出为 JSON 文件并推送到浏览器下载"""
    if not session.get("user_id") or session.get("role") != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403
    import os as _os
    from ops.backup import export_tables_json
    from flask import send_file
    server   = _os.environ.get("SQL_SERVER", "localhost")
    database = _os.environ.get("SQL_DATABASE", "movie_system")
    backup_dir = _os.environ.get("BACKUP_DIR", "./backups")
    try:
        path = export_tables_json(server, database, backup_dir)
        return send_file(str(path.resolve()), mimetype="application/json",
                         as_attachment=True, download_name=path.name)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =======================
# 登录注册 API
# =======================
@app.route("/api/health", methods=["GET"])
def health_liveness():
    return jsonify({"status": "ok", "service": "movie-recommendation-api"})


@app.route("/api/health/ready", methods=["GET"])
def health_readiness():
    if ping_database():
        return jsonify({"status": "ready", "database": "connected", "pool": pool_stats()})
    return jsonify({"status": "not_ready", "database": "disconnected"}), 503


@app.route("/api/login", methods=["POST"])
@rate_limit_auth
def login():
    try:
        # 检查请求内容类型
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # 如果是从表单提交，使用form数据
            data = request.form

        username = data.get("username")
        password = data.get("password")
        role = data.get("role", "user")

        print(f"登录尝试 - 用户名: {username}, 身份: {role}")

        if not username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

        if role == "admin":
            admin = get_admin_by_username(username)
            if admin and verify_password(password, admin.get("password_hash")):
                session["user_id"] = admin["admin_id"]
                session["admin_id"] = admin["admin_id"]
                session["username"] = admin["username"]
                session["role"] = "admin"
                print(f"管理员登录成功 - 管理员ID: {admin['admin_id']}")
                return jsonify({"success": True, "message": "管理员登录成功", "role": "admin"})
        else:
            user = user_model.get_user_by_username(username)
            if user and verify_password(password, user.get("password_hash")):
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                session["role"] = "user"
                print(f"用户登录成功 - 用户ID: {user['user_id']}")
                return jsonify({"success": True, "message": "用户登录成功", "role": "user"})

        print("登录失败 - 用户名或密码错误")
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401
    except Exception as e:
        print(f"登录异常: {str(e)}")
        return jsonify({"success": False, "message": f"登录失败: {str(e)}"}), 500


@app.route("/api/register", methods=["POST"])
@rate_limit_auth
def register():
    try:
        print("收到注册请求")

        # 检查请求内容类型
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # 如果是从表单提交，使用form数据
            data = request.form.to_dict()

        print(f"注册数据: {data}")

        username = data.get("username")
        password = data.get("password")
        nickname = data.get("nickname")
        age = data.get("age")
        gender = data.get("gender")
        role = data.get("role", "user")
        admin_code = data.get("admin_code", "")

        if not username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

        if len(username) < 3:
            return jsonify({"success": False, "message": "用户名至少需要3个字符"}), 400

        if len(password) < 6:
            return jsonify({"success": False, "message": "密码至少需要6个字符"}), 400

        # ── 管理员注册路径 ──
        if role == "admin":
            # 检查管理员用户名是否已存在
            existing_admin = get_admin_by_username(username)
            if existing_admin:
                return jsonify({"success": False, "message": "管理员用户名已存在"}), 400
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO dbo.admin (username, password_hash) VALUES (?, ?)",
                    (username, hash_password(password))
                )
                conn.commit()
                cur.execute("SELECT admin_id FROM dbo.admin WHERE username=?", (username,))
                row = cur.fetchone()
                admin_id = row["admin_id"] if row else None
            finally:
                cur.close(); conn.close()
            if admin_id:
                session["user_id"] = admin_id
                session["admin_id"] = admin_id
                session["username"] = username
                session["role"] = "admin"
                print(f"管理员注册成功 - ID: {admin_id}")
                return jsonify({"success": True, "message": "管理员注册成功", "role": "admin"})
            return jsonify({"success": False, "message": "注册失败"}), 500

        # ── 普通用户注册路径 ──
        existing_user = user_model.get_user_by_username(username)
        if existing_user:
            return jsonify({"success": False, "message": "用户名已存在"}), 400

        # 处理年龄字段
        if age:
            try:
                age = int(age)
            except ValueError:
                age = None

        # 添加用户
        user_id = user_model.add_user(
            username=username,
            password_hash=hash_password(password),
            nickname=nickname,
            age=age,
            gender=gender
        )

        if user_id:
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = "user"
            print(f"注册成功 - 用户ID: {user_id}")
            return jsonify({"success": True, "message": "注册成功", "role": "user"})
        else:
            print("注册失败 - 数据库插入失败")
            return jsonify({"success": False, "message": "注册失败"}), 500

    except Exception as e:
        print(f"注册异常: {str(e)}")
        return jsonify({"success": False, "message": f"注册失败: {str(e)}"}), 500


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("admin_id", None)
    session.pop("username", None)
    session.pop("role", None)
    flash("您已成功退出登录", "success")
    return redirect(url_for("login_page"))


# =======================
# Dashboard API
# =======================
@app.route("/api/dashboard/stats")
def dashboard_stats():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        print("开始获取仪表盘统计数据...")

        # 添加数据库连接检查
        try:
            test_conn = get_connection()
            if test_conn is None:
                return jsonify({"error": "数据库连接失败"}), 500
            test_conn.close()
        except Exception as e:
            print(f"数据库连接测试失败: {str(e)}")
            return jsonify({"error": "数据库连接失败"}), 500

        # 原有的统计代码...
        total_movies = movie_model.get_movies_count()
        total_users = user_model.get_users_count()
        total_ratings = rating_model.get_ratings_count()
        total_history = history_model.get_history_count()

        return jsonify({
            "total_movies": total_movies,
            "total_users": total_users,
            "total_ratings": total_ratings,
            "total_history": total_history
        })
    except Exception as e:
        print(f"获取仪表盘统计数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# =======================
# Movie API
# =======================

@app.route("/api/movies", methods=["GET"])
def get_movies():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        year = request.args.get('year', '')
        genre = request.args.get('genre', '')

        print(f"获取电影列表 - 页码: {page}, 搜索: {search}, 年份: {year}, 类型: {genre}")

        # 使用新的搜索方法
        movies, total = movie_model.search_movies(
            search_term=search if search else None,
            year=year if year else None,
            genre_id=genre if genre else None,
            page=page,
            limit=limit
        )

        print(f"查询结果: 找到 {len(movies)} 个电影, 总数: {total}")

        return jsonify({
            "movies": movies,
            "total": total,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        print(f"获取电影列表错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/movies/top")
def get_top_movies():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        limit = request.args.get('limit', 5, type=int)
        movies = movie_model.get_all_movies()
        # 按评分排序取前N个
        sorted_movies = sorted(movies, key=lambda x: x.get('avg_score', 0), reverse=True)
        return jsonify({"movies": sorted_movies[:limit]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/movies/<int:movie_id>", methods=["GET"])
def get_movie(movie_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        movie = movie_model.get_movie_by_id(movie_id)
        if movie:
            return jsonify(movie)
        return jsonify({"error": "Movie not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/movies", methods=["POST"])
def add_movie():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403

    try:
        data = request.json
        print(f"添加电影数据: {data}")

        # 验证必需字段
        if not data.get('title'):
            return jsonify({"error": "电影名称不能为空"}), 400

        # 处理类型数据
        genre_ids = data.get('genre_ids', [])
        if isinstance(genre_ids, str):
            genre_ids = [int(id) for id in genre_ids.split(',')] if genre_ids else []

        movie_id = movie_model.add_movie(
            title=data.get('title'),
            release_year=data.get('release_year'),
            language=data.get('language'),
            duration=data.get('duration'),
            director=data.get('director'),
            description=data.get('description'),
            genre_ids=genre_ids
        )

        if movie_id:
            return jsonify({"message": "电影添加成功", "movie_id": movie_id}), 201
        else:
            return jsonify({"error": "添加电影失败"}), 500
    except Exception as e:
        print(f"添加电影异常: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/movies/<int:movie_id>", methods=["PUT"])
def update_movie(movie_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403

    try:
        data = request.json
        print(f"更新电影数据: {data}")

        # 处理类型数据
        genre_ids = data.get('genre_ids', [])
        if isinstance(genre_ids, str):
            genre_ids = [int(id) for id in genre_ids.split(',')] if genre_ids else []

        rows = movie_model.update_movie(
            movie_id,
            title=data.get('title'),
            release_year=data.get('release_year'),
            language=data.get('language'),
            duration=data.get('duration'),
            director=data.get('director'),
            description=data.get('description'),
            genre_ids=genre_ids
        )

        if rows:
            return jsonify({"message": "电影更新成功"})
        return jsonify({"error": "电影未找到"}), 404
    except Exception as e:
        print(f"更新电影异常: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/movies/<int:movie_id>", methods=["DELETE"])
def delete_movie(movie_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    if session.get("role") != "admin":
        return jsonify({"error": "仅管理员可操作"}), 403

    try:
        rows = movie_model.delete_movie(movie_id)
        if rows:
            return jsonify({"message": "电影删除成功"})
        return jsonify({"error": "电影未找到"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =======================
# User API
# =======================
@app.route("/api/users", methods=["GET"])
def get_users_list():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        gender = request.args.get('gender', '')
        favorite_genre = request.args.get('favorite_genre', '')

        print(f"获取用户列表 - 页码: {page}, 搜索: {search}, 性别: {gender}, 偏好类型: {favorite_genre}")

        # 使用新的搜索方法
        users, total = user_model.search_users(
            search_term=search if search else None,
            gender=gender if gender else None,
            favorite_genre=favorite_genre if favorite_genre else None,
            page=page,
            limit=limit
        )

        print(f"查询结果: 找到 {len(users)} 个用户, 总数: {total}")

        # 添加调试信息，显示前几个用户的数据
        if users:
            print("前几个用户数据:")
            for i, user in enumerate(users[:3]):
                print(f"用户 {i + 1}: {user}")

        return jsonify({
            "users": users,
            "total": total,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        print(f"获取用户列表错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/recent")
def get_recent_users_list():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        limit = request.args.get('limit', 5, type=int)
        users = user_model.get_all_users()
        # 按注册时间排序取最新用户
        sorted_users = sorted(users, key=lambda x: x.get('register_date', ''), reverse=True)
        return jsonify({"users": sorted_users[:limit]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_single_user(user_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        user = user_model.get_user_by_id(user_id)
        if user:
            return jsonify(user)
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users", methods=["POST"])
def add_new_user():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        data = request.json
        print(f"添加用户数据: {data}")

        # 验证必需字段
        if not data.get('username') or not data.get('password'):
            return jsonify({"error": "用户名和密码不能为空"}), 400

        # 检查用户名是否已存在
        existing_user = user_model.get_user_by_username(data['username'])
        if existing_user:
            return jsonify({"error": "用户名已存在"}), 400

        # 密码加密
        data['password_hash'] = hash_password(data['password'])
        del data['password']

        # 处理可选字段
        user_data = {
            'username': data['username'],
            'password_hash': data['password_hash'],
            'nickname': data.get('nickname'),
            'age': data.get('age'),
            'gender': data.get('gender'),
            'favorite_genre_id': data.get('favorite_genre_id')
        }

        user_id = user_model.add_user(**user_data)
        if user_id:
            return jsonify({"message": "用户添加成功", "user_id": user_id}), 201
        else:
            return jsonify({"error": "添加用户失败"}), 500
    except Exception as e:
        print(f"添加用户异常: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["PUT"])
def update_existing_user(user_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        data = request.json
        print(f"更新用户数据: {data}")

        # 密码加密
        if 'password' in data and data['password']:
            data['password_hash'] = hash_password(data['password'])
            del data['password']

        # 构建更新数据
        update_data = {}
        for key in ['username', 'password_hash', 'nickname', 'age', 'gender', 'favorite_genre_id']:
            if key in data:
                update_data[key] = data[key]

        rows = user_model.update_user(user_id, **update_data)
        if rows:
            return jsonify({"message": "用户更新成功"})
        return jsonify({"error": "用户未找到"}), 404
    except Exception as e:
        print(f"更新用户异常: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_existing_user(user_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        rows = user_model.delete_user(user_id)
        if rows:
            return jsonify({"message": "用户删除成功"})
        return jsonify({"error": "用户未找到"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================
# Rating API
# =======================
@app.route("/api/ratings", methods=["GET"])
def get_ratings():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        score = request.args.get('score', '')
        date = request.args.get('date', '')

        # 所有登录用户都能查看全部评分（写操作仍有所有权校验）
        uid_filter = None
        ratings, total = rating_model.search_ratings(
            search_term=search if search else None,
            score=int(score) if score else None,
            date=date if date else None,
            page=page,
            limit=limit,
            user_id=uid_filter
        )

        return jsonify({
            "ratings": ratings,
            "total": total,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        print(f"获取评分列表错误: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/ratings", methods=["POST"])
def add_rating():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    data = request.json or {}
    movie_id = data.get("movie_id")
    score = data.get("score")
    if not movie_id or score is None:
        return jsonify({"error": "缺少 movie_id 或 score"}), 400
    try:
        score = float(score)
        if not (0.5 <= score <= 5.0):
            return jsonify({"error": "评分必须在 0.5-5.0 之间"}), 400
        uid = session["user_id"]
        rating_id = rating_model.add_rating(uid, movie_id, score)
        if rating_id:
            return jsonify({"message": "评分添加成功", "rating_id": rating_id}), 201
        return jsonify({"error": "添加失败，该电影可能已评分"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 添加获取单个评分的路由
@app.route("/api/ratings/<int:rating_id>", methods=["GET"])
def get_rating(rating_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        rating = rating_model.get_rating_by_id(rating_id)
        if rating:
            return jsonify(rating)
        return jsonify({"error": "评分记录未找到"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 添加更新评分的路由
@app.route("/api/ratings/<int:rating_id>", methods=["PUT"])
def update_rating(rating_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        existing = rating_model.get_rating_by_id(rating_id)
        if not existing:
            return jsonify({"error": "评分记录未找到"}), 404
        if session.get("role") != "admin" and existing.get("user_id") != session["user_id"]:
            return jsonify({"error": "无权修改他人的评分"}), 403
        data = request.json
        score = float(data.get("score", 0))
        if not (0.5 <= score <= 5.0):
            return jsonify({"error": "评分必须在 0.5-5.0 之间"}), 400
        rows = rating_model.update_rating(rating_id, score)
        if rows:
            return jsonify({"message": "评分更新成功"})
        return jsonify({"error": "更新失败"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 添加删除评分的路由
@app.route("/api/ratings/<int:rating_id>", methods=["DELETE"])
def delete_rating(rating_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        existing = rating_model.get_rating_by_id(rating_id)
        if not existing:
            return jsonify({"error": "评分记录未找到"}), 404
        if session.get("role") != "admin" and existing.get("user_id") != session["user_id"]:
            return jsonify({"error": "无权删除他人的评分"}), 403
        rows = rating_model.delete_rating(rating_id)
        if rows:
            return jsonify({"message": "评分删除成功"})
        return jsonify({"error": "删除失败"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# =======================
# History API
# =======================
@app.route("/api/history", methods=["GET"])
def get_history():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        completed = request.args.get('completed', '')
        date = request.args.get('date', '')

        # 处理 completed 参数
        completed_param = None
        if completed.lower() == 'true':
            completed_param = True
        elif completed.lower() == 'false':
            completed_param = False

        # 所有登录用户都能查看全部记录（写操作仍有所有权校验）
        uid_filter = None
        history, total = history_model.search_history(
            search_term=search if search else None,
            completed=completed_param,
            date=date if date else None,
            page=page,
            limit=limit,
            user_id=uid_filter
        )

        return jsonify({
            "history": history,
            "total": total,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        print(f"获取历史记录列表错误: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/history/<int:history_id>", methods=["GET"])
def get_single_history(history_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        history = history_model.get_history_by_id(history_id)
        if history:
            return jsonify(history)
        return jsonify({"error": "历史记录未找到"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history", methods=["POST"])
def add_history():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    data = request.json or {}
    movie_id = data.get("movie_id")
    if not movie_id:
        return jsonify({"error": "缺少 movie_id"}), 400
    try:
        uid = session["user_id"]
        duration = data.get("duration_watched")
        completed = bool(data.get("completed", False))
        history_id = history_model.add_history(uid, movie_id, duration, completed)
        if history_id:
            return jsonify({"message": "观看记录添加成功", "history_id": history_id}), 201
        return jsonify({"error": "添加失败"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<int:history_id>", methods=["PUT"])
def update_history(history_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        existing = history_model.get_history_by_id(history_id)
        if not existing:
            return jsonify({"error": "历史记录未找到"}), 404
        if session.get("role") != "admin" and existing.get("user_id") != session["user_id"]:
            return jsonify({"error": "无权修改他人的记录"}), 403
        data = request.json
        rows = history_model.update_history(history_id, data.get("duration_watched"), data.get("completed"))
        if rows:
            return jsonify({"message": "历史记录更新成功"})
        return jsonify({"error": "更新失败"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<int:history_id>", methods=["DELETE"])
def delete_history(history_id):
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        existing = history_model.get_history_by_id(history_id)
        if not existing:
            return jsonify({"error": "历史记录未找到"}), 404
        if session.get("role") != "admin" and existing.get("user_id") != session["user_id"]:
            return jsonify({"error": "无权删除他人的记录"}), 403
        rows = history_model.delete_history(history_id)
        if rows:
            return jsonify({"message": "历史记录删除成功"})
        return jsonify({"error": "删除失败"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================
# Genre API (添加这个新的API路由)
# =======================
@app.route("/api/genres", methods=["GET"])
def get_genres():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        # 这里需要根据您的数据库结构实现获取类型列表
        # 假设有一个 genre 表
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM genre ORDER BY genre_name;")
        genres = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({"genres": genres})
    except Exception as e:
        print(f"获取类型列表错误: {str(e)}")
        # 返回一个默认的类型列表作为fallback
        default_genres = [
            {"genre_id": 1, "genre_name": "动作"},
            {"genre_id": 2, "genre_name": "喜剧"},
            {"genre_id": 3, "genre_name": "剧情"},
            {"genre_id": 4, "genre_name": "科幻"},
            {"genre_id": 5, "genre_name": "恐怖"}
        ]
        return jsonify({"genres": default_genres})


# =======================
# Dashboard Chart Data API (添加这个API路由)
# =======================
@app.route("/api/dashboard/chart-data")
def dashboard_chart_data():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        # 这里返回一些示例数据
        # 实际项目中应该从数据库获取真实数据
        return jsonify({
            "labels": ["1月", "2月", "3月", "4月", "5月", "6月"],
            "users": [65, 59, 80, 81, 56, 55],
            "movies": [28, 48, 40, 19, 86, 27]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================
# Dashboard Recent Activities API
# =======================
@app.route("/api/dashboard/recent-activities")
def dashboard_recent_activities():
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        # 这里返回一些示例数据
        # 实际项目中应该从数据库获取真实数据
        activities = [
            {
                "type": "user",
                "title": "新用户注册",
                "time": "2024-01-15T10:30:00"
            },
            {
                "type": "rating",
                "title": "用户对《电影A》评分",
                "time": "2024-01-15T09:15:00"
            },
            {
                "type": "movie",
                "title": "新电影《电影B》添加",
                "time": "2024-01-14T16:45:00"
            }
        ]
        return jsonify({"activities": activities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =======================
# Recommendation API
# =======================
@app.route("/recommendations")
def recommendations_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("recommendations.html", username=session.get('username'))

# 优化推荐API - 添加缓存和异步
@app.route("/api/recommendations", methods=["GET"])
@cache_response(timeout=300)  # 缓存5分钟
def get_recommendations():
    """获取个性化推荐"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        user_id = session.get("user_id")
        limit = request.args.get('limit', 10, type=int)
        method = request.args.get('method', 'hybrid')

        # 获取推荐
        recommendations = recommendation_model.get_recommendations_for_user(
            user_id=user_id,
            limit=limit,
            method=method
        )

        return jsonify({
            "recommendations": recommendations,
            "total": len(recommendations),
            "method": method
        })

    except Exception as e:
        print(f"获取推荐失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/recommendations/popular", methods=["GET"])
def get_popular_recommendations():
    """获取热门推荐"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        limit = request.args.get('limit', 10, type=int)

        popular_movies = recommendation_model.get_popular_movies(limit=limit)

        return jsonify({
            "movies": popular_movies,
            "total": len(popular_movies),
            "type": "popular"
        })

    except Exception as e:
        print(f"获取热门推荐失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations/similar/<int:movie_id>", methods=["GET"])
def get_similar_movies(movie_id):
    """获取相似电影"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        limit = request.args.get('limit', 10, type=int)

        similar_movies = recommendation_model.get_similar_movies(
            movie_id=movie_id,
            limit=limit
        )

        return jsonify({
            "similar_movies": similar_movies,
            "total": len(similar_movies),
            "original_movie_id": movie_id
        })

    except Exception as e:
        print(f"获取相似电影失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations/train", methods=["POST"])
def train_recommendation_model():
    """训练推荐模型（管理员权限）"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    # 这里可以添加管理员权限检查
    try:
        from models.recommendation_model import recommender

        success = recommender.train_hybrid_model()

        if success:
            return jsonify({
                "message": "推荐模型训练成功",
                "status": "success"
            })
        else:
            return jsonify({
                "error": "模型训练失败",
                "status": "error"
            }), 500

    except Exception as e:
        print(f"训练模型失败: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations/stats", methods=["GET"])
def get_recommendation_stats():
    """获取推荐系统统计信息"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401

    try:
        from models.recommendation_model import recommender

        stats = recommendation_model.get_recommendation_stats()

        return jsonify(stats)

    except Exception as e:
        print(f"获取推荐统计失败: {str(e)}")
        return jsonify({"error": str(e)}), 500



# =======================
# 数据库高级特性 API（视图 / 存储过程）
# =======================

@app.route("/api/db/movie-stats", methods=["GET"])
def api_movie_stats():
    """查询 vw_movie_stats 视图：带评分统计的电影列表"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        limit = int(request.args.get("limit", 20))
        sort = request.args.get("sort", "rating_count")
        allowed_sort = {"rating_count", "avg_score", "watch_count", "movie_id"}
        if sort not in allowed_sort:
            sort = "rating_count"
        poster_only = request.args.get("poster_only", "0") == "1"
        where = "WHERE poster_url IS NOT NULL AND poster_url <> ''" if poster_only else ""
        cursor.execute(f"""
            SELECT TOP (?) movie_id, title, release_year, director,
                   poster_url, avg_score, rating_count, max_score, min_score,
                   watch_count, complete_count
            FROM dbo.vw_movie_stats
            {where}
            ORDER BY {sort} DESC
        """, (limit,))
        rows = cursor.fetchall()
        for r in rows:
            r["avg_score"] = float(r["avg_score"] or 0)
        return jsonify({"movies": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/user-activity", methods=["GET"])
def api_user_activity():
    """查询 vw_user_activity 视图：用户活跃度排行"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        limit = int(request.args.get("limit", 20))
        cursor.execute("""
            SELECT TOP (?) user_id, username, nickname, age, gender,
                   favorite_genre, total_ratings, avg_rating_given,
                   total_watched, total_completed, last_rating_time, last_watch_time
            FROM dbo.vw_user_activity
            ORDER BY total_ratings DESC
        """, (limit,))
        rows = cursor.fetchall()
        for r in rows:
            if r.get("last_rating_time"):
                r["last_rating_time"] = str(r["last_rating_time"])[:19]
            if r.get("last_watch_time"):
                r["last_watch_time"] = str(r["last_watch_time"])[:19]
            r["avg_rating_given"] = float(r.get("avg_rating_given") or 0)
        return jsonify({"users": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/genre-popularity", methods=["GET"])
def api_genre_popularity():
    """查询 vw_genre_popularity 视图：类型热度统计"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT genre_id, genre_name, movie_count, avg_score,
                   total_ratings, total_watches
            FROM dbo.vw_genre_popularity
            ORDER BY total_ratings DESC
        """)
        rows = cursor.fetchall()
        for r in rows:
            r["avg_score"] = float(r.get("avg_score") or 0)
        return jsonify({"genres": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/movie-rank", methods=["GET"])
def api_movie_rank():
    """查询 vw_movie_rank 视图：电影排行榜（窗口函数结果）"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        limit = int(request.args.get("limit", 20))
        cursor.execute("""
            SELECT TOP (?) movie_id, title, release_year, avg_score,
                   rating_count, watch_count,
                   rank_by_popularity, rank_by_score, rank_in_year
            FROM dbo.vw_movie_rank
            ORDER BY rank_by_score
        """, (limit,))
        rows = cursor.fetchall()
        for r in rows:
            r["avg_score"] = float(r.get("avg_score") or 0)
        return jsonify({"movies": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/recommendations/<int:user_id>", methods=["GET"])
def api_sp_recommendations(user_id):
    """调用存储过程 sp_get_recommendations：基于协同过滤的个性化推荐"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        top_n = int(request.args.get("top_n", 10))
        cursor.execute("EXEC dbo.sp_get_recommendations @user_id=?, @top_n=?",
                       (user_id, top_n))
        rows = cursor.fetchall()
        for r in rows:
            r["predicted_score"] = float(r.get("predicted_score") or 0)
        return jsonify({"recommendations": rows, "user_id": user_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/add-rating", methods=["POST"])
def api_sp_add_rating():
    """调用存储过程 sp_add_rating（带事务）：防重复评分"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        data = request.get_json() or {}
        uid = data.get("user_id") or session["user_id"]
        mid = data.get("movie_id")
        score = data.get("score")
        if not mid or score is None:
            return jsonify({"success": False, "message": "缺少 movie_id 或 score"}), 400
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DECLARE @res NVARCHAR(100);
            EXEC dbo.sp_add_rating @user_id=?, @movie_id=?, @score=?, @result=@res OUTPUT;
            SELECT @res AS result;
        """, (uid, mid, float(score)))
        row = cursor.fetchone()
        result = row["result"] if row else ""
        conn.commit()
        ok = result.startswith("OK")
        return jsonify({"success": ok, "message": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/dashboard-stats", methods=["GET"])
def api_sp_dashboard_stats():
    """调用存储过程 sp_dashboard_stats：一次返回完整仪表盘指标"""
    if not session.get("user_id"):
        return jsonify({"error": "未授权"}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("EXEC dbo.sp_dashboard_stats")
        row = cursor.fetchone()
        if row:
            return jsonify(dict(row))
        return jsonify({}), 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@app.route("/api/db/audit-log", methods=["GET"])
def api_audit_log():
    """查询审计日志（仅管理员）"""
    if not session.get("user_id") or session.get("role") != "admin":
        return jsonify({"error": "仅管理员可访问"}), 403
    try:
        conn = get_connection()
        cursor = conn.cursor()
        table = request.args.get("table", "")
        limit = min(int(request.args.get("limit", 50)), 200)
        if table:
            cursor.execute("""
                SELECT TOP (?) log_id, table_name, operation, record_id,
                       old_value, new_value, changed_by, changed_at
                FROM dbo.audit_log WHERE table_name=?
                ORDER BY changed_at DESC
            """, (limit, table))
        else:
            cursor.execute("""
                SELECT TOP (?) log_id, table_name, operation, record_id,
                       old_value, new_value, changed_by, changed_at
                FROM dbo.audit_log ORDER BY changed_at DESC
            """, (limit,))
        rows = cursor.fetchall()
        for r in rows:
            if r.get("changed_at"):
                r["changed_at"] = str(r["changed_at"])[:19]
        return jsonify({"logs": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


# =======================
# 运行服务器
# =======================
if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    workers = int(os.environ.get("WAITRESS_THREADS", "8"))

    if os.environ.get("USE_WAITRESS", "yes").lower() in ("1", "true", "yes"):
        try:
            from waitress import serve

            print(f"Waitress 并发服务: http://{host}:{port} (threads={workers})")
            serve(app, host=host, port=port, threads=workers)
        except ImportError:
            print("未安装 waitress，回退到 Flask 内置服务器")
            app.run(host=host, port=port, debug=debug, threaded=True)
    else:
        app.run(host=host, port=port, debug=debug, threaded=True)