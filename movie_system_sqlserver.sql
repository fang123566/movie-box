IF DB_ID(N'movie_system') IS NULL
BEGIN
    CREATE DATABASE movie_system;
END
GO

USE movie_system;
GO

IF OBJECT_ID(N'dbo.movie_genre', N'U') IS NOT NULL DROP TABLE dbo.movie_genre;
IF OBJECT_ID(N'dbo.history', N'U') IS NOT NULL DROP TABLE dbo.history;
IF OBJECT_ID(N'dbo.rating', N'U') IS NOT NULL DROP TABLE dbo.rating;
IF OBJECT_ID(N'dbo.[user]', N'U') IS NOT NULL DROP TABLE dbo.[user];
IF OBJECT_ID(N'dbo.movie', N'U') IS NOT NULL DROP TABLE dbo.movie;
IF OBJECT_ID(N'dbo.genre', N'U') IS NOT NULL DROP TABLE dbo.genre;
IF OBJECT_ID(N'dbo.admin', N'U') IS NOT NULL DROP TABLE dbo.admin;
GO

-- ============================================================
-- 1. 基础表
-- ============================================================

CREATE TABLE dbo.genre (
    genre_id   INT           IDENTITY(1,1) PRIMARY KEY,
    genre_name NVARCHAR(100) NOT NULL UNIQUE
);
GO

CREATE TABLE dbo.movie (
    movie_id     INT           IDENTITY(1,1) PRIMARY KEY,
    title        NVARCHAR(255) NOT NULL,
    release_year INT           NULL,
    language     NVARCHAR(50)  NULL,
    duration     INT           NULL,
    director     NVARCHAR(100) NULL,
    description  NVARCHAR(MAX) NULL,
    poster_url   NVARCHAR(500) NULL,
    created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    -- CHECK 约束：保证数据完整性
    CONSTRAINT CK_movie_year     CHECK (release_year IS NULL OR (release_year >= 1888 AND release_year <= 2100)),
    CONSTRAINT CK_movie_duration CHECK (duration IS NULL OR duration > 0)
);
GO

CREATE TABLE dbo.[user] (
    user_id          INT           IDENTITY(1,1) PRIMARY KEY,
    username         NVARCHAR(100) NOT NULL UNIQUE,
    password_hash    NVARCHAR(255) NOT NULL,
    nickname         NVARCHAR(100) NULL,
    age              INT           NULL,
    gender           NVARCHAR(20)  NULL,
    favorite_genre_id INT          NULL,
    register_date    DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    -- CHECK 约束
    CONSTRAINT CK_user_age    CHECK (age IS NULL OR (age >= 1 AND age <= 150)),
    CONSTRAINT CK_user_gender CHECK (gender IS NULL OR gender IN (N'male', N'female', N'other')),
    CONSTRAINT FK_user_favorite_genre FOREIGN KEY (favorite_genre_id) REFERENCES dbo.genre(genre_id)
);
GO

CREATE TABLE dbo.admin (
    admin_id      INT           IDENTITY(1,1) PRIMARY KEY,
    username      NVARCHAR(100) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL
);
GO

CREATE TABLE dbo.rating (
    rating_id   INT           IDENTITY(1,1) PRIMARY KEY,
    user_id     INT           NOT NULL,
    movie_id    INT           NOT NULL,
    score       DECIMAL(3,1)  NOT NULL,
    rating_time DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    -- CHECK 约束：评分范围 0.5 ~ 5.0
    CONSTRAINT CK_rating_score CHECK (score >= 0.5 AND score <= 5.0),
    CONSTRAINT FK_rating_user  FOREIGN KEY (user_id)  REFERENCES dbo.[user](user_id)  ON DELETE CASCADE,
    CONSTRAINT FK_rating_movie FOREIGN KEY (movie_id) REFERENCES dbo.movie(movie_id)  ON DELETE CASCADE,
    -- 唯一约束：每个用户对每部电影只能评一次
    CONSTRAINT UQ_rating_user_movie UNIQUE (user_id, movie_id)
);
GO

