# 阶段 5 方案 · Vue3 前端（混合检索 + 影评洞察）

> 状态：**待 yuan 确认**。确认后按第 6 节分步实施，每步独立可验证。
> 本文档是「方案 + 目录」交付物；代码实现从下一步开始。

## 1. 定位与信息架构

电影盒子是**检索与发现平台**，不是管理后台。因此顶导航只有三个入口，
首页即检索，数据面板**不放在首页**（yuan 2026-10-15 明确要求），
独立为「影评洞察」页：

```
顶导航（继承原系统 layout.html 的角色二分与用户区结构）
┌──────────────────────────────────────────────────────────┐
│ 🎬 电影盒子 │ 混合检索  影评洞察  项目说明        │ 用户区 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  路由 /        → HomeView      混合检索（首页）            │
│  路由 /insights→ InsightsView  影评洞察（数据面板独立成页） │
│  路由 /about   → AboutView     项目说明（数据源/合规/进度） │
│                                                          │
│  阶段 6 预留：/fun/* 类型混搭器 · 盲盒 · 足迹地图            │
└──────────────────────────────────────────────────────────┘
```

### 与原系统的页面对照（蓝本映射）

| 原系统页面 | 新平台对应 | 演变说明 |
|---|---|---|
| `/dashboard` 数据面板（首页） | `/insights` 影评洞察 | **从首页迁出独立成页**；四统计卡换成大数据指标（影评总量/影片数/正面率/主题词数） |
| `/` 登录页 | 阶段 6 用户模块 | 登录态未接入前，用户区显示「演示模式」 |
| `/movies` 电影浏览/管理 | `/` 混合检索首页 | SQL 查询 → ES 混合检索 + 分面 + 高亮，新增「影评」检索 Tab |
| 数据趋势分析图（Chart.js） | 年代趋势图（ECharts） | 新增后端 `/insights/trends` 接口供图 |
| `/recommendations` 智能推荐 | 阶段 6 推荐模块 | pkl SVD → 向量召回 + 情感感知重排 |
| 最近活动 | 暂不做 | 采集/分析流水线事件流，阶段 7 运维页再做 |
| `/ops` 系统运维 | 阶段 7 运维页 | ES 集群健康 / 索改进度 / 峰值内存 |
| `/profile` `/settings` | 阶段 6 用户模块 | 直接迁移 |
| 棕灰主题 + 渐变导航 + 卡片仪表盘 | **全局视觉，整体继承** | 见第 4 节 |

## 2. 技术选型

| 项 | 选型 | 理由 |
|---|---|---|
| 框架 | Vue 3.5（Composition API + `<script setup>`） | 课程栈已定 |
| 构建 | Vite 7 | 课程栈已定；dev server 5173 与后端 CORS 白名单已对齐 |
| 路由 | Vue Router 4（history 模式） | 三页 + 阶段 6 扩展位 |
| 图表 | ECharts 5.6 + vue-echarts | 课程栈已定；饼图/条形/折线都够用 |
| HTTP | 原生 fetch 封装（不引 axios） | 接口少而简单，少一条依赖链 |
| UI 框架 | **不用** Element Plus 等重型库 | 页面就两个，手写 CSS 才能完整继承棕灰主题，构建也快 |
| 状态 | 组件内 ref/reactive，不引 Pinia | 检索状态只在 HomeView 用；阶段 6 上 Pinia |

**开发联调**：`vite.config.js` 里把 `/api` 代理到 `http://127.0.0.1:8000`，
开发期不走 CORS，后端零改动。

## 3. 目录结构（将创建）

```
frontend/
├── index.html                  Vite 入口（<div id="app"> + 模块脚本）
├── package.json                依赖与脚本：dev / build / preview
├── vite.config.js              dev server + /api 代理 + build 输出 dist/
├── .gitignore                  node_modules/ dist/
├── public/
│   └── favicon.svg             胶片图标（继承原系统 fa-clapperboard 意象）
└── src/
    ├── main.js                 装配：createApp + router + theme.css
    ├── App.vue                 根组件：AppHeader + <router-view> + AppFooter
    ├── router/
    │   └── index.js            路由表（/ · /insights · /about + 阶段 6 占位注释）
    ├── api/
    │   └── index.js            请求层（见第 5 节接口映射）
    ├── styles/
    │   └── theme.css           棕灰主题 CSS 变量 + 基础排版 + 通用组件类
    ├── components/
    │   ├── layout/
    │   │   ├── AppHeader.vue   渐变导航栏（品牌 + 页面导航 + 用户区）
    │   │   └── AppFooter.vue   页脚（数据源合规声明）
    │   ├── search/
    │   │   ├── SearchBox.vue       品牌大搜索框（停输 250ms 联想，键盘上下选）
    │   │   ├── FacetRail.vue       左侧分面栏（类型/国家/语言/年份/评分/来源）
    │   │   ├── ActiveChips.vue     已选条件 chips（点 × 移除 + 全部清除）
    │   │   ├── SortBar.vue         排序切换 + 结果计数 + 耗时 + 影片/影评 Tab
    │   │   ├── MovieCard.vue       影片卡（海报/评分/年份/类型/多源徽章/导演）
    │   │   ├── MovieGrid.vue       结果网格 + 加载骨架 + 空态 + 分页
    │   │   └── ReviewPanel.vue     影评列表（情感标签 + 关键词高亮 + 篇幅）
    │   └── insights/
    │       ├── StatStrip.vue       统计卡条（4 张，继承原系统四卡样式）
    │       ├── SentimentChart.vue  情感分布饼图
    │       ├── GenreChart.vue      类型均分横向条形图
    │       ├── TrendChart.vue      年代趋势折线图（影片数 + 均分双轴）
    │       ├── TopicBoard.vue      主题词榜（夸什么 / 骂什么双栏）
    │       └── LexiconBoard.vue    归纳词典 Top N（正面 / 负面双栏 + 元信息）
    └── views/
        ├── HomeView.vue         首页 = 混合检索（SearchBox + FacetRail + 结果区）
        ├── InsightsView.vue     影评洞察（StatStrip + 4 图表区 + 2 榜单）
        └── AboutView.vue        项目说明（数据源 5 个 + 合规红线 + 阶段进度表）
```

