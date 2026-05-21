# [file name]: recommendation.py

from db_config import get_connection
# 修改导入方式
try:
    # 尝试从当前目录导入
    from .recommendation_model import recommender
except ImportError:
    try:
        # 尝试从父目录导入
        from models.recommendation_model import recommender
    except ImportError:
        # 最后尝试直接导入
        from recommendation_model import recommender

import functools
import time
from flask import g

# 在 recommendation.py 中优化 get_recommendations_for_user 函数
def get_recommendations_for_user(user_id, limit=10, method='hybrid'):
    """为用户获取推荐 """
    try:
        start_time = time.time()
        print(f"开始为用户 {user_id} 获取推荐，方法: {method}")

        # 先检查是否有缓存的推荐结果
        cache_key = f"recommendations:{user_id}:{method}:{limit}"

        # 如果有缓存，直接返回
        if hasattr(g, '_recommendation_cache') and cache_key in g._recommendation_cache:
            cached_data, timestamp = g._recommendation_cache[cache_key]
            if time.time() - timestamp < 300:  # 5分钟缓存
                print(f"使用缓存推荐，用户: {user_id}")
                return cached_data

        # 确保模型已加载
        if not recommender.load_model():
            print("模型未加载，返回热门电影")
            return get_popular_movies(limit=limit)

        # 获取推荐
        recommendations = recommender.recommend_for_user(
            user_id=user_id,
            n_recommendations=limit,
            method=method
        )

        # 批量获取电影详细信息（优化查询）
        detailed_recommendations = []
        if recommendations:
            conn = get_connection()
            cursor = conn.cursor()

            # 批量查询电影信息
            movie_ids = [rec['movie_id'] for rec in recommendations]
            placeholders = ', '.join(['?'] * len(movie_ids))

            cursor.execute(f"""
                SELECT m.movie_id, m.title, m.release_year, m.language, m.duration,
                       m.director, m.description, m.poster_url,
                       COALESCE(AVG(r.score), 0) as avg_rating,
                       COUNT(r.rating_id) as rating_count,
                       STRING_AGG(g.genre_name, ',') as genres
                FROM movie m
                LEFT JOIN rating r ON m.movie_id = r.movie_id
                LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
                LEFT JOIN genre g ON mg.genre_id = g.genre_id
                WHERE m.movie_id IN ({placeholders})
                GROUP BY m.movie_id, m.title, m.release_year, m.language,
                         m.duration, m.director, m.description, m.poster_url
            """, movie_ids)

            movies_info = {row['movie_id']: row for row in cursor.fetchall()}

            for rec in recommendations:
                movie_id = rec['movie_id']
                movie_info = movies_info.get(movie_id)

                if movie_info:
                    detailed_rec = {
                        'movie_id': movie_id,
                        'title': movie_info['title'],
                        'release_year': movie_info['release_year'],
                        'director': movie_info['director'],
                        'duration': movie_info['duration'],
                        'description': movie_info['description'],
                        'avg_rating': float(movie_info['avg_rating']) if movie_info['avg_rating'] else 0,
                        'rating_count': movie_info['rating_count'],
                        'genres': movie_info['genres'].split(',') if movie_info['genres'] else [],
                        'recommendation_score': rec.get('score', 0),
                        'recommendation_method': rec.get('method', method),
                        'predicted_rating': min(5.0, rec.get('score', 0) * 5)
                    }
                    detailed_recommendations.append(detailed_rec)

            cursor.close()
            conn.close()

        # 缓存结果
        if not hasattr(g, '_recommendation_cache'):
            g._recommendation_cache = {}
        g._recommendation_cache[cache_key] = (detailed_recommendations, time.time())

        end_time = time.time()
        print(f"推荐生成完成，用户: {user_id}, 耗时: {end_time - start_time:.2f}秒")

        return detailed_recommendations

    except Exception as e:
        print(f"获取推荐失败: {e}")
        # 返回热门电影作为fallback
        return get_popular_movies(limit=limit)


