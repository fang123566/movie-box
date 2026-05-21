# 电影推荐系统（Movie Recommendation System）

> 基于 **Flask + SQL Server** 的全栈电影信息与推荐 Web 应用。  
> 集成 **120 部真实中文电影数据**、多策略推荐引擎，以及面向生产环境的加解密、连接池并发、容灾备份等运维体系。

---

## 目录

- [更新日志](#更新日志)
- [功能概览](#功能概览)
- [角色权限对照](#角色权限对照)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [数据库设计](#数据库设计)
- [快速开始](#快速开始)
- [页面说明](#页面说明)
- [API 接口文档](#api-接口文档)
- [运维能力详解](#运维能力详解)
- [推荐算法](#推荐算法)
- [数据说明](#数据说明)
- [常见问题](#常见问题)

---

## 更新日志

### v1.3.0 — 2026-05-20（当前版本）

**角色权限体系重构**
- 注册页面新增身份选择（普通用户 / 管理员），无需邀请码，直接选择角色注册
- 导航栏按角色分流：管理员显示管理类菜单，普通用户显示个人功能菜单
- `/users` 用户管理页仅管理员可访问，普通用户重定向首页
- 电影增删改 API（POST/PUT/DELETE `/api/movies`）增加管理员校验，普通用户返回 403
- 评分列表 API、观看历史 API 按角色自动过滤：管理员看全部数据，普通用户只看自己的

**导出功能上线**
- 新增 `GET /api/ops/export-download`：直接将全库数据导出为 JSON 文件推送到浏览器下载
- 系统运维页「导出并下载 JSON」按钮触发浏览器下载，无需查看服务器文件系统
- 全库备份遇权限错误时自动降级为 JSON 导出，不再报错中断

**Bug 修复**
- 修复 `search_ratings` / `search_history` 使用 MySQL 语法导致在 SQL Server 上报错（`%s`→`?`、`LIMIT`→`OFFSET FETCH`、`DATE()`→`CAST AS DATE`）
- 修复 JSON 导出时 `Decimal` 类型无法序列化的问题（转为 `float`）

**UI 优化**
- 个人资料页、账户设置页增加背景图+半透明毛玻璃卡片效果
- 仪表盘「热门电影」区域增加图片预加载校验（过滤 TMDB 1×1 占位图）
- 页脚版权更新为 Designed by FY!

### v1.2.0 — 2026-05-19

- 仪表盘热门电影海报墙动态加载（从 `/api/db/movie-stats` 拉取真实海报）
- 最新注册用户模块动态加载
- `vw_movie_stats` 视图补充 `poster_url` 字段，支持 `poster_only` 过滤参数
- 修复 `get_all_movies()` GROUP BY 问题（改用子查询计算 avg_score）

### v1.1.0 — 2026-05-18

- 管理员登录支持（admin 表独立校验）
- 登录页新增角色下拉选择（用户 / 管理员）
- 注册成功后按角色跳转（管理员→`/ops`，普通用户→`/dashboard`）
- 注册时性别 value 改为 `male/female/other` 匹配数据库 CHECK 约束

---

## 功能概览

| 模块 | 说明 |
|------|------|
| **用户管理** | 注册 / 登录（用户 + 管理员双角色）、个人资料编辑、密码修改 |
| **电影管理** | 管理员可增删改查；普通用户只读浏览 + 评分 |
| **评分管理** | 管理员查看所有评分；普通用户查看/管理自己的评分 |
| **观看历史** | 管理员查看所有记录；普通用户查看自己的观看记录 |
| **推荐引擎** | SVD 协同过滤 + 内容相似 + 热门混合推荐，个性化电影推荐 |
| **仪表盘** | 实时统计（用户数、电影数、评分数、历史数）、热门电影海报墙 |
| **运维中心** | 加解密状态、连接池监控、一键备份 / JSON 下载导出（仅管理员）|

---

## 角色权限对照

| 功能 | 管理员 | 普通用户 |
|------|--------|----------|
| 首页仪表盘 | ✅ | ✅ |
| 浏览电影 | ✅ | ✅ |
| 新增 / 编辑 / 删除电影 | ✅ | ❌ 403 |
| 用户管理页（`/users`） | ✅ | ❌ 重定向 |
| 查看所有评分 | ✅ | ❌ 只看自己 |
| 查看所有历史记录 | ✅ | ❌ 只看自己 |
| 智能推荐 | — | ✅ |
| 个人资料 / 账户设置 | ✅ | ✅ |
| 系统运维（`/ops`） | ✅ | ❌ 重定向 |
| 数据导出下载 | ✅ | ❌ 403 |

---

## 技术栈

| 分类 | 技术 / 版本 |
|------|------------|
| **Web 框架** | Flask 2.3+、Flask-CORS |
| **并发服务** | Waitress（多线程，默认 8 线程）|
| **数据库** | Microsoft SQL Server（2019+）|
| **数据库驱动** | pyodbc 5.0+、ODBC Driver 17/18 for SQL Server |
| **ORM / 查询层** | 原生 SQL + 自定义 `DictCursor`（MySQL → SQL Server 兼容层）|
| **连接池** | 自研 `ConnectionPool`（queue.Queue，线程安全）|
| **密码安全** | werkzeug PBKDF2-SHA256（新用户）+ 旧 SHA256 兼容 |
| **配置加密** | cryptography Fernet（AES-128-CBC）|
| **限流** | 自研内存令牌桶（IP + 路由级）|
| **推荐算法** | scikit-surprise SVD + scikit-learn 内容相似度 |
| **前端** | Bootstrap 5、Font Awesome 6、Chart.js |
| **备份** | SQL Server `BACKUP DATABASE` + JSON 双轨 |

---

## 项目结构

```
movie-recommendation-system-main/
│
├── movie_system_sqlserver.sql      # ① 建库建表脚本（在 SSMS 执行一次）
├── seed_sqlserver_data.py          # ② 批量导入电影 / 用户 / 评分 / 历史
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
│
├── data/
│   ├── web_movies.json             # 120 部真实电影元数据
│   ├── web_movie_data.py           # JSON 解析与格式化工具
│   └── fetch_web_movies.py         # （可选）重新抓取/生成电影数据
│
├── scripts/
│   ├── backup_database.py          # 命令行执行全库备份
│   ├── restore_database.py         # 从 .bak 恢复数据库
│   ├── generate_encryption_key.py  # 生成 Fernet 加密密钥
│   └── scheduled_backup.bat        # Windows 任务计划程序示例
│
└── movie_system_api/
    ├── app.py                      # Flask 应用主入口，所有路由定义
    ├── db_config.py                # 数据库连接、连接池、SQL 兼容转换
    │
    ├── ops/                        # 运维模块
    │   ├── __init__.py
    │   ├── crypto.py               # 密码哈希、Fernet 加解密
    │   ├── db_pool.py              # 线程安全连接池实现
    │   ├── rate_limit.py           # IP 级登录限流
    │   └── backup.py               # 全库备份、JSON 导出、恢复
    │
    ├── models/                     # 数据访问层（DAL）
    │   ├── user.py                 # 用户 CRUD
    │   ├── movie.py                # 电影 CRUD + 搜索
    │   ├── rating.py               # 评分 CRUD
    │   ├── history.py              # 观看历史 CRUD
    │   ├── recommendation.py       # 推荐逻辑调用层
    │   └── recommendation_model.py # SVD + 内容推荐实现
    │
    ├── static/
    │   ├── css/                    # 自定义样式
    │   └── js/                     # 前端交互脚本
    │
    └── templates/
        ├── index.html              # 登录页
        ├── register.html           # 注册页
        ├── layout.html             # 公共导航 / 布局
        └── dashboard/
            ├── index.html          # 仪表盘首页
            ├── movies.html         # 电影管理
            ├── users.html          # 用户管理
            ├── ratings.html        # 评分管理
            ├── history.html        # 观看历史
            ├── profile.html        # 个人资料
            ├── settings.html       # 账户设置
            └── ops.html            # 系统运维（管理员专属）
```

---

## 数据库设计

数据库名：`movie_system`，初始化脚本：`movie_system_sqlserver.sql`，高级特性脚本：`movie_system_advanced.sql`。

### 基础表（7 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `genre` | `genre_id` | 20 种电影类型 |
| `movie` | `movie_id` | 电影信息，含 CHECK 约束（年份 1888-2100，时长 > 0）|
| `[user]` | `user_id` | 用户信息，含 CHECK 约束（年龄 1-150，性别枚举）|
| `admin` | `admin_id` | 管理员账号 |
| `rating` | `rating_id` | 评分，CHECK 约束（0.5≤score≤5.0），UNIQUE(user_id, movie_id) |
| `history` | `history_id` | 观看历史，含完成状态 |
| `movie_genre` | `(movie_id, genre_id)` | 电影-类型多对多关联 |

**主要约束：**
- **主键（PK）**：每张表均有 `IDENTITY` 自增主键
- **外键（FK）**：6 条外键，关联删除全部设置 `ON DELETE CASCADE`
- **唯一约束（UQ）**：`user.username`、`genre.genre_name`、`rating(user_id, movie_id)`
- **CHECK 约束**：评分范围、年龄范围、年份范围、时长正整数、性别枚举

### 索引（8 个）

| 索引名 | 表 | 列 | 用途 |
|--------|----|----|------|
| `IX_movie_year` | movie | release_year DESC | 按年份筛选/排序 |
| `IX_movie_language` | movie | language | 按语言筛选 |
| `IX_user_register` | [user] | register_date DESC | 最新注册用户查询 |
| `IX_user_gender` | [user] | gender | 性别统计分析 |
| `IX_rating_user` | rating | user_id, rating_time DESC | 用户评分历史 |
| `IX_rating_movie` | rating | movie_id, score DESC | 电影评分聚合 |
| `IX_history_user` | history | user_id, watch_time DESC | 用户观影时间线 |
| `IX_history_movie` | history | movie_id | 电影观看统计 |

### 视图（4 个）

| 视图名 | 核心技术 | 功能 |
|--------|----------|------|
| `vw_movie_stats` | LEFT JOIN + 子查询聚合 | 电影统计（均分、评分数、最高/低分、观看量）|
| `vw_user_activity` | LEFT JOIN + 多子查询 | 用户活跃度（评分数、观看数、最近活动时间）|
| `vw_genre_popularity` | GROUP BY + 多表 JOIN | 类型热度（电影数、均分、总评分、总观看）|
| `vw_movie_rank` | **RANK() / DENSE_RANK() 窗口函数** | 综合排行榜（按热度、评分、年份内排名）|

### 存储过程（4 个）

| 存储过程名 | 核心技术 | 功能 |
|------------|----------|------|
| `sp_get_recommendations` | CTE + 自连接 + TOP | 基于协同过滤的个性化电影推荐 |
| `sp_add_rating` | **BEGIN TRANSACTION / TRY-CATCH** | 安全添加/更新评分，防重复，原子写入 |
| `sp_dashboard_stats` | 多子查询聚合 | 一次调用返回仪表盘全部指标 |
| `sp_delete_user` | 事务 + 审计日志写入 | 删除用户前记录审计，事务保证一致性 |

### 触发器（3 个）

| 触发器名 | 类型 | 触发时机 | 功能 |
|----------|------|----------|------|
| `trg_rating_audit` | AFTER | rating INSERT/UPDATE/DELETE | 自动将评分变更写入 audit_log |
| `trg_prevent_movie_delete` | INSTEAD OF | movie DELETE | 有评分的电影禁止直接删除 |
| `trg_user_insert_audit` | AFTER | [user] INSERT | 新用户注册自动写入审计日志 |

### 审计日志表

`audit_log` 表记录所有关键数据变更，字段包含：被操作表、操作类型（INSERT/UPDATE/DELETE）、原值（JSON）、新值（JSON）、操作时间。支持合规审计和数据溯源。

### 事务使用

- `sp_add_rating`：评分写入用显式事务，任何异常自动 ROLLBACK
- `sp_delete_user`：删除用户前先写审计日志，再执行删除，原子保证
- `sp_merge_user_history`：账号合并迁移历史/评分，全程事务保护

### 高级 API 端点（对接以上特性）

| 端点 | 底层 | 说明 |
|------|------|------|
| `GET /api/db/movie-stats` | `vw_movie_stats` | 电影统计视图查询 |
| `GET /api/db/user-activity` | `vw_user_activity` | 用户活跃度视图 |
| `GET /api/db/genre-popularity` | `vw_genre_popularity` | 类型热度视图 |
| `GET /api/db/movie-rank` | `vw_movie_rank` | 排行榜视图（窗口函数）|
| `GET /api/db/recommendations/{uid}` | `sp_get_recommendations` | 存储过程推荐 |
| `POST /api/db/add-rating` | `sp_add_rating` | 存储过程+事务评分 |
| `GET /api/db/dashboard-stats` | `sp_dashboard_stats` | 存储过程仪表盘 |
| `GET /api/db/audit-log` | `audit_log` | 审计日志查询（管理员）|

---

## 快速开始

### 1. 环境要求

| 依赖 | 要求 |
|------|------|
| Python | **3.9+**（推荐 3.10 / 3.11）|
| SQL Server | 2016+（本机或远程，建议启用 TCP/IP 协议）|
| ODBC 驱动 | [ODBC Driver 17 或 18 for SQL Server](https://learn.microsoft.com/zh-cn/sql/connect/odbc/download-odbc-driver-for-sql-server) |

### 2. 安装 Python 依赖

```powershell
pip install -r requirements.txt
```

`requirements.txt` 包含：

```
flask>=2.3.0
flask-cors>=4.0.0
pyodbc>=5.0.0
werkzeug>=2.3.0
cryptography>=41.0.0
waitress>=2.1.0
pandas>=1.5.0
numpy>=1.23.0
scikit-learn>=1.2.0
scikit-surprise>=1.1.3
```

### 3. 初始化数据库

**步骤一：在 SSMS 执行建库建表脚本（仅首次）**

```
1. 打开 SQL Server Management Studio（SSMS）
2. 连接到本机（Windows 身份验证）
3. 新建查询 → 打开 movie_system_sqlserver.sql → 全选 → 执行（F5）
4. 确认左侧对象资源管理器出现 movie_system 数据库
```

> 若之前已建库，且 `password_hash` 字段长度不足，需先执行升级：
> ```sql
> USE movie_system;
> ALTER TABLE dbo.[user] ALTER COLUMN password_hash NVARCHAR(255) NOT NULL;
> ```

**步骤二：导入示例数据**

```powershell
python seed_sqlserver_data.py
```

成功后将导入：**120 部电影、40 个用户、~1446 条评分、~1837 条观看记录**

> 如需重新生成电影 JSON（需网络），可先执行：
> ```powershell
> python data\fetch_web_movies.py
> ```

### 4. 配置环境变量

```powershell
copy .env.example .env
```

然后编辑 `.env`，**至少修改以下两项**：

```env
FLASK_SECRET_KEY=你的随机长字符串（建议32位以上）
SQL_SERVER=localhost          # 若为命名实例改为 localhost\SQLEXPRESS
```

完整配置说明见 `.env.example`。

### 5. 启动服务

```powershell
cd movie_system_api
python app.py
```

浏览器访问：**http://127.0.0.1:5000**

**默认账号：**

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `admin123` |
| 普通用户 | `alice` | `123456` |
| 普通用户 | `bob` ~ `user40` | `123456`（共 40 个）|

---

## 页面说明

### 公共页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 登录 | 支持用户 / 管理员角色选择 |
| `/register` | 注册 | 选择身份（普通用户 / 管理员）+ 填写基本信息 |

### 普通用户页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/dashboard` | 仪表盘 | 统计卡片 + 热门电影海报墙 + 最新用户 |
| `/movies` | 浏览电影 | 只读列表，支持搜索/筛选，无增删改按钮 |
| `/ratings` | 我的评分 | 仅显示当前用户的评分记录 |
| `/history` | 我的记录 | 仅显示当前用户的观看记录 |
| `/recommendations` | 智能推荐 | 个性化推荐 + 热门推荐 + 相似电影 |
| `/profile` | 个人资料 | 修改昵称、年龄、性别、偏好类型（背景图）|
| `/settings` | 账户设置 | 修改密码、密码强度检测（背景图）|

### 管理员页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/dashboard` | 仪表盘 | 同普通用户 |
| `/movies` | 电影管理 | 完整增删改查，含新增弹窗 |
| `/users` | 用户管理 | 用户列表、性别/偏好筛选、编辑/删除 |
| `/ratings` | 评分管理 | 所有用户评分记录 |
| `/history` | 观看记录 | 所有用户观看历史 |
| `/profile` | 个人资料 | 同普通用户 |
| `/settings` | 账户设置 | 同普通用户 |
| `/ops` | 系统运维 | 加密状态、连接池监控、备份、**一键导出下载** |

---

## API 接口文档

> 所有 API 均需登录后访问（Session 验证），返回 JSON 格式。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 登录，Body: `{username, password, role}` |
| POST | `/api/register` | 注册，Body: `{username, password, nickname, age, gender, role}` |
| GET | `/logout` | 退出登录（重定向）|

### 个人资料

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/profile` | 获取当前用户信息 |
| PUT | `/api/profile` | 修改昵称/年龄/性别/偏好类型 |
| POST | `/api/change-password` | 修改密码，Body: `{old_password, new_password}` |

### 电影

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/movies` | 电影列表（支持 `?page` `?limit` `?search` `?year` `?genre_id`）|
| GET | `/api/movies/{id}` | 单部电影详情（含平均评分、类型）|
| POST | `/api/movies` | 新增电影 |
| PUT | `/api/movies/{id}` | 更新电影信息 |
| DELETE | `/api/movies/{id}` | 删除电影 |
| GET | `/api/movies/top` | 评分最高的电影列表 |
| GET | `/api/genres` | 所有电影类型 |

### 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users` | 用户列表（支持 `?search` `?gender` `?favorite_genre`）|
| GET | `/api/users/{id}` | 单个用户信息 |
| POST | `/api/users` | 新增用户（管理员操作）|
| PUT | `/api/users/{id}` | 更新用户信息 |
| DELETE | `/api/users/{id}` | 删除用户 |
| GET | `/api/users/recent` | 最近注册用户 |

### 评分

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ratings` | 评分列表（支持 `?user_id` `?movie_id` `?page` `?limit`）|
| GET | `/api/ratings/{id}` | 单条评分 |
| POST | `/api/ratings` | 新增评分，Body: `{user_id, movie_id, score}` |
| PUT | `/api/ratings/{id}` | 更新评分 |
| DELETE | `/api/ratings/{id}` | 删除评分 |

### 观看历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/history` | 历史列表（支持 `?user_id` `?movie_id` `?page` `?limit`）|
| POST | `/api/history` | 新增观看记录 |
| PUT | `/api/history/{id}` | 更新记录（如补充时长）|
| DELETE | `/api/history/{id}` | 删除记录 |

### 推荐

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/recommendations` | 个性化推荐（`?method=hybrid/svd/content`）|
| GET | `/api/recommendations/popular` | 热门电影推荐 |
| GET | `/api/recommendations/similar/{movie_id}` | 相似电影 |
| POST | `/api/recommendations/train` | 训练推荐模型（管理员）|

### 仪表盘 & 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/stats` | 汇总统计（用户/电影/评分/历史数量）|
| GET | `/api/dashboard/chart-data` | 图表数据 |
| GET | `/api/dashboard/recent-activities` | 最近活动 |
| GET | `/api/health` | 存活探针 |
| GET | `/api/health/ready` | 就绪探针（含 DB 连通 + 连接池状态）|

### 运维（管理员专属）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ops/status` | 加密状态、连接池、限流配置概览 |
| POST | `/api/ops/backup` | 触发备份，Body: `{type: "full" \| "json"}`；`full` 自动降级为 JSON |
| GET | `/api/ops/export-download` | **直接下载** 全库 JSON 文件到浏览器 |

---

## 运维能力详解

### 🔒 加解密

| 层次 | 实现方案 | 说明 |
|------|----------|------|
| 用户密码 | **PBKDF2-SHA256**（werkzeug，自动加盐）| 新注册 / 修改密码时生效 |
| 旧密码兼容 | SHA256 十六进制哈希 | 旧用户可无感登录 |
| 数据库连接密码 | **Fernet（AES-128-CBC）** | 密文写入 `.env`，运行时自动解密 |
| Session 防篡改 | Flask `SECRET_KEY` 签名 | 修改 `FLASK_SECRET_KEY` 即可 |

**生成 Fernet 加密密钥：**

```powershell
python scripts\generate_encryption_key.py
# 输出: APP_ENCRYPTION_KEY=xxxxxxxxxxxx...
```

**加密数据库 SA 密码（可选，SQL Server 身份验证模式）：**

```python
# 在 movie_system_api 目录下执行
from ops.crypto import encrypt_connection_password
print(encrypt_connection_password("你的SA密码"))
```

将输出值写入 `.env`：

```env
SQL_TRUSTED_CONNECTION=no
SQL_USERNAME=sa
SQL_PASSWORD=enc:xxxxxxxxxxxxxxxx
SQL_PASSWORD_ENCRYPTED=true
APP_ENCRYPTION_KEY=你的Fernet密钥
```

---

### ⚡ 并发处理

**连接池（`ops/db_pool.py`）：**

- 基于 `queue.Queue` 的线程安全实现
- `acquire()` 超时 5 秒后抛出 `TimeoutError`
- `release()`：正常时归还连接，异常时销毁并补充新连接
- 支持溢出连接（临时扩容），溢出用完后自动回收

**Waitress 多线程：**

- 默认启动 8 个 Worker 线程，支持并发 HTTP 请求
- 通过 `WAITRESS_THREADS` 环境变量调整

**登录限流（`ops/rate_limit.py`）：**

- 滑动时间窗口，按 `IP + 请求路径` 计数
- 默认：同一 IP 每 60 秒最多 10 次登录/注册请求
- 超限返回 HTTP 429 + 剩余等待秒数

```env
DB_POOL_SIZE=10         # 连接池容量
DB_POOL_OVERFLOW=5      # 溢出上限
WAITRESS_THREADS=8      # HTTP 并发线程数
LOGIN_RATE_LIMIT=10     # 限流次数
LOGIN_RATE_WINDOW=60    # 限流时间窗口（秒）
```

---

### 🛡️ 容灾备份

**双轨备份策略：**

| 备份类型 | 文件格式 | 用途 |
|----------|----------|------|
| 全库备份 | `.bak`（压缩）| 灾难恢复，秒级还原 |
| 业务表导出 | `_tables_YYYYMMDD.json` | 审计、数据迁移、跨平台还原 |

**命令行执行备份：**

```powershell
# 执行全库 + JSON 双轨备份（保留最近 7 份，自动清理旧备份）
python scripts\backup_database.py

# 指定备份目录
python scripts\backup_database.py --dir D:\backups\movie_system
```

**从备份恢复：**

```powershell
# 从 .bak 文件恢复（会覆盖现有库，需手动输入 YES 确认）
python scripts\restore_database.py --file backups\movie_system_20260520_020000.bak
```

**管理员可在系统运维页面（`/ops`）直接点击按钮触发备份。**

**自动定时备份（Windows 任务计划程序）：**

```
1. 打开"任务计划程序" → 创建基本任务
2. 触发器：每天凌晨 2:00
3. 操作：启动程序 → 选择 scripts\scheduled_backup.bat
4. 设置完成后可手动运行测试
```

```env
BACKUP_DIR=backups        # 备份存储目录
BACKUP_KEEP_COUNT=7       # 保留最近几份备份
```

---

## 推荐算法

系统实现四种推荐策略，通过混合权重融合。

| 策略 | 算法 | 说明 |
|------|------|------|
| **协同过滤** | SVD（矩阵分解）| 基于用户评分行为，找相似用户喜欢的电影 |
| **内容推荐** | TF-IDF + 余弦相似度 | 基于电影类型、描述文本的内容相似性 |
| **热门推荐** | 加权评分（贝叶斯）| 综合评分数量与均值，推荐口碑佳的电影 |
| **混合推荐** | 加权融合 | 结合协同过滤 + 内容推荐，缺冷启动数据时退化为热门 |

**推荐 API 参数：**

```
GET /api/recommendations?method=hybrid&limit=10
  method: hybrid（混合）| svd（协同过滤）| content（内容）
  limit:  返回数量（默认 10）
```

**训练 / 更新推荐模型：**

```powershell
cd movie_system_api
python train_recommendation_model.py
# 或通过管理员权限调用 POST /api/recommendations/train
```

模型文件保存在 `movie_system_api/models/recommendation_model.pkl`。

---

## 数据说明

| 数据项 | 数量 | 来源 |
|--------|------|------|
| 电影 | 120 部 | 国产片数据库 + MovieLens 热门片译名 |
| 用户 | 40 个 | 种子数据（密码均为 `123456`）|
| 类型 | 20 种 | 动作/喜剧/剧情/科幻/恐怖/爱情/动画等 |
| 评分 | ~1446 条 | 随机生成（2.5 ~ 5.0 星）|
| 观看历史 | ~1837 条 | 随机生成（含完成状态）|

包含的代表性电影（部分）：

> 流浪地球、哪吒之魔童降世、我不是药神、长津湖、霸王别姬、活着、让子弹飞、无间道、  
> 肖申克的救赎、阿甘正传、盗梦空间、星际穿越、千与千寻、寄生虫、釜山行 等

---

## 常见问题

**Q：启动报 `No module named 'flask'` 或 `pyodbc'`？**  
确认 `pip install -r requirements.txt` 已在**当前 Python 环境**执行成功。

**Q：连接报错 `[ODBC Driver] Data source name not found`？**  
下载并安装 [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/zh-cn/sql/connect/odbc/download-odbc-driver-for-sql-server)，安装完重启 IDE / 终端。

**Q：使用 SQL Server 命名实例（如 SQLEXPRESS）？**  
在 `.env` 中设置：`SQL_SERVER=localhost\SQLEXPRESS`

**Q：旧用户（SHA256 密码）登录失败？**  
`verify_password()` 已兼容 SHA256 哈希，能正常登录。若要升级旧密码为 PBKDF2，重新执行 `seed_sqlserver_data.py` 即可（会覆盖密码）。

**Q：推荐结果为空？**  
确保数据库中有足够的评分数据（至少 20 条），或先执行 `python train_recommendation_model.py` 训练模型。

**Q：备份时报权限错误（操作系统错误 5）？**  
SQL Server 服务账号无权写入项目目录（Desktop 等路径）。系统已内置自动降级：`full` 备份失败时自动改为 Python 直接导出 JSON 到 `backups/` 目录，不影响使用。若需真正的 `.bak` 备份，请将 `BACKUP_DIR` 设置为 SQL Server 服务账号有权写入的路径（如 `C:\SQLBackups`）并手动授权。

**Q：导出 JSON 时报 `Decimal is not JSON serializable`？**  
已在 `ops/backup.py` 修复，`Decimal` 类型自动转为 `float`。若仍报错，请确认服务器已完全重启（关闭旧进程后重新运行 `python app.py`）。

**Q：重启服务器后仍报旧错误？**  
请确认旧的 Python 进程已终止：
```powershell
Get-Process python* | Stop-Process -Force
```
然后重新启动：`python movie_system_api/app.py`

**Q：如何部署到生产环境？**

1. 修改 `FLASK_SECRET_KEY` 为随机长字符串
2. 设置 `FLASK_DEBUG=false`
3. 配置 Nginx / IIS 反向代理 + HTTPS 证书
4. 调大 `WAITRESS_THREADS`（建议 CPU 核心数 × 2）
5. 配置定时备份任务（`scripts\scheduled_backup.bat`）
6. 将 `backups/` 同步到异地存储

---

## License

本项目为学习 / 课程设计用途，欢迎参考和二次开发。