## 4. 视觉主题（从原 layout.html 继承）

`src/styles/theme.css` 直接移植原系统的主题变量，不改色相：

```css
:root{
  --primary-brown:#8B7355;   /* 导航渐变起点 */
  --primary-gray:#696969;    /* 导航渐变终点 */
  --light-brown:#A68A6D;     /* hover / 强调 */
  --dark-brown:#6B4F3A;      /* 标题文字 */
  --warm-gray:#8C8C8C;
  --light-beige:#F5F5DC;     /* 页面背景 */
}
```

继承的视觉语言：135° 棕灰渐变导航栏、圆角半透明 hover、
`fade-in-up` 逐卡入场动画（统计卡错开 0.1s）、标题 800 字重居中、
深棕渐变页脚。新增的检索页沿用同一套变量，不引入第二套色板。

## 5. 接口映射（全部已有，只新增一个）

前端只调 `/api/v1/*`，代理后同源：

| 前端动作 | 接口 | 用到响应里的 |
|---|---|---|
| 影片检索 | `POST /api/v1/search/movies` | `hits`（MovieHit）+ `facets`（Facet，selected 已由后端算好）+ `meta` |
| 影评检索 | `POST /api/v1/search/reviews` | `hits`（ReviewHit 含 sentiment_score/highlight）+ `facets` |
| 搜索联想 | `GET /api/v1/search/suggest?q=` | SuggestItem（片名/年份/评分） |
| 影片详情 | `GET /api/v1/search/movies/{id}` | MovieHit 全字段 |
| 情感分布 + 类型均分 | `GET /api/v1/insights/sentiment` | `total` / `buckets` / `positive_ratio` / `by_genre` |
| 主题词榜 | `GET /api/v1/insights/topics?top=30` | `keywords`（含 df_positive/df_negative/lift/side） |
| 归纳词典 | `GET /api/v1/insights/lexicon?top=20` | `top_positive` / `top_negative` / `meta` |
| 单片画像 | `GET /api/v1/insights/movies/{id}` | keywords + sentiment_hint |
| 情感打分演示 | `POST /api/v1/insights/sentiment` | hits 高亮词（可解释性演示条，放影评洞察页） |
| **年代趋势（新增）** | `GET /api/v1/insights/trends` | 按年代聚合的影片数 + 平均分 |

唯一的后端增量：`GET /api/v1/insights/trends`（约 30 行）——
movies 索引上对 `release_year` 做 range/date_histogram 聚合，
每十年一桶，返回影片数与均分，替代原系统的「数据趋势分析」图位。

## 6. 分步实施计划（每步独立可验证）

| 步骤 | 内容 | 验证方法 |
|---|---|---|
| 1 | 脚手架：Vite 工程 + theme.css + App.vue 骨架 + 路由 + AppHeader/AppFooter | `npm run dev` 后 5173 看到棕灰主题三页框架，导航可切 |
| 2 | api 层 + HomeView 影片检索：SearchBox（联想）+ FacetRail + MovieCard + 分页 | 搜「流浪地球」出结果；点类型分面结果收窄且分面计数不锁死 |
| 3 | 影评 Tab：ReviewPanel + 情感标签 + 高亮 + 情感分面 | 切到影评 Tab 搜「boring」，negative 分面计数正确 |
| 4 | InsightsView：StatStrip + 饼图 + 条形图 + 主题榜 + 词典 + 打分演示条 | 六个区块全部出数；词典元信息展示「14381 词 / 归纳法」 |
| 5 | 后端 trends 接口 + TrendChart + AboutView + `npm run build` 产物验证 | build 通过；trends 接口 200；三页走查一遍 |

步骤 1–5 每步完成即汇报，不跨步堆代码。

## 7. 明确不做（控制范围）

- 登录/注册/角色权限 → 阶段 6
- 推荐与趣味功能 → 阶段 6
- Docker 化前端 → 阶段 7
- 移动端深度适配 → 只保证 768px 以上可用（课程演示场景）

## 8. 依赖安装预估

```bash
cd frontend
npm create vite@latest . -- --template vue      # 或手写 package.json
npm i vue-router echarts vue-echarts
npm i -D vite @vitejs/plugin-vue
```

预计 node_modules 约 120 MB（vue + echarts 大头），`npm run build` 产物约 400 KB（gzip 后约 130 KB）。
