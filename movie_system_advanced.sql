-- ================================================================
-- movie_system_advanced.sql
-- 高级数据库特性：审计表 / 视图 / 存储过程 / 触发器 / 事务示例
-- 执行前提：已运行 movie_system_sqlserver.sql 并导入数据
-- ================================================================
USE movie_system;
GO

-- ================================================================
-- 一、审计日志表（Audit Table）
-- 记录评分和用户信息的所有变更，支持溯源与合规审计
-- ================================================================
IF OBJECT_ID(N'dbo.audit_log', N'U') IS NOT NULL DROP TABLE dbo.audit_log;
GO

CREATE TABLE dbo.audit_log (
    log_id       INT           IDENTITY(1,1) PRIMARY KEY,
    table_name   NVARCHAR(50)  NOT NULL,                -- 被操作的表
    operation    NVARCHAR(10)  NOT NULL,                -- INSERT / UPDATE / DELETE
    record_id    INT           NOT NULL,                -- 被操作记录的主键
    old_value    NVARCHAR(MAX) NULL,                    -- 变更前（JSON 格式）
    new_value    NVARCHAR(MAX) NULL,                    -- 变更后（JSON 格式）
    changed_by   NVARCHAR(100) NULL,                    -- 操作人（用户名）
    changed_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT CK_audit_op CHECK (operation IN (N'INSERT', N'UPDATE', N'DELETE'))
);
GO
CREATE INDEX IX_audit_table_time ON dbo.audit_log (table_name, changed_at DESC);
GO


-- ================================================================
-- 二、视图（Views）
-- ================================================================

-- 视图 1：电影统计视图 —— 含平均分、评分数、观看次数
IF OBJECT_ID(N'dbo.vw_movie_stats', N'V') IS NOT NULL DROP VIEW dbo.vw_movie_stats;
GO
CREATE VIEW dbo.vw_movie_stats AS
    SELECT
        m.movie_id,
        m.title,
        m.release_year,
        m.language,
        m.duration,
        m.director,
        m.description,
        m.poster_url,
        -- 评分统计
        ISNULL(r.avg_score,  0)    AS avg_score,
        ISNULL(r.rating_cnt, 0)    AS rating_count,
        ISNULL(r.max_score,  0)    AS max_score,
        ISNULL(r.min_score,  0)    AS min_score,
        -- 观看统计
        ISNULL(h.watch_cnt,  0)    AS watch_count,
        ISNULL(h.complete_cnt, 0)  AS complete_count
    FROM dbo.movie m
    LEFT JOIN (
        SELECT movie_id,
               ROUND(AVG(CAST(score AS FLOAT)), 2) AS avg_score,
               COUNT(*)                             AS rating_cnt,
               MAX(score)                           AS max_score,
               MIN(score)                           AS min_score
        FROM dbo.rating
        GROUP BY movie_id
    ) r ON m.movie_id = r.movie_id
    LEFT JOIN (
        SELECT movie_id,
               COUNT(*)              AS watch_cnt,
               SUM(CAST(completed AS INT)) AS complete_cnt
        FROM dbo.history
        GROUP BY movie_id
    ) h ON m.movie_id = h.movie_id;
GO


-- 视图 2：用户活跃度视图 —— 评分数、观看数、最近活动时间
IF OBJECT_ID(N'dbo.vw_user_activity', N'V') IS NOT NULL DROP VIEW dbo.vw_user_activity;
GO
CREATE VIEW dbo.vw_user_activity AS
    SELECT
        u.user_id,
        u.username,
        u.nickname,
        u.age,
        u.gender,
        u.register_date,
        g.genre_name                       AS favorite_genre,
        ISNULL(r.rating_cnt,  0)           AS total_ratings,
        ISNULL(r.avg_given,   0)           AS avg_rating_given,
        ISNULL(h.watch_cnt,   0)           AS total_watched,
        ISNULL(h.completed_cnt, 0)         AS total_completed,
        r.last_rating_time,
        h.last_watch_time
    FROM dbo.[user] u
    LEFT JOIN dbo.genre g ON u.favorite_genre_id = g.genre_id
    LEFT JOIN (
        SELECT user_id,
               COUNT(*)                              AS rating_cnt,
               ROUND(AVG(CAST(score AS FLOAT)), 2)  AS avg_given,
               MAX(rating_time)                      AS last_rating_time
        FROM dbo.rating
        GROUP BY user_id
    ) r ON u.user_id = r.user_id
    LEFT JOIN (
        SELECT user_id,
               COUNT(*)                       AS watch_cnt,
               SUM(CAST(completed AS INT))    AS completed_cnt,
               MAX(watch_time)                AS last_watch_time
        FROM dbo.history
        GROUP BY user_id
    ) h ON u.user_id = h.user_id;
