// Dashboard 全局功能
let currentPage = 1;
const itemsPerPage = 10;

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 显示提示信息
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container-fluid');
    container.insertBefore(alertDiv, container.firstChild);
    
    // 自动消失
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.parentNode.removeChild(alertDiv);
        }
    }, 5000);
}

// 加载仪表板统计数据
async function loadDashboardStats() {
    try {
        console.log('正在加载仪表盘统计数据...');
        const response = await fetch('/api/dashboard/stats');

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('仪表盘统计数据响应:', data);

        if (data.error) {
            throw new Error(data.error);
        }

        // 更新DOM元素 - 添加更详细的日志
        const totalMoviesElem = document.getElementById('totalMovies');
        const totalUsersElem = document.getElementById('totalUsers');
        const totalRatingsElem = document.getElementById('totalRatings');
        const totalHistoryElem = document.getElementById('totalHistory');

        console.log('找到的元素:', {
            totalMovies: totalMoviesElem,
            totalUsers: totalUsersElem,
            totalRatings: totalRatingsElem,
            totalHistory: totalHistoryElem
        });

        if (totalMoviesElem) {
            totalMoviesElem.textContent = data.total_movies || 0;
            console.log('设置电影数:', data.total_movies);
        }
        if (totalUsersElem) {
            totalUsersElem.textContent = data.total_users || 0;
            console.log('设置用户数:', data.total_users);
        }
        if (totalRatingsElem) {
            totalRatingsElem.textContent = data.total_ratings || 0;
            console.log('设置评分数:', data.total_ratings);
        }
        if (totalHistoryElem) {
            totalHistoryElem.textContent = data.total_history || 0;
            console.log('设置历史记录数:', data.total_history);
        }

        console.log('仪表盘统计数据更新完成');
    } catch (error) {
        console.error('加载统计数据失败:', error);
        // 设置默认值
        document.getElementById('totalMovies').textContent = 0;
        document.getElementById('totalUsers').textContent = 0;
        document.getElementById('totalRatings').textContent = 0;
        document.getElementById('totalHistory').textContent = 0;
    }
}

// 加载图表数据
async function loadChartData() {
    try {
        const response = await fetch('/api/dashboard/chart-data');
        const data = await response.json();
        
        if (response.ok) {
            renderChart(data);
        }
    } catch (error) {
        console.error('加载图表数据失败:', error);
    }
}

// 在 dashboard.js 中找到 renderChart 函数，替换为以下代码：

// 渲染图表 - 美化版本
function renderChart(data) {
    const ctx = document.getElementById('dataChart').getContext('2d');

    // 销毁现有图表实例（如果存在）
    if (window.dataChartInstance) {
        window.dataChartInstance.destroy();
    }

    // 创建新的图表实例
    window.dataChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels || ['1月', '2月', '3月', '4月', '5月', '6月'],
            datasets: [{
                label: '新增用户',
                data: data.users || [65, 59, 80, 81, 56, 72],
                borderColor: '#8B7355', // 使用主题棕色
                backgroundColor: 'rgba(139, 115, 85, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#8B7355',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }, {
                label: '新增电影',
                data: data.movies || [28, 48, 40, 45, 36, 60],
                borderColor: '#696969', // 使用主题灰色
                backgroundColor: 'rgba(105, 105, 105, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#696969',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: {
                            size: 14,
                            weight: '600',
                            family: "'Segoe UI', 'Microsoft YaHei', sans-serif"
                        },
                        color: '#2c3e50'
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(44, 62, 80, 0.95)',
                    titleFont: {
                        size: 13,
                        weight: '600'
                    },
                    bodyFont: {
                        size: 13,
                        weight: '500'
                    },
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += context.parsed.y;
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '时间',
                        color: '#2c3e50',
                        font: {
                            size: 14,
                            weight: '600',
                            family: "'Segoe UI', 'Microsoft YaHei', sans-serif"
                        },
                        padding: {top: 10, bottom: 5}
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#5d6d7e',
                        font: {
                            size: 13,
                            weight: '500',
                            family: "'Segoe UI', 'Microsoft YaHei', sans-serif"
                        },
                        padding: 8
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '数量',
                        color: '#2c3e50',
                        font: {
                            size: 14,
                            weight: '600',
                            family: "'Segoe UI', 'Microsoft YaHei', sans-serif"
                        },
                        padding: {top: 5, bottom: 10}
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#5d6d7e',
                        font: {
                            size: 13,
                            weight: '500',
                            family: "'Segoe UI', 'Microsoft YaHei', sans-serif"
                        },
                        padding: 8
                    },
                    suggestedMin: 0
                }
            },
            interaction: {
                intersect: false,
                mode: 'nearest'
            },
            animations: {
                tension: {
                    duration: 1000,
                    easing: 'linear'
                }
            }
        }
    });
}

