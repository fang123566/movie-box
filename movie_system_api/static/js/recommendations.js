// static/js/recommendations.js

// 全局变量
let currentMethod = 'hybrid';
let currentLimit = 10;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 绑定方法选择按钮事件
    document.querySelectorAll('[data-method]').forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有按钮的active类
            document.querySelectorAll('[data-method]').forEach(b => {
                b.classList.remove('active');
            });
            // 添加当前按钮的active类
            this.classList.add('active');

            currentMethod = this.getAttribute('data-method');
            updateMethodBadge();
            loadRecommendations();
        });
    });

    // 绑定数量选择事件
    document.getElementById('recommendationLimit').addEventListener('change', function() {
        currentLimit = parseInt(this.value);
        loadRecommendations();
    });

    // 初始加载
    loadRecommendations();
    loadRecommendationStats();
});

// 更新方法显示
function updateMethodBadge() {
    const methodNames = {
        'hybrid': '混合算法',
        'item_based': '基于内容',
        'user_based': '协同过滤',
        'popular': '热门推荐'
    };
    document.getElementById('currentMethod').textContent = methodNames[currentMethod] || currentMethod;
}

// 加载推荐
async function loadRecommendations() {
    const container = document.getElementById('recommendationsContainer');
    container.innerHTML = `
        <div class="col-12 text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
            <p class="mt-2">正在为您生成个性化推荐...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/recommendations?method=${currentMethod}&limit=${currentLimit}`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        displayRecommendations(data.recommendations);
        updateCounts(data.total);
        document.getElementById('recommendationTime').textContent =
            `最后更新: ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        container.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>加载推荐失败: ${error.message}</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="loadRecommendations()">
                        重试
                    </button>
                </div>
            </div>
        `;
    }
}