GO


-- 视图 3：类型热度视图 —— 每个类型的电影数、平均分、总观看量
IF OBJECT_ID(N'dbo.vw_genre_popularity', N'V') IS NOT NULL DROP VIEW dbo.vw_genre_popularity;
GO
CREATE VIEW dbo.vw_genre_popularity AS
    SELECT
        g.genre_id,
        g.genre_name,
        COUNT(DISTINCT mg.movie_id)               AS movie_count,
        ROUND(AVG(CAST(r.score AS FLOAT)), 2)     AS avg_score,
        COUNT(r.rating_id)                        AS total_ratings,
        COUNT(h.history_id)                       AS total_watches
    FROM dbo.genre g
    LEFT JOIN dbo.movie_genre mg ON g.genre_id = mg.genre_id
    LEFT JOIN dbo.rating  r ON mg.movie_id = r.movie_id
    LEFT JOIN dbo.history h ON mg.movie_id = h.movie_id
    GROUP BY g.genre_id, g.genre_name;
GO


-- 视图 4：电影排行榜视图（窗口函数）
IF OBJECT_ID(N'dbo.vw_movie_rank', N'V') IS NOT NULL DROP VIEW dbo.vw_movie_rank;
GO
CREATE VIEW dbo.vw_movie_rank AS
    SELECT
        movie_id,
        title,
        release_year,
        avg_score,
        rating_count,
        watch_count,
        -- 窗口函数：按评分人数降序排名
        RANK()       OVER (ORDER BY rating_count DESC)        AS rank_by_popularity,
        -- 窗口函数：按平均分降序排名（至少5人评过）
        RANK()       OVER (ORDER BY CASE WHEN rating_count >= 5
                                    THEN avg_score ELSE 0 END DESC) AS rank_by_score,
        -- 窗口函数：年份内相对排名（DENSE_RANK 示例）
        DENSE_RANK() OVER (PARTITION BY release_year ORDER BY avg_score DESC) AS rank_in_year
    FROM dbo.vw_movie_stats;
GO


-- ================================================================
-- 三、存储过程（Stored Procedures）
-- ================================================================

-- 存储过程 1：获取指定用户的个性化推荐（基于相似用户评分，协同过滤简化版）
IF OBJECT_ID(N'dbo.sp_get_recommendations', N'P') IS NOT NULL DROP PROC dbo.sp_get_recommendations;
GO
CREATE PROCEDURE dbo.sp_get_recommendations
    @user_id   INT,
    @top_n     INT = 10
AS
BEGIN
    SET NOCOUNT ON;
    -- 找出与目标用户评过相同电影且评分相近的用户（余弦相似度简化：共同评分数量代替）
    WITH similar_users AS (
        SELECT r2.user_id AS sim_user_id,
               COUNT(*)   AS common_movies,
               AVG(ABS(r1.score - r2.score)) AS score_diff
        FROM dbo.rating r1
        JOIN dbo.rating r2
            ON r1.movie_id = r2.movie_id
           AND r2.user_id  <> @user_id
        WHERE r1.user_id = @user_id
        GROUP BY r2.user_id
        HAVING COUNT(*) >= 3
    ),
    -- 取相似用户高分评价的电影，且目标用户还没看过
    candidate_movies AS (
        SELECT r.movie_id,
               AVG(CAST(r.score AS FLOAT))    AS pred_score,
               COUNT(*)                        AS vote_count
        FROM dbo.rating r
        JOIN similar_users su ON r.user_id = su.sim_user_id
        WHERE r.movie_id NOT IN (
            SELECT movie_id FROM dbo.rating WHERE user_id = @user_id
        )
        AND r.score >= 3.5
        GROUP BY r.movie_id
    )
    SELECT TOP (@top_n)
        m.movie_id,
        m.title,
        m.director,
        m.release_year,
        ROUND(cm.pred_score, 2) AS predicted_score,
        cm.vote_count
    FROM candidate_movies cm
    JOIN dbo.movie m ON cm.movie_id = m.movie_id
    ORDER BY cm.pred_score DESC, cm.vote_count DESC;
END;
GO


