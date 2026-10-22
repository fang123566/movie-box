# 电影盒子 · 交付说明（Docker 全栈部署）

> 阶段 7 交付物。目标：**一条命令，在任何装了 Docker 的机器上跑起整套系统**，
> 不需要预先准备 Python 环境、不需要先跑数据采集管线、不需要手动建索引。

---

## 1. 交付内容

| 组件 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| elasticsearch | `yingjian-zhisou/es-ik:8.15.3` | 9200 | 官方 ES 8.15.3 + IK 中文分词插件 |
| backend | `yingjian-zhisou/backend:1.0.0` | 8000 | FastAPI + uvicorn，数据已打进镜像 |
| frontend | `yingjian-zhisou/frontend:1.0.0` | **8080** | Vite 构建产物 + nginx 托管 + /api 反代 |
| kibana（可选） | 官方 `kibana:8.15.3` | 5601 | `--profile tools` 才启动，平时不起 |

三个业务容器同在 `yjzs-net` 网络，用服务名互相寻址；
ES 数据落在命名卷 `yjzs_es_data`，`down`（不加 `-v`）不丢数据。

## 2. 环境要求

- Docker Engine ≥ 24（或 Docker Desktop），Compose v2
- 可用端口：8080（前端）、8000（后端）、9200（ES）；Kibana 另需 5601
- 内存：ES 默认堆 1 GB，整套约 2.5–3 GB；内存紧张可在 `.env` 里调
  `ES_JAVA_OPTS=-Xms512m -Xmx512m`
- 磁盘：三个镜像约 2.6 GB（ES 1.97 GB 是大头），ES 数据卷约 200 MB

## 3. 一键启动

```bash
# 在仓库根目录（有 docker-compose.yml 的目录）
docker-compose up -d
```

首次启动会自动按顺序完成：

1. **构建/拉取镜像**（本地已有则跳过；后端镜像构建约 1–2 分钟）
2. **ES 就绪**：compose 健康检查（`_cluster/health`）+ 后端入口再兜一层等待
3. **自动导索引**：入口检测到 `movies`/`reviews` 别名缺失时，用**镜像内烘焙的
   processed 数据**建库导入（幂等；已有索引则跳过，重启不会重导）
4. **起服务**：uvicorn（8000）+ nginx（80→宿主机 8080）

看到 `docker-compose ps` 三个容器都 `Up (healthy)` 即可打开
**<http://localhost:8080>**。

> 演示账号：`admin` / `admin123`（首次启动由后端自动播种）。
> 也可以直接在登录卡注册新账号，注册即登录。

## 4. 数据从哪来（为什么不用先跑采集）

后端镜像里 COPY 了两份数据资产：

- `data_lake/processed/` —— 488 部多源融合电影 + 49,873 条清洗后影评（约 87 MB），
  供索引导入；
- `data_lake/analysis/` —— 情感词典 / 主题榜 / 统计报告（约 3.7 MB），
  供 `/api/v1/insights/*` 接口直读（后端 mtime 缓存，不重复读盘）。

所以交付镜像 = 代码 + 数据 + 分析产物，**自包含**。
采集/清洗/分析管线（`ingest/` → `transform/` → `analysis/`）仍然完整保留在仓库里，
用于复现数据生产过程，但部署运行不依赖它们。

### 想更新数据怎么办

```bash
# 本机开发路径（方式 B）：重跑管线 → 重建索引 → 重建后端镜像
python -m transform.run_transform all            # 重新融合（文件→文件）
python -m index.run_index build --recreate       # 重建 ES 索引（别名原子切换）
docker-compose build backend                     # 新 processed 数据打进新镜像
docker-compose up -d backend                     # 滚动替换
```

## 5. 配置项

配置单源仍然是 `.env`（`common/settings.py` 读取），但**容器内不挂 .env**——
部署参数走 compose 的 `environment`，改这些不用碰 .env：

| 变量 | 默认 | 说明 |
|---|---|---|
| `ES_HOSTS` | `http://elasticsearch:9200` | 容器网络内 ES 地址（服务名）。**不要**透传宿主 .env 里的 `127.0.0.1:9200` |
| `API_PORT` | `8000` | 后端监听端口 |
| `IMAGE_FETCH_PROXY` | 空（直连） | 海报代理出口。宿主机有代理时填 `http://host.docker.internal:12001`（容器里 `127.0.0.1` 指容器自己，不是宿主机） |
| `ES_JAVA_OPTS` | `-Xms1g -Xmx1g` | ES 堆大小，内存紧张调小 |
| `ES_VERSION` / `IK_VERSION` | `8.15.3` | 升级 ES 时两个一起改（IK 必须与 ES 主版本一致） |