def get_popular_movies(limit=10):
    """获取热门电影"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP (?) m.movie_id, m.title, m.release_year, m.language, m.duration,
                   m.director, m.description, m.poster_url,
                   AVG(r.score) as avg_rating,
                   COUNT(r.rating_id) as rating_count,
                   STRING_AGG(g.genre_name, ',') as genres,
                   COUNT(DISTINCT h.history_id) as watch_count
            FROM movie m
            LEFT JOIN rating r ON m.movie_id = r.movie_id
            LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
            LEFT JOIN genre g ON mg.genre_id = g.genre_id
            LEFT JOIN history h ON m.movie_id = h.movie_id
            GROUP BY m.movie_id, m.title, m.release_year, m.language,
                     m.duration, m.director, m.description, m.poster_url
            HAVING COUNT(r.rating_id) >= 1
            ORDER BY 
                (COUNT(r.rating_id) * AVG(r.score)) DESC,
                COUNT(DISTINCT h.history_id) DESC
        """, (limit,))

        movies = cursor.fetchall()

        # 处理结果
        for movie in movies:
            if movie['genres']:
                movie['genres'] = movie['genres'].split(',')
            else:
                movie['genres'] = []

            if movie['avg_rating']:
                movie['avg_rating'] = float(movie['avg_rating'])
            else:
                movie['avg_rating'] = 0

        return movies

    except Exception as e:
        print(f"获取热门电影失败: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_similar_movies(movie_id, limit=10):
    """获取相似电影"""
    try:
        # 确保模型已加载
        if not recommender.load_model():
            return []

        conn = get_connection()
        cursor = conn.cursor()

        # 获取目标电影信息
        cursor.execute("""
            SELECT m.movie_id, m.title, m.release_year, m.language, m.duration,
                   m.director, m.description, m.poster_url,
                   STRING_AGG(g.genre_name, ',') as genres
            FROM movie m
            LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
            LEFT JOIN genre g ON mg.genre_id = g.genre_id
            WHERE m.movie_id = ?
            GROUP BY m.movie_id, m.title, m.release_year, m.language,
                     m.duration, m.director, m.description, m.poster_url
        """, (movie_id,))

        target_movie = cursor.fetchone()
        if not target_movie:
            return []

        # 使用模型获取相似电影
        if movie_id in recommender.movie_ids:
            movie_idx = recommender.movie_ids.index(movie_id)

            # 计算相似度
            similarities = []
            for other_movie_id in recommender.movie_ids:
                if other_movie_id != movie_id:
                    similarity = recommender.movie_similarity_df.loc[movie_id, other_movie_id]
                    similarities.append((other_movie_id, similarity))

            # 按相似度排序
            similarities.sort(key=lambda x: x[1], reverse=True)

            # 获取详细信息
            similar_movies = []
            for sim_movie_id, similarity in similarities[:limit]:
                cursor.execute("""
                    SELECT m.movie_id, m.title, m.release_year, m.language, m.duration,
                           m.director, m.description, m.poster_url,
                           AVG(r.score) as avg_rating,
                           STRING_AGG(g.genre_name, ',') as genres
                    FROM movie m
                    LEFT JOIN rating r ON m.movie_id = r.movie_id
                    LEFT JOIN movie_genre mg ON m.movie_id = mg.movie_id
                    LEFT JOIN genre g ON mg.genre_id = g.genre_id
                    WHERE m.movie_id = ?
                    GROUP BY m.movie_id, m.title, m.release_year, m.language,
                             m.duration, m.director, m.description, m.poster_url
                """, (sim_movie_id,))

                movie_info = cursor.fetchone()
                if movie_info:
                    if movie_info['genres']:
                        movie_info['genres'] = movie_info['genres'].split(',')
                    else:
                        movie_info['genres'] = []

                    if movie_info['avg_rating']:
                        movie_info['avg_rating'] = float(movie_info['avg_rating'])

                    movie_info['similarity_score'] = float(similarity)
                    similar_movies.append(movie_info)

            return similar_movies

        return []

    except Exception as e:
        print(f"获取相似电影失败: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_recommendation_stats():
    """获取推荐系统统计"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 获取总用户数
        cursor.execute("SELECT COUNT(*) as total_users FROM [user]")
        total_users = cursor.fetchone()['total_users']

        # 获取有评分行为的用户数
        cursor.execute("SELECT COUNT(DISTINCT user_id) as active_users FROM rating")
        active_users = cursor.fetchone()['active_users']

        # 获取电影数
        cursor.execute("SELECT COUNT(*) as total_movies FROM movie")
        total_movies = cursor.fetchone()['total_movies']

        # 获取评分总数
        cursor.execute("SELECT COUNT(*) as total_ratings FROM rating")
        total_ratings = cursor.fetchone()['total_ratings']

        # 获取稀疏度
        if total_users > 0 and total_movies > 0:
            sparsity = 1 - (total_ratings / (total_users * total_movies))
        else:
            sparsity = 1

        # 尝试加载模型信息
        model_info = {}
        try:
            if recommender.load_model():
                model_info = {
                    'user_count': len(recommender.user_ids),
                    'movie_count': len(recommender.movie_ids),
                    'explained_variance': recommender.explained_variance,
                    'model_size': len(recommender.user_ids) * len(recommender.movie_ids)
                }
        except:
            pass

        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_movies': total_movies,
            'total_ratings': total_ratings,
            'sparsity': sparsity,
            'coverage': active_users / total_users if total_users > 0 else 0,
            'avg_ratings_per_user': total_ratings / active_users if active_users > 0 else 0,
            'model_info': model_info
        }

    except Exception as e:
        print(f"获取推荐统计失败: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()