// 加载最近活动
async function loadRecentActivities() {
    try {
        const response = await fetch('/api/dashboard/recent-activities');
        const data = await response.json();
        
        const container = document.getElementById('recentActivities');
        
        if (response.ok && data.activities) {
            container.innerHTML = data.activities.map(activity => `
                <div class="activity-item">
                    <div class="activity-icon">
                        <i class="fas ${getActivityIcon(activity.type)}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-title">${activity.title}</div>
                        <div class="activity-time">${formatTime(activity.time)}</div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center text-muted py-3">暂无活动数据</div>';
        }
    } catch (error) {
        console.error('加载活动数据失败:', error);
        document.getElementById('recentActivities').innerHTML = 
            '<div class="text-center text-muted py-3">加载失败</div>';
    }
}

// 获取活动图标
function getActivityIcon(type) {
    const icons = {
        'rating': 'fa-star',
        'user': 'fa-user-plus',
        'movie': 'fa-video',
        'history': 'fa-history'
    };
    return icons[type] || 'fa-bell';
}

// 格式化时间
function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) { // 1分钟内
        return '刚刚';
    } else if (diff < 3600000) { // 1小时内
        return `${Math.floor(diff / 60000)}分钟前`;
    } else if (diff < 86400000) { // 1天内
        return `${Math.floor(diff / 3600000)}小时前`;
    } else {
        return date.toLocaleDateString();
    }
}

// 加载热门电影
async function loadTopMovies() {
    try {
        const response = await fetch('/api/movies/top?limit=5');
        const data = await response.json();
        
        const container = document.getElementById('topMovies');
        
        if (response.ok && data.movies) {
            container.innerHTML = data.movies.map(movie => `
                <div class="d-flex align-items-center mb-3">
                    <div class="movie-poster me-3" style="width: 60px; height: 80px;">
                        <i class="fas fa-film"></i>
                    </div>
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${movie.title}</h6>
                        <div class="d-flex align-items-center">
                            <span class="rating-stars me-2">
                                ${generateStarRating(movie.avg_score)}
                            </span>
                            <small class="text-muted">${movie.avg_score || '暂无评分'}</small>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center text-muted py-3">暂无电影数据</div>';
        }
    } catch (error) {
        console.error('加载热门电影失败:', error);
    }
}

// 生成星级评分
function generateStarRating(score) {
    if (!score) return '暂无评分';
    
    const fullStars = Math.floor(score);
    const halfStar = score % 1 >= 0.5;
    const emptyStars = 5 - fullStars - (halfStar ? 1 : 0);
    
    let stars = '';
    for (let i = 0; i < fullStars; i++) {
        stars += '<i class="fas fa-star"></i>';
    }
    if (halfStar) {
        stars += '<i class="fas fa-star-half-alt"></i>';
    }
    for (let i = 0; i < emptyStars; i++) {
        stars += '<i class="far fa-star"></i>';
    }
    return stars;
}

// 加载最新用户
async function loadNewUsers() {
    try {
        const response = await fetch('/api/users/recent?limit=5');
        const data = await response.json();
        
        const container = document.getElementById('newUsers');
        
        if (response.ok && data.users) {
            container.innerHTML = data.users.map(user => `
                <div class="d-flex align-items-center mb-3">
                    <div class="bg-primary rounded-circle d-flex align-items-center justify-content-center me-3" 
                         style="width: 40px; height: 40px;">
                        <i class="fas fa-user text-white"></i>
                    </div>
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${user.nickname || user.username}</h6>
                        <small class="text-muted">注册时间: ${formatTime(user.register_date)}</small>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center text-muted py-3">暂无用户数据</div>';
        }
    } catch (error) {
        console.error('加载最新用户失败:', error);
    }
}

// 电影管理功能
async function loadMovies(page = 1) {
    try {
        const search = document.getElementById('searchInput').value;
        const year = document.getElementById('yearFilter').value;
        const genre = document.getElementById('genreFilter').value;
        
        let url = `/api/movies?page=${page}&limit=${itemsPerPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (year) url += `&year=${year}`;
        if (genre) url += `&genre=${genre}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        const tbody = document.getElementById('moviesTableBody');
        
        if (response.ok && data.movies && data.movies.length > 0) {
            tbody.innerHTML = data.movies.map(movie => `
                <tr>
                    <td>${movie.movie_id}</td>
                    <td>
                        <strong>${movie.title}</strong>
                        ${movie.description ? `<br><small class="text-muted">${movie.description.substring(0, 50)}...</small>` : ''}
                    </td>
                    <td>${movie.release_year || '-'}</td>
                    <td>${movie.language || '-'}</td>
                    <td>${movie.duration ? `${movie.duration}分钟` : '-'}</td>
                    <td>${movie.director || '-'}</td>
                    <td>${movie.genres ? movie.genres.map(g => `<span class="badge bg-secondary me-1">${g}</span>`).join('') : '-'}</td>
                    <td>
                        <div class="rating-stars">
                            ${generateStarRating(movie.avg_score)}
                        </div>
                        <small class="text-muted">${movie.avg_score || '暂无'}</small>
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary" onclick="editMovie(${movie.movie_id})" title="编辑">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-danger" onclick="deleteMovie(${movie.movie_id})" title="删除">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
            
            renderPagination(data.total, page, 'movies');
        } else {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center py-4 text-muted">
                        <i class="fas fa-film fa-2x mb-3 d-block"></i>
                        暂无电影数据
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('加载电影失败:', error);
        showAlert('加载电影数据失败', 'danger');
    }
}

// 渲染分页
function renderPagination(totalItems, currentPage, type) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    const pagination = document.getElementById('pagination');
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // 上一页
    if (currentPage > 1) {
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(${currentPage - 1}, '${type}')">上一页</a></li>`;
    }
    
    // 页码
    for (let i = 1; i <= totalPages; i++) {
        if (i === currentPage) {
            html += `<li class="page-item active"><a class="page-link" href="#">${i}</a></li>`;
        } else {
            html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(${i}, '${type}')">${i}</a></li>`;
        }
    }
    
    // 下一页
    if (currentPage < totalPages) {
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(${currentPage + 1}, '${type}')">下一页</a></li>`;
    }
    
    pagination.innerHTML = html;
}

// 切换页面
function changePage(page, type) {
    currentPage = page;
    switch (type) {
        case 'movies':
            loadMovies(page);
            break;
        // 可以添加其他类型的分页处理
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM 加载完成，开始初始化仪表板...');

    // 初始化仪表板数据
    if (document.getElementById('dataChart')) {
        console.log('检测到仪表板页面，开始加载数据...');

        // 先加载统计数据
        loadDashboardStats();

        // 然后加载其他数据
        setTimeout(() => {
            loadChartData();
            loadRecentActivities();
            loadTopMovies();
            loadNewUsers();
        }, 100);

        // 刷新按钮
        document.getElementById('refreshBtn')?.addEventListener('click', function() {
            console.log('手动刷新数据...');
            loadDashboardStats();
            loadChartData();
            loadRecentActivities();
            loadTopMovies();
            loadNewUsers();
            showAlert('数据已刷新', 'success');
        });
    }

    // 导出按钮
    document.getElementById('exportBtn')?.addEventListener('click', function() {
        showAlert('导出功能开发中...', 'info');
    });
});

// 电影编辑和删除功能（需要在具体页面中实现）
async function editMovie(movieId) {
    // 实现编辑电影逻辑
    showAlert(`编辑电影 ID: ${movieId}`, 'info');
}

async function deleteMovie(movieId) {
    if (confirm('确定要删除这部电影吗？此操作不可撤销。')) {
        try {
            const response = await fetch(`/api/movies/${movieId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                showAlert('电影删除成功', 'success');
                loadMovies(currentPage);
            } else {
                showAlert('删除失败', 'danger');
            }
        } catch (error) {
            console.error('删除电影失败:', error);
            showAlert('删除失败', 'danger');
        }
    }
}