`.env` 里的 `IMAGE_FETCH_PROXY_DOCKER` 是给 compose 读取的可选代理变量，
只影响 Docker 部署，不影响本机开发。

### 改前端端口

编辑 `docker-compose.yml` 中 frontend 的 `ports: "8080:80"`，左边是宿主机端口。

## 6. 日常运维

```bash
docker-compose ps                    # 状态
docker-compose logs -f backend       # 后端日志（含索引导入进度）
docker-compose logs -f frontend      # nginx 访问日志
docker-compose restart backend       # 只重启后端
docker-compose down                  # 停全部，保留 ES 数据卷
docker-compose down -v               # 停全部 + 删数据卷（下次启动自动重导）
docker-compose build backend frontend # 改了代码后重建（ES 不用重建）
docker-compose --profile tools up -d # 起 Kibana
```

## 7. 已验证项（交付前实测，非纸上谈兵）

| 验证 | 方法 | 结果 |
|---|---|---|
| 干净卷一键部署 | `down -v` 后 `up -d`，模拟全新机器 | 自动导入 488 部 + 49,873 条，**0 失败，峰值内存 67.3 MB**（movies 1.6s / reviews 13.3s） |
| 接口回归（经 nginx 反代） | curl 打 8080 | 登录发 JWT · 电影检索（IK 分词）· 影评检索 · 情感洞察 · 年代趋势 · 主题榜 · 足迹地图 全 200 |
| 海报图片代理 | `/api/v1/img?url=<TMDB>` | 200 · image/jpeg · 102,464 B 真实图片；非白名单域名 400 拒绝 |
| SPA 深链接 | 直接访问 `/mix` 等前端路由 | 200（nginx try_files 回退 index.html） |
| 静态资源缓存 | `/assets/*.js` 响应头 | `Cache-Control: public, immutable`（7 天） |
| 前端全流程走查 | puppeteer 14 项走查（注册→登录→检索→详情→评分/想看→我的→推荐→盲盒→洞察→说明） | **14/14 通过，全程零控制台错误** |
| 登录/安全链路 | curl 全流程 | 错误密码 401 · 注册自动登录 · 改密后旧密码失效 · 想看清单增删查 · 未登录 401 · 不存在 id 404 |
| 文档数核对 | 删卷重建前后 `_count` 对比 | movies 488 / reviews 49,873 一致 |

复测命令：

```bash
# 接口冒烟（任选几项）
curl -s http://localhost:8080/api/v1/health
curl -s "http://localhost:8080/api/v1/search/movies?q=星际"

# 前端走查（需要 puppeteer-core，见 scripts/ 注释）
node scripts/verify_frontend_walkthrough.js http://localhost:8080
```

## 8. 常见问题

| 现象 | 原因与处理 |
|---|---|
| `up -d` 后 8080 打不开 | 看 `docker-compose ps`：backend 要 healthy 后 frontend 才起；首次导入约 15–30s。`logs -f backend` 看进度 |
| 端口被占用 | 改 compose 里 frontend 的 `ports` 左半（如 `"8081:80"`） |
| 海报裂图 | 宿主机网络到 image.tmdb.org 不通：设 `IMAGE_FETCH_PROXY_DOCKER=http://host.docker.internal:<你的代理端口>` 后 `up -d` 重建 backend |
| 中文搜索质量下降 | ES 镜像没带上 IK（跳过了 build）：`docker-compose build elasticsearch`，索引层会自动降级 cjk，功能不缺 |
| 想完全重来 | `docker-compose down -v` 再 `up -d`，数据自动重建（用户注册的演示数据也会清掉） |
| ES 起不来/黄状态 | 单节点 + 未分配副本是正常的 yellow；red 才异常，`logs -f elasticsearch` 排查 |

## 9. 课程答辩要点（与实现对应）

- **工程完整性**：采集（限速/退避/断点续跑）→ 清洗融合（字段优先级表）→ 索引
  （IK/别名原子切换）→ 服务（混合检索/分面/高亮）→ 分析（自归纳情感词典，
  留出集准确率 83.56%）→ 前端（11 视图）→ **部署（三容器一键拉起）** 全链路闭环。
- **大数据纪律**：全流程流式处理，实测峰值内存 67–95 MB 量级（IMDb 两遍扫描、
  Kaggle 5 万条影评均流式）；演示数据与真实数据物理隔离（曾抓出 49 部 Demo
  污染正式索引的事故）。
- **可复现**：`down -v` 清库后一条命令重建全部数据与索引，导入幂等。
- **安全意识**：JWT + bcrypt、登录失败限流、单 flight 缓存防雪崩、
  全局 500 兜底不泄露细节、图片代理域名白名单、XSS 高亮转义。