CREATE TABLE dbo.history (
    history_id      INT       IDENTITY(1,1) PRIMARY KEY,
    user_id         INT       NOT NULL,
    movie_id        INT       NOT NULL,
    watch_time      DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    duration_watched INT      NULL,
    completed       BIT       NOT NULL DEFAULT 0,
    CONSTRAINT CK_history_duration CHECK (duration_watched IS NULL OR duration_watched >= 0),
    CONSTRAINT FK_history_user  FOREIGN KEY (user_id)  REFERENCES dbo.[user](user_id)  ON DELETE CASCADE,
    CONSTRAINT FK_history_movie FOREIGN KEY (movie_id) REFERENCES dbo.movie(movie_id)  ON DELETE CASCADE
);
GO

CREATE TABLE dbo.movie_genre (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    CONSTRAINT FK_movie_genre_movie  FOREIGN KEY (movie_id) REFERENCES dbo.movie(movie_id)  ON DELETE CASCADE,
    CONSTRAINT FK_movie_genre_genre  FOREIGN KEY (genre_id) REFERENCES dbo.genre(genre_id)  ON DELETE CASCADE
);
GO

-- ============================================================
-- 2. 索引（提升查询性能）
-- ============================================================

-- 电影：按年份、语言筛选
CREATE INDEX IX_movie_year     ON dbo.movie (release_year DESC);
CREATE INDEX IX_movie_language ON dbo.movie (language);
-- 用户：按注册时间、性别统计
CREATE INDEX IX_user_register  ON dbo.[user] (register_date DESC);
CREATE INDEX IX_user_gender    ON dbo.[user] (gender);
-- 评分：按用户、按电影分别查询
CREATE INDEX IX_rating_user    ON dbo.rating (user_id, rating_time DESC);
CREATE INDEX IX_rating_movie   ON dbo.rating (movie_id, score DESC);
-- 观看历史：按用户时间线查询
CREATE INDEX IX_history_user   ON dbo.history (user_id, watch_time DESC);
CREATE INDEX IX_history_movie  ON dbo.history (movie_id);
GO

INSERT INTO dbo.genre (genre_name) VALUES
(N'动作'), (N'喜剧'), (N'剧情'), (N'科幻'), (N'恐怖'),
(N'爱情'), (N'动画'), (N'悬疑'), (N'犯罪'), (N'冒险'),
(N'家庭'), (N'奇幻'), (N'音乐'), (N'战争'), (N'西部'), (N'纪录片'), (N'青春'), (N'运动');
GO

-- 默认管理员（用户名: admin，初始密码: admin123，PBKDF2-SHA256 哈希）
-- ⚠️ 生产环境请立即登录后修改密码！
INSERT INTO dbo.admin (username, password_hash) VALUES
(N'admin', N'pbkdf2:sha256:600000$defaultsalt0000$placeholder_run_seed_to_generate_real_hash');
GO
-- 说明：以上 hash 为占位符，正式 hash 由 seed_sqlserver_data.py 自动写入。
-- 若只执行本 SQL 脚本，请在 Python 中运行：
--   from ops.crypto import hash_password; print(hash_password('admin123'))
-- 然后 UPDATE dbo.admin SET password_hash=N'输出值' WHERE username=N'admin';

-- 中文电影样例（完整 120 部 + 用户/评分/历史请运行: python seed_sqlserver_data.py）
INSERT INTO dbo.movie (title, release_year, language, duration, director, description, poster_url) VALUES
(N'流浪地球', 2019, N'中文', 125, N'郭帆', N'太阳即将毁灭，人类开启“流浪地球”计划，推动地球离开太阳系寻找新家园。', NULL),
(N'盗梦空间', 2010, N'英语', 148, NULL, N'《盗梦空间》(2010)，科幻、悬疑类型影片。', NULL),
(N'疯狂动物城2', 2025, N'英语', NULL, NULL, N'《疯狂动物城2》(2025)，动画、喜剧、冒险类型影片。', N'https://image.tmdb.org/t/p/w500/oJ7g2CifqpStmoYQyaLQgEU32qO.jpg');
GO

INSERT INTO dbo.movie_genre (movie_id, genre_id)
SELECT m.movie_id, g.genre_id
FROM dbo.movie m
JOIN dbo.genre g ON
    (m.title = N'流浪地球' AND g.genre_name IN (N'科幻', N'冒险', N'剧情'))
    OR (m.title = N'盗梦空间' AND g.genre_name IN (N'科幻', N'悬疑', N'动作'))
    OR (m.title = N'疯狂动物城2' AND g.genre_name IN (N'动画', N'喜剧', N'冒险'));
GO