// 显示推荐
function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendationsContainer');

    if (!recommendations || recommendations.length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    <p>暂无推荐数据，请先对电影进行评分或观看</p>
                    <a href="/movies" class="btn btn-sm btn-primary">去浏览电影</a>
                </div>
            </div>
        `;
        return;
    }

    let html = '';

    recommendations.forEach((movie, index) => {
        const scorePercent = Math.min(100, (movie.recommendation_score || 0) * 20);
        const predictedRating = movie.predicted_rating ? movie.predicted_rating.toFixed(1) : '--';

        // 获取推荐方法对应的样式
        let methodBadgeClass = '';
        let methodText = '';

        switch(movie.recommendation_method) {
            case 'item_based':
                methodBadgeClass = 'method-item';
                methodText = '基于内容';
                break;
            case 'user_based':
                methodBadgeClass = 'method-user';
                methodText = '协同过滤';
                break;
            case 'svd':
                methodBadgeClass = 'method-svd';
                methodText = '矩阵分解';
                break;
            case 'popular':
                methodBadgeClass = 'method-popular';
                methodText = '热门推荐';
                break;
        }

        html += `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card movie-card" onclick="showMovieDetail(${movie.movie_id})" style="cursor: pointer;">
                    <div class="recommendation-score">
                        <span class="badge ${methodBadgeClass} method-badge me-1">${methodText}</span>
                        ${predictedRating}
                    </div>
                    <div class="card-body">
                        <h6 class="card-title">${movie.title}</h6>
                        <div class="mb-2">
                            <small class="text-muted">
                                ${movie.release_year || '年份未知'} ·
                                ${movie.duration ? movie.duration + '分钟' : '时长未知'} ·
                                ${movie.director || '导演未知'}
                            </small>
                        </div>

                        <!-- 预测评分条 -->
                        <div class="mb-2">
                            <small class="text-muted">预测评分</small>
                            <div class="prediction-meter">
                                <div class="prediction-fill" style="width: ${scorePercent}%"></div>
                            </div>
                            <div class="d-flex justify-content-between small text-muted">
                                <span>1分</span>
                                <span>预测: ${predictedRating}分</span>
                                <span>5分</span>
                            </div>
                        </div>

                        <!-- 类型标签 -->
                        <div class="mb-2">
                            ${movie.genres.slice(0, 3).map(genre =>
                                `<span class="badge bg-secondary me-1">${genre}</span>`
                            ).join('')}
                            ${movie.genres.length > 3 ?
                                `<span class="badge bg-light text-dark">+${movie.genres.length - 3}</span>` : ''
                            }
                        </div>

                        <!-- 描述 -->
                        <p class="card-text small text-muted" style="
                            display: -webkit-box;
                            -webkit-line-clamp: 2;
                            -webkit-box-orient: vertical;
                            overflow: hidden;
                        ">
                            ${movie.description || '暂无描述'}
                        </p>

                        <!-- 操作按钮 -->
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation(); rateMovie(${movie.movie_id})">
                                <i class="fas fa-star"></i> 评分
                            </button>
                            <button class="btn btn-sm btn-outline-success" onclick="event.stopPropagation(); addToWatchlist(${movie.movie_id})">
                                <i class="fas fa-plus-circle"></i> 想看
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="event.stopPropagation(); findSimilar(${movie.movie_id})">
                                <i class="fas fa-arrow-right-circle"></i> 相似
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// 更新计数
function updateCounts(count) {
    document.getElementById('personalizedCount').textContent = count;
}

// 加载推荐统计
async function loadRecommendationStats() {
    try {
        const response = await fetch('/api/recommendations/stats');
        const stats = await response.json();

        if (stats.error) {
            throw new Error(stats.error);
        }

        // 更新计数卡片
        document.getElementById('activeUsers').textContent = stats.active_users || 0;
        document.getElementById('totalMovies').textContent = stats.total_movies || 0;
        document.getElementById('accuracyRate').textContent =
            stats.model_info?.explained_variance ?
            (stats.model_info.explained_variance * 100).toFixed(1) + '%' : 'N/A';

        // 创建图表
        createStatsChart(stats);

    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

// 创建统计图表
function createStatsChart(stats) {
    const ctx = document.getElementById('recommendationStatsChart').getContext('2d');

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['活跃用户', '非活跃用户'],
            datasets: [{
                data: [
                    stats.active_users || 0,
                    (stats.total_users || 0) - (stats.active_users || 0)
                ],
                backgroundColor: [
                    '#a73b28',
                    '#706162'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: '用户活跃度分布'
                }
            }
        }
    });
}

// 查找相似电影
async function findSimilarMovies() {
    const searchInput = document.getElementById('similarMovieSearch');
    const query = searchInput.value.trim();

    if (!query) {
        alert('请输入电影名称');
        return;
    }

    // 先搜索电影
    try {
        const response = await fetch(`/api/movies?search=${encodeURIComponent(query)}&limit=5`);
        const data = await response.json();

        if (data.movies && data.movies.length > 0) {
            const movie = data.movies[0];
            await showSimilarMovies(movie.movie_id);
        } else {
            document.getElementById('similarMoviesResult').innerHTML = `
                <div class="alert alert-warning">
                    未找到电影: "${query}"
                </div>
            `;
        }
    } catch (error) {
        console.error('搜索电影失败:', error);
    }
}

// 显示相似电影
async function showSimilarMovies(movieId) {
    const resultDiv = document.getElementById('similarMoviesResult');
    resultDiv.innerHTML = `
        <div class="text-center">
            <div class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
            <p class="small text-muted mt-2">正在查找相似电影...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/recommendations/similar/${movieId}?limit=5`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        if (data.similar_movies && data.similar_movies.length > 0) {
            let html = '<h6 class="mb-3">相似电影:</h6>';

            data.similar_movies.forEach(movie => {
                const similarity = (movie.similarity_score * 100).toFixed(1);

                html += `
                    <div class="card mb-2" onclick="showMovieDetail(${movie.movie_id})" style="cursor: pointer;">
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong class="small">${movie.title}</strong>
                                    <br>
                                    <small class="text-muted">
                                        ${movie.release_year || ''} ·
                                        ${movie.director ? movie.director.substring(0, 10) + '...' : ''}
                                    </small>
                                </div>
                                <span class="badge similarity-badge">${similarity}%</span>
                            </div>
                        </div>
                    </div>
                `;
            });

            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-info">
                    未找到相似电影
                </div>
            `;
        }

    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-danger">
                查找失败: ${error.message}
            </div>
        `;
    }
}

// 显示电影详情
async function showMovieDetail(movieId) {
    try {
        const response = await fetch(`/api/movies/${movieId}`);
        const movie = await response.json();

        if (movie.error) {
            throw new Error(movie.error);
        }

        // 更新模态框内容
        document.getElementById('movieDetailTitle').textContent = movie.title;

        const content = `
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body text-center">
                            <h3>${movie.avg_score || 0}</h3>
                            <div class="text-warning">
                                ${'★'.repeat(Math.floor(movie.avg_score || 0))}
                                ${'☆'.repeat(5 - Math.floor(movie.avg_score || 0))}
                            </div>
                            <p class="small text-muted">平均评分</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <p><strong>导演:</strong> ${movie.director || '未知'}</p>
                    <p><strong>上映年份:</strong> ${movie.release_year || '未知'}</p>
                    <p><strong>语言:</strong> ${movie.language || '未知'}</p>
                    <p><strong>时长:</strong> ${movie.duration ? movie.duration + '分钟' : '未知'}</p>
                    <p><strong>类型:</strong> ${movie.genres ? movie.genres.join(', ') : '无'}</p>
                </div>
            </div>
            <div class="mt-3">
                <h6>简介</h6>
                <p>${movie.description || '暂无简介'}</p>
            </div>
            <div class="mt-3">
                <button class="btn btn-primary" onclick="rateMovie(${movieId})">
                    <i class="fas fa-star"></i> 立即评分
                </button>
                <button class="btn btn-outline-primary ms-2" onclick="findSimilar(${movieId})">
                    <i class="fas fa-arrow-right-circle"></i> 查找相似电影
                </button>
            </div>
        `;

        document.getElementById('movieDetailContent').innerHTML = content;

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('movieDetailModal'));
        modal.show();

    } catch (error) {
        alert('加载电影详情失败: ' + error.message);
    }
}

// 刷新推荐
function refreshRecommendations() {
    loadRecommendations();
}

// 查找相似电影
function findSimilar(movieId) {
    // 关闭详情模态框
    const modal = bootstrap.Modal.getInstance(document.getElementById('movieDetailModal'));
    if (modal) {
        modal.hide();
    }

    // 搜索相似电影
    showSimilarMovies(movieId);
}

// 评分电影
async function rateMovie(movieId) {
    const score = prompt('请为这部电影评分（1-5分）:');
    if (score && score >= 1 && score <= 5) {
        try {
            const response = await fetch(`/api/ratings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    movie_id: movieId,
                    score: parseInt(score)
                })
            });

            const result = await response.json();
            if (result.success) {
                alert('评分成功！推荐列表将更新...');
                loadRecommendations();
            } else {
                alert('评分失败: ' + (result.message || '未知错误'));
            }
        } catch (error) {
            alert('评分失败: ' + error.message);
        }
    }
}

// 添加到想看列表
async function addToWatchlist(movieId) {
    try {
        const response = await fetch(`/api/history`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                movie_id: movieId,
                duration_watched: 0,
                completed: false
            })
        });

        const result = await response.json();
        if (result.success || result.message) {
            alert('已添加到想看列表！');
        } else {
            alert('添加失败');
        }
    } catch (error) {
        alert('添加失败: ' + error.message);
    }
}