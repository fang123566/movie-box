# [file name]: recommendation_model.py
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
import pickle
import os
from db_config import get_connection
import time

class MovieRecommender:
    def __init__(self):
        os.makedirs('models', exist_ok=True)
        self.user_movie_matrix = None
        self.movie_similarity = None
        self.user_similarity = None
        self.model_path = 'models/recommendation_model.pkl'
        self.metadata_path = 'models/movie_metadata.pkl'

        # 确保模型目录存在
        os.makedirs('models', exist_ok=True)

    def load_data_from_db(self):
        """从数据库加载评分数据"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            print("正在从数据库加载评分数据...")
            # 方法1: 使用游标直接获取数据，避免pandas.read_sql的问题
            rating_query = """
                SELECT r.user_id, r.movie_id, r.score
                FROM rating r
                WHERE r.user_id IS NOT NULL AND r.movie_id IS NOT NULL AND r.score IS NOT NULL
                ORDER BY r.rating_time DESC
            """
            cursor.execute(rating_query)
            rating_data = cursor.fetchall()

            # 将数据转换为DataFrame
            if rating_data:
                rating_df = pd.DataFrame(rating_data, columns=['user_id', 'movie_id', 'score'])
                print(f"实际评分数据: {len(rating_df)} 条")
                print(f"评分数据示例: {rating_data[:3] if rating_data else '无'}")
            else:
                rating_df = pd.DataFrame(columns=['user_id', 'movie_id', 'score'])
                print("警告：评分表为空或没有有效数据")

            # 获取观看历史数据
            print("正在加载观看历史数据...")
            history_query = """
                SELECT user_id, movie_id, 
                       CASE WHEN completed = 1 THEN 1 ELSE 0.5 END as watch_score
                FROM history
                WHERE user_id IS NOT NULL AND movie_id IS NOT NULL
            """
            cursor.execute(history_query)
            history_data = cursor.fetchall()

            if history_data:
                history_df = pd.DataFrame(history_data, columns=['user_id', 'movie_id', 'watch_score'])
                print(f"实际观看记录: {len(history_df)} 条")
            else:
                history_df = pd.DataFrame(columns=['user_id', 'movie_id', 'watch_score'])
                print("警告：历史表为空或没有有效数据")

            # 获取电影元数据
            print("正在加载电影元数据...")
            metadata_query = """
                SELECT m.movie_id, m.title, m.release_year, m.director,
                       COALESCE(AVG(r.score), 0) as avg_rating,
                       COALESCE(COUNT(r.rating_id), 0) as rating_count
                FROM movie m
                LEFT JOIN rating r ON m.movie_id = r.movie_id
                GROUP BY m.movie_id
            """
            cursor.execute(metadata_query)
            metadata_data = cursor.fetchall()

            if metadata_data:
                metadata_df = pd.DataFrame(metadata_data,
                                           columns=['movie_id', 'title', 'release_year', 'director', 'avg_rating',
                                                    'rating_count'])
                print(f"电影元数据: {len(metadata_df)} 部")
            else:
                metadata_df = pd.DataFrame(
                    columns=['movie_id', 'title', 'release_year', 'director', 'avg_rating', 'rating_count'])
                print("警告：电影表为空")

            # 检查实际数据内容
            if len(rating_df) > 0:
                print(f"前3条评分数据: {rating_df.head(3).to_dict('records')}")
            if len(history_df) > 0:
                print(f"前3条观看记录: {history_df.head(3).to_dict('records')}")

            return rating_df, history_df, metadata_df

        except Exception as e:
            print(f"加载数据错误: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        finally:
            cursor.close()
            conn.close()

    def prepare_data(self):
        """准备训练数据"""
        rating_df, history_df, metadata_df = self.load_data_from_db()

        # 详细检查数据
        print(f"检查数据 - rating_df: {'非空' if not rating_df.empty else '空'}, shape: {rating_df.shape}")
        print(f"检查数据 - history_df: {'非空' if not history_df.empty else '空'}, shape: {history_df.shape}")
        print(f"检查数据 - metadata_df: {'非空' if not metadata_df.empty else '空'}, shape: {metadata_df.shape}")

        if rating_df.empty and history_df.empty:
            print("错误：评分数据和观看历史都为空！")
            print("请先添加一些评分数据或观看历史")
            return False

        # 确保列名正确
        if not rating_df.empty:
            # 检查必要列是否存在
            required_columns = ['user_id', 'movie_id', 'score']
            missing_columns = [col for col in required_columns if col not in rating_df.columns]
            if missing_columns:
                print(f"评分数据缺少必要列: {missing_columns}")
                rating_df = pd.DataFrame()  # 标记为空

        if not history_df.empty:
            # 重命名列以匹配
            if 'watch_score' in history_df.columns:
                history_df = history_df.rename(columns={'watch_score': 'score'})

        # 合并数据
        data_frames = []

        if not rating_df.empty:
            print(f"使用评分数据: {len(rating_df)} 条")
            # 确保数据类型正确
            rating_df['score'] = pd.to_numeric(rating_df['score'], errors='coerce')
            rating_df = rating_df.dropna(subset=['score'])
            if not rating_df.empty:
                data_frames.append(rating_df[['user_id', 'movie_id', 'score']])

        if not history_df.empty:
            print(f"使用观看历史: {len(history_df)} 条")
            # 确保数据类型正确
            history_df['score'] = pd.to_numeric(history_df['score'], errors='coerce')
            history_df = history_df.dropna(subset=['score'])
            if not history_df.empty:
                data_frames.append(history_df[['user_id', 'movie_id', 'score']])

        if not data_frames:
            print("错误：所有数据都为空，无法训练模型")
            return False

        # 合并所有数据
        combined_df = pd.concat(data_frames, ignore_index=True)
        print(f"合并后总数据量: {len(combined_df)} 条")

        if combined_df.empty:
            print("错误：合并后的数据为空")
            return False

        # 创建用户-电影评分矩阵
        print("正在创建评分矩阵...")
        try:
            user_movie_pivot = combined_df.pivot_table(
                index='user_id',
                columns='movie_id',
                values='score',
                fill_value=0,
                aggfunc='mean'
            )

            print(f"评分矩阵形状: {user_movie_pivot.shape}")

            if user_movie_pivot.shape[0] == 0 or user_movie_pivot.shape[1] == 0:
                print("错误：创建的评分矩阵为空！")
                return False

            self.user_movie_matrix = csr_matrix(user_movie_pivot.values)
            self.user_ids = user_movie_pivot.index.tolist()
            self.movie_ids = user_movie_pivot.columns.tolist()

            # 保存元数据
            if not metadata_df.empty:
                self.movie_metadata = metadata_df.set_index('movie_id').to_dict('index')
            else:
                self.movie_metadata = {}

            print(f"数据准备完成：{len(self.user_ids)} 个用户，{len(self.movie_ids)} 部电影")
            return True

        except Exception as e:
            print(f"创建评分矩阵失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def train_item_based_cf(self):
        """基于物品的协同过滤"""
        print("训练基于物品的协同过滤模型...")

        # 计算电影之间的相似度
        movie_similarity = cosine_similarity(self.user_movie_matrix.T)

        # 转换为DataFrame以便查询
        self.movie_similarity_df = pd.DataFrame(
            movie_similarity,
            index=self.movie_ids,
            columns=self.movie_ids
        )

        print(f"模型训练完成，共{len(self.movie_ids)}部电影")
        return True

    def train_user_based_cf(self):
        """基于用户的协同过滤"""
        print("训练基于用户的协同过滤模型...")

        # 计算用户之间的相似度
        user_similarity = cosine_similarity(self.user_movie_matrix)

        # 转换为DataFrame
        self.user_similarity_df = pd.DataFrame(
            user_similarity,
            index=self.user_ids,
            columns=self.user_ids
        )

        print(f"模型训练完成，共{len(self.user_ids)}个用户")
        return True

    def train_matrix_factorization(self, n_components=20):
        """矩阵分解（SVD）"""
        print("训练矩阵分解模型...")

        svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.user_factors = svd.fit_transform(self.user_movie_matrix)
        self.item_factors = svd.components_.T

        self.explained_variance = svd.explained_variance_ratio_.sum()
        print(f"模型训练完成，解释方差: {self.explained_variance:.2%}")

        return True

    def train_hybrid_model(self):
        """训练混合模型"""
        print("开始训练混合推荐模型...")
        start_time = time.time()

        # 准备数据
        if not self.prepare_data():
            print("数据准备失败，无法训练模型")
            return False

        # 检查是否有足够的数据
        if len(self.user_ids) < 5 or len(self.movie_ids) < 10:
            print(f"数据不足：只有 {len(self.user_ids)} 个用户和 {len(self.movie_ids)} 部电影")
            print("建议添加更多用户评分或观看记录后再训练模型")
            return False

        print(f"数据充足，开始训练...")

        try:
            # 训练所有模型
            if not self.train_item_based_cf():
                print("基于物品的协同过滤训练失败")

            if not self.train_user_based_cf():
                print("基于用户的协同过滤训练失败")

            if not self.train_matrix_factorization():
                print("矩阵分解训练失败")

            # 保存模型
            self.save_model()

            end_time = time.time()
            training_time = end_time - start_time

            print(f"模型训练成功！")
            print(f"用户数量: {len(self.user_ids)}")
            print(f"电影数量: {len(self.movie_ids)}")
            print(f"训练耗时: {training_time:.2f} 秒")

            if hasattr(self, 'explained_variance'):
                print(f"模型解释方差: {self.explained_variance:.2%}")

            return True

        except Exception as e:
            print(f"训练混合模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def recommend_for_user(self, user_id, n_recommendations=10, method='hybrid'):
        """为用户生成推荐"""
        if not hasattr(self, 'movie_similarity_df'):
            if not self.load_model():
                return []

        user_idx = None
        if user_id in self.user_ids:
            user_idx = self.user_ids.index(user_id)

        recommendations = []

        if method == 'item_based' or method == 'hybrid':
            # 基于物品的推荐
            item_recs = self._item_based_recommendations(user_id, user_idx, n_recommendations)
            recommendations.extend(item_recs)

        if method == 'user_based' or method == 'hybrid':
            # 基于用户的推荐
            user_recs = self._user_based_recommendations(user_id, user_idx, n_recommendations)
            recommendations.extend(user_recs)

        if method == 'svd' or method == 'hybrid':
            # SVD推荐
            svd_recs = self._svd_recommendations(user_id, user_idx, n_recommendations)
            recommendations.extend(svd_recs)

        # 去重并排序
        seen_movies = set()
        unique_recommendations = []

        for movie_id, score, method_type in recommendations:
            if movie_id not in seen_movies:
                seen_movies.add(movie_id)
                unique_recommendations.append({
                    'movie_id': movie_id,
                    'score': score,
                    'method': method_type,
                    'metadata': self.movie_metadata.get(movie_id, {})
                })

        # 按得分排序
        unique_recommendations.sort(key=lambda x: x['score'], reverse=True)

        return unique_recommendations[:n_recommendations]

    def _item_based_recommendations(self, user_id, user_idx, n_recs):
        """基于物品的推荐逻辑"""
        if user_idx is None:
            return []

        # 获取用户评分过的电影
        user_ratings = self.user_movie_matrix[user_idx].toarray().flatten()
        rated_movies = np.where(user_ratings > 0)[0]

        recommendations = []

        for movie_idx in rated_movies:
            movie_id = self.movie_ids[movie_idx]
            rating = user_ratings[movie_idx]

            if movie_id in self.movie_similarity_df.index:
                # 找到与这个电影相似的其他电影
                similar_movies = self.movie_similarity_df[movie_id].sort_values(ascending=False)

                for similar_movie_id, similarity in similar_movies.items():
                    if similarity > 0.3 and similar_movie_id != movie_id:
                        # 预测评分 = 原评分 * 相似度
                        predicted_score = rating * similarity
                        recommendations.append((similar_movie_id, predicted_score, 'item_based'))

        return recommendations

    def _user_based_recommendations(self, user_id, user_idx, n_recs):
        """基于用户的推荐逻辑"""
        if user_idx is None:
            return []

        if user_id not in self.user_similarity_df.index:
            return []

        # 找到相似用户
        similar_users = self.user_similarity_df[user_id].sort_values(ascending=False)

        recommendations = []
        user_ratings = self.user_movie_matrix[user_idx].toarray().flatten()

        for similar_user_id, similarity in similar_users.items():
            if similarity > 0.3 and similar_user_id != user_id:
                similar_user_idx = self.user_ids.index(similar_user_id)
                similar_user_ratings = self.user_movie_matrix[similar_user_idx].toarray().flatten()

                # 找到相似用户看过但当前用户没看过的电影
                for movie_idx, rating in enumerate(similar_user_ratings):
                    if rating > 0 and user_ratings[movie_idx] == 0:
                        movie_id = self.movie_ids[movie_idx]
                        predicted_score = rating * similarity
                        recommendations.append((movie_id, predicted_score, 'user_based'))

        return recommendations

    def _svd_recommendations(self, user_id, user_idx, n_recs):
        """SVD矩阵分解推荐"""
        if user_idx is None:
            return []

        # 计算预测评分
        predicted_ratings = np.dot(self.user_factors[user_idx], self.item_factors.T)

        # 获取用户已评分的电影
        user_ratings = self.user_movie_matrix[user_idx].toarray().flatten()

        recommendations = []

        for movie_idx, predicted_score in enumerate(predicted_ratings):
            movie_id = self.movie_ids[movie_idx]
            # 只推荐用户没看过的电影
            if user_ratings[movie_idx] == 0 and predicted_score > 0:
                recommendations.append((movie_id, predicted_score, 'svd'))

        return recommendations

    def save_model(self):
        """保存模型到文件"""
        model_data = {
            'user_movie_matrix': self.user_movie_matrix,
            'movie_similarity_df': self.movie_similarity_df,
            'user_similarity_df': self.user_similarity_df,
            'user_factors': self.user_factors,
            'item_factors': self.item_factors,
            'user_ids': self.user_ids,
            'movie_ids': self.movie_ids,
            'movie_metadata': self.movie_metadata,
            'explained_variance': self.explained_variance
        }

        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"模型已保存到 {self.model_path}")

    def load_model(self):
        """从文件加载模型"""
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)

            self.user_movie_matrix = model_data['user_movie_matrix']
            self.movie_similarity_df = model_data['movie_similarity_df']
            self.user_similarity_df = model_data['user_similarity_df']
            self.user_factors = model_data['user_factors']
            self.item_factors = model_data['item_factors']
            self.user_ids = model_data['user_ids']
            self.movie_ids = model_data['movie_ids']
            self.movie_metadata = model_data['movie_metadata']
            self.explained_variance = model_data.get('explained_variance', 0)

            print(f"模型已从 {self.model_path} 加载")
            return True

        except Exception as e:
            print(f"加载模型失败: {e}")
            return False

    def get_popular_movies(self, n=10):
        """获取热门电影（基于评分人数和平均分）"""
        if not hasattr(self, 'movie_metadata'):
            if not self.load_model():
                return []

        movies_with_score = []

        for movie_id, metadata in self.movie_metadata.items():
            if 'avg_rating' in metadata and 'rating_count' in metadata:
                avg_rating = metadata['avg_rating'] or 0
                rating_count = metadata['rating_count'] or 0

                # 使用贝叶斯平均计算得分
                # (评分人数 * 平均分 + 全局平均 * 最小样本) / (评分人数 + 最小样本)
                bayesian_score = (rating_count * avg_rating + 3.0 * 10) / (rating_count + 10)

                movies_with_score.append({
                    'movie_id': movie_id,
                    'score': bayesian_score,
                    'avg_rating': avg_rating,
                    'rating_count': rating_count,
                    'metadata': metadata
                })

        # 按得分排序
        movies_with_score.sort(key=lambda x: x['score'], reverse=True)

        return movies_with_score[:n]


# 创建全局推荐器实例
recommender = MovieRecommender()