-- 存储过程 2：添加评分（含事务，防止重复评分）
IF OBJECT_ID(N'dbo.sp_add_rating', N'P') IS NOT NULL DROP PROC dbo.sp_add_rating;
GO
CREATE PROCEDURE dbo.sp_add_rating
    @user_id  INT,
    @movie_id INT,
    @score    DECIMAL(3,1),
    @result   NVARCHAR(100) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    -- 参数校验
    IF @score < 0.5 OR @score > 5.0
    BEGIN
        SET @result = N'ERROR: 评分必须在 0.5 到 5.0 之间';
        RETURN;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (SELECT 1 FROM dbo.rating WHERE user_id = @user_id AND movie_id = @movie_id)
        BEGIN
            -- 已有评分则更新
            UPDATE dbo.rating
            SET score = @score, rating_time = SYSDATETIME()
            WHERE user_id = @user_id AND movie_id = @movie_id;
            SET @result = N'OK: 评分已更新';
        END
        ELSE
        BEGIN
            INSERT INTO dbo.rating (user_id, movie_id, score)
            VALUES (@user_id, @movie_id, @score);
            SET @result = N'OK: 评分已添加';
        END

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @result = N'ERROR: ' + ERROR_MESSAGE();
    END CATCH
END;
GO


-- 存储过程 3：获取仪表盘汇总统计（单次调用返回多项指标）
IF OBJECT_ID(N'dbo.sp_dashboard_stats', N'P') IS NOT NULL DROP PROC dbo.sp_dashboard_stats;
GO
CREATE PROCEDURE dbo.sp_dashboard_stats
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        (SELECT COUNT(*) FROM dbo.movie)                              AS total_movies,
        (SELECT COUNT(*) FROM dbo.[user])                             AS total_users,
        (SELECT COUNT(*) FROM dbo.rating)                             AS total_ratings,
        (SELECT COUNT(*) FROM dbo.history)                            AS total_history,
        (SELECT ROUND(AVG(CAST(score AS FLOAT)), 2) FROM dbo.rating)  AS overall_avg_score,
        (SELECT COUNT(*) FROM dbo.history WHERE completed = 1)        AS total_completed,
        (SELECT COUNT(*) FROM dbo.[user]
         WHERE register_date >= DATEADD(DAY, -30, SYSDATETIME()))      AS new_users_30d,
        (SELECT COUNT(*) FROM dbo.rating
         WHERE rating_time >= DATEADD(DAY, -30, SYSDATETIME()))        AS new_ratings_30d;
END;
GO


-- 存储过程 4：批量删除用户（事务保证原子性）
IF OBJECT_ID(N'dbo.sp_delete_user', N'P') IS NOT NULL DROP PROC dbo.sp_delete_user;
GO
CREATE PROCEDURE dbo.sp_delete_user
    @user_id INT,
    @result  NVARCHAR(100) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        -- 级联已由外键 ON DELETE CASCADE 处理，此处记录审计日志后直接删除
        DECLARE @username NVARCHAR(100);
        SELECT @username = username FROM dbo.[user] WHERE user_id = @user_id;

        IF @username IS NULL
        BEGIN
            SET @result = N'ERROR: 用户不存在';
            ROLLBACK TRANSACTION;
            RETURN;
        END

        INSERT INTO dbo.audit_log (table_name, operation, record_id, old_value, changed_by)
        VALUES (N'user', N'DELETE', @user_id,
                N'{"username":"' + @username + N'"}',
                SYSTEM_USER);

        DELETE FROM dbo.[user] WHERE user_id = @user_id;
        SET @result = N'OK: 用户 ' + @username + N' 已删除';
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @result = N'ERROR: ' + ERROR_MESSAGE();
    END CATCH
END;
GO


-- ================================================================
-- 四、触发器（Triggers）
-- ================================================================

-- 触发器 1：评分变更自动写入审计日志（INSERT / UPDATE / DELETE）
IF OBJECT_ID(N'dbo.trg_rating_audit', N'TR') IS NOT NULL DROP TRIGGER dbo.trg_rating_audit;
GO
CREATE TRIGGER dbo.trg_rating_audit
ON dbo.rating
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    -- 处理 INSERT
    IF EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.audit_log (table_name, operation, record_id, new_value)
        SELECT N'rating', N'INSERT', i.rating_id,
               N'{"user_id":' + CAST(i.user_id AS NVARCHAR) +
               N',"movie_id":' + CAST(i.movie_id AS NVARCHAR) +
               N',"score":' + CAST(i.score AS NVARCHAR) + N'}'
        FROM inserted i;
    END

    -- 处理 UPDATE
    IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.audit_log (table_name, operation, record_id, old_value, new_value)
        SELECT N'rating', N'UPDATE', i.rating_id,
               N'{"score":' + CAST(d.score AS NVARCHAR) + N'}',
               N'{"score":' + CAST(i.score AS NVARCHAR) + N'}'
        FROM inserted i JOIN deleted d ON i.rating_id = d.rating_id;
    END

    -- 处理 DELETE
    IF NOT EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.audit_log (table_name, operation, record_id, old_value)
        SELECT N'rating', N'DELETE', d.rating_id,
               N'{"user_id":' + CAST(d.user_id AS NVARCHAR) +
               N',"movie_id":' + CAST(d.movie_id AS NVARCHAR) +
               N',"score":' + CAST(d.score AS NVARCHAR) + N'}'
        FROM deleted d;
    END
END;
GO


-- 触发器 2：禁止删除有评分记录的电影（业务规则保护）
IF OBJECT_ID(N'dbo.trg_prevent_movie_delete', N'TR') IS NOT NULL DROP TRIGGER dbo.trg_prevent_movie_delete;
GO
CREATE TRIGGER dbo.trg_prevent_movie_delete
ON dbo.movie
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM dbo.rating r
        JOIN deleted d ON r.movie_id = d.movie_id
    )
    BEGIN
        RAISERROR(N'该电影存在用户评分，不能直接删除。请先删除所有评分记录。', 16, 1);
        RETURN;
    END
    -- 无评分时允许删除
    DELETE FROM dbo.movie WHERE movie_id IN (SELECT movie_id FROM deleted);
END;
GO


-- 触发器 3：新用户注册自动写入审计日志
IF OBJECT_ID(N'dbo.trg_user_insert_audit', N'TR') IS NOT NULL DROP TRIGGER dbo.trg_user_insert_audit;
GO
CREATE TRIGGER dbo.trg_user_insert_audit
ON dbo.[user]
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.audit_log (table_name, operation, record_id, new_value)
    SELECT N'user', N'INSERT', i.user_id,
           N'{"username":"' + i.username + N'","register_date":"' +
           CONVERT(NVARCHAR, i.register_date, 120) + N'"}'
    FROM inserted i;
END;
GO


-- ================================================================
-- 五、事务示例：转移观看历史（演示显式事务的回滚场景）
-- ================================================================
-- 该存储过程将源用户的所有历史迁移给目标用户（模拟账号合并），
-- 若目标用户不存在则自动回滚，确保原子性。
IF OBJECT_ID(N'dbo.sp_merge_user_history', N'P') IS NOT NULL DROP PROC dbo.sp_merge_user_history;
GO
CREATE PROCEDURE dbo.sp_merge_user_history
    @src_user_id  INT,
    @dest_user_id INT,
    @result       NVARCHAR(200) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        IF NOT EXISTS (SELECT 1 FROM dbo.[user] WHERE user_id = @dest_user_id)
        BEGIN
            SET @result = N'ERROR: 目标用户不存在';
            ROLLBACK TRANSACTION;
            RETURN;
        END

        DECLARE @cnt INT;

        -- 迁移历史（忽略目标用户已有的记录，避免主键冲突）
        UPDATE dbo.history
        SET user_id = @dest_user_id
        WHERE user_id = @src_user_id
          AND movie_id NOT IN (
              SELECT movie_id FROM dbo.history WHERE user_id = @dest_user_id
          );
        SET @cnt = @@ROWCOUNT;

        -- 迁移评分（同理）
        UPDATE dbo.rating
        SET user_id = @dest_user_id
        WHERE user_id = @src_user_id
          AND movie_id NOT IN (
              SELECT movie_id FROM dbo.rating WHERE user_id = @dest_user_id
          );

        SET @result = N'OK: 已迁移 ' + CAST(@cnt AS NVARCHAR) + N' 条历史记录';
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        SET @result = N'ERROR: ' + ERROR_MESSAGE();
    END CATCH
END;
GO


-- ================================================================
-- 六、常用分析查询（CTE + 窗口函数示例）
-- ================================================================

-- 示例 1：每个类型中评分最高的前 3 部电影（PARTITION BY + RANK）
-- SELECT * FROM (
--     SELECT g.genre_name, m.title, ms.avg_score,
--            RANK() OVER (PARTITION BY g.genre_id ORDER BY ms.avg_score DESC) AS rn
--     FROM dbo.vw_movie_stats ms
--     JOIN dbo.movie_genre mg ON ms.movie_id = mg.movie_id
--     JOIN dbo.genre g ON mg.genre_id = g.genre_id
--     WHERE ms.rating_count >= 3
-- ) ranked WHERE rn <= 3;

-- 示例 2：近 30 天最活跃用户（CTE + 聚合）
-- WITH recent_activity AS (
--     SELECT user_id, COUNT(*) AS ops
--     FROM (
--         SELECT user_id FROM dbo.rating  WHERE rating_time >= DATEADD(DAY,-30,SYSDATETIME())
--         UNION ALL
--         SELECT user_id FROM dbo.history WHERE watch_time  >= DATEADD(DAY,-30,SYSDATETIME())
--     ) t
--     GROUP BY user_id
-- )
-- SELECT TOP 10 u.username, u.nickname, ra.ops
-- FROM recent_activity ra JOIN dbo.[user] u ON ra.user_id = u.user_id
-- ORDER BY ra.ops DESC;

PRINT N'movie_system_advanced.sql 执行完成';
GO
