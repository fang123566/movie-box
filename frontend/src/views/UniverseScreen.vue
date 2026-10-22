<template>
  <!--
    ============================================================
    电影盒子 · 影评洞察大屏（全屏 HUD）
    ------------------------------------------------------------
    用户 2026-10-19 定调：影评洞察页 = 这个数据分析大屏本体，
    不做纵向长网页。100vh 一屏、零滚动条，全部真实数据（ES 聚合）。

    两层：
      大厅（默认）：手绘影院外墙，六扇门 = 六个分类，推门进展厅（itomdev.com 式房间导航）
      展厅：顶部馆内导览（回大厅/串门/门牌直达）+ 中央图表 + 左翼 + 右翼 + 底部真实影评流
    ============================================================
  -->
  <div ref="root" class="dashboard-container">

    <!-- ========== 底层：3D 粒子星系（图表模式下压暗不卸载） ========== -->
    <div class="three-canvas-layer" :class="{ 'is-dim': mode !== 'room' || view !== 'galaxy' }">
      <!-- 深空背板：浅色页面上给粒子一块可见的"夜空"（椭圆盘=星系本体形状，
           边缘羽化融入暖白页面；没有它 NormalBlending 的粒子会被白底洗没） -->
      <div class="galaxy-bg" aria-hidden="true" />
      <GalaxyStage :movies="movies" :paused="hudHover || mode !== 'room' || view !== 'galaxy'" />
    </div>

    <!-- ========== 大厅层：六扇门，推门进入对应展厅（itomdev.com 式房间导航） ========== -->
    <InsightHouse
      v-if="mode === 'house'"
      class="house-layer"
      :rooms="VIEWS"
      @enter="enterRoom"
    />

    <!-- ========== 上层：悬浮 HUD（大厅模式下只留顶栏，其余区块收起） ========== -->
    <div class="hud-layer">

      <!-- ---- 01 顶部状态栏 ---- -->
      <header class="top-bar" @pointerenter="hudHover = true" @pointerleave="hudHover = false">
        <div class="top-bar__brand">
          <span class="top-bar__logo">影评洞察</span>
          <span class="top-bar__sub">实时数据分析大屏</span>
        </div>
        <div class="top-bar__spacer" />
        <div class="top-bar__meta">
          <span>影评 <b class="top-bar__num"><RollingNumber :value="reviewTotal" :duration="2000" /></b> 条</span>
          <span>影片 <b class="top-bar__num"><RollingNumber :value="movieTotal" :duration="1800" /></b> 部</span>
          <span>星图采样 <b class="top-bar__num"><RollingNumber :value="movies.length" :duration="1600" /></b> 部</span>
          <span class="top-bar__live"><i class="top-bar__dot" />实时</span>
        </div>
        <button class="top-bar__btn" type="button" @click="toggleFs">⛶ 全屏</button>
      </header>

      <!-- 大厅模式：悬浮导览图按钮（itomdev 汉堡钮位，常驻可见，不会进展厅就找不到北） -->
      <button v-show="mode === 'house'" class="house-map-btn" type="button" @click="mapOpen = true">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" /></svg>
        <span>导览图</span>
      </button>

      <!-- ---- 02 中央图表剧场（Flourish 式动态图表） ---- -->
      <!-- 标签栏常驻可见（用户反馈：星系视图下上方看不到切换入口）：
           星系视图只显示标签、不显示图表面板；切到图表视图再展开面板 -->
      <!-- 馆内导览：回大厅 / 当前展厅门牌 / 串门 / 六扇门直达
           （原 16s 自动轮播停用：房间是"走进去"的，不该自己换房） -->
      <div v-show="mode === 'room'" class="stage-dock" @pointerenter="hudHover = true" @pointerleave="hudHover = false">
        <div class="room-nav">
          <!-- ★ 返回入口（用户三次反馈"看不到返回按钮"）：大号高对比 pill + 导览图圆钮双保险 -->
          <button class="room-nav__back" type="button" @click="backToHouse">← 回大厅</button>
          <button class="room-nav__map" type="button" aria-label="打开导览图" title="导览图" @click="mapOpen = true">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" /></svg>
          </button>

          <div class="room-nav__plate">
            <i class="room-nav__icon">{{ curView.icon }}</i>
            <b>{{ curView.zh }}</b>
            <span>独立展厅 · 仅本门数据</span>
          </div>
          <!-- 每个展厅相互独立：进展厅后只保留「回大厅」出口，不提供串门 / 门牌直达，
               避免在一个门里跳转到其他门的数据（用户 2026-10-22 要求做分离）；
               换展厅请走「回大厅」或导览图 -->
        </div>
        <div v-show="view !== 'galaxy'" class="stage-panel">
          <div class="stage-panel__inner">
            <Transition name="stage-fade" mode="out-in">
              <BoxOfficeGallery
                v-if="view === 'box'"
                :gallery="boxOffice?.gallery || []"
                :total-movies="boxOffice?.total_movies || 0"
                :total-revenue="boxOffice?.total_revenue || 0"
                :top-year="boxOffice?.top_year"
                :pick="boxPick"
              />
              <BumpChart v-else-if="view === 'rank'" :matrix="matrix" />
              <SankeyFlow v-else-if="view === 'flow'" :matrix="matrix" />
              <DivergenceChart v-else-if="view === 'diverge'" :divergence="douban?.rating_divergence || []" />
              <GlobeMapPanel v-else-if="view === 'globe'" :points="mapPoints" @select="onMapSelect" />
            </Transition>
          </div>
        </div>
      </div>

      <!-- ---- 03 左翼：回声廊 / 词典词云 ---- -->
      <section
        v-show="mode === 'room'"
        class="left-panel hud-panel"
        @pointerenter="hudHover = true"
        @pointerleave="hudHover = false"
      >
        <div class="hud-panel__body">
          <i class="hud-panel__scan" />
          <div class="hud-title">
            <i class="hud-title__bar" />
            <span class="hud-title__zh">{{ panelMeta[leftTab].zh }}</span>
            <span class="hud-title__en">{{ panelMeta[leftTab].en }}</span>
            <i class="hud-title__line" />
          </div>
          <div class="panel-tabs">
            <button
              v-for="t in curView.left"
              :key="t"
              class="panel-tab"
              :class="{ 'is-on': leftTab === t }"
              type="button"
              @click="leftTab = t"
            >{{ panelMeta[t].tab }}</button>
          </div>
          <div class="panel-scroll">
            <Transition name="stage-fade" mode="out-in">
              <EchoChamber v-if="leftTab === 'echo'" :sentiment="sentiment" :lexicon="lexicon" />
              <WordCloudCard v-else-if="leftTab === 'cloud'" :lexicon="lexicon" />
              <DoubanPanel v-else-if="leftTab === 'douban'" :douban="douban" />
              <BoxOfficeRank
                v-else-if="leftTab === 'boxrank'"
                :gallery="boxOffice?.gallery || []"
                :total-movies="boxOffice?.total_movies || 0"
                @pick="boxPick = $event"
              />
            </Transition>
          </div>
        </div>
      </section>

      <!-- ---- 04 右翼：叙事时间轴 / 类型口碑榜 ---- -->
      <section
        v-show="mode === 'room'"
        class="right-panel hud-panel"
        @pointerenter="hudHover = true"
        @pointerleave="hudHover = false"
      >
        <div class="hud-panel__body">
          <i class="hud-panel__scan" />
          <div class="hud-title">
            <i class="hud-title__bar" />
            <span class="hud-title__zh">{{ panelMeta[rightTab].zh }}</span>
            <span class="hud-title__en">{{ panelMeta[rightTab].en }}</span>
            <i class="hud-title__line" />
          </div>
          <div class="panel-tabs">
            <button
              v-for="t in curView.right"
              :key="t"
              class="panel-tab"
              :class="{ 'is-on': rightTab === t }"
              type="button"
              @click="rightTab = t"
            >{{ panelMeta[t].tab }}</button>
          </div>
          <div class="panel-scroll">
            <Transition name="stage-fade" mode="out-in">
              <StoryTimeline v-if="rightTab === 'story'" :trends="trends" />
              <GenreRankCard v-else-if="rightTab === 'rank'" :by-genre="sentiment?.by_genre || []" />
              <CoveragePanel v-else-if="rightTab === 'coverage'" :douban="douban" />
              <BoxOfficeTrend
                v-else-if="rightTab === 'boxtrend'"
                :years="boxOffice?.years || []"
                :total-revenue="boxOffice?.total_revenue || 0"
                :total-movies="boxOffice?.total_movies || 0"
              />
            </Transition>
          </div>
        </div>
      </section>

      <!-- ---- 05 星系读图指南（galaxy 视图专属：用户反馈"看不懂星系在表达什么"） ---- -->
      <div
        v-if="mode === 'room' && view === 'galaxy'"
        class="galaxy-legend"
        @pointerenter="hudHover = true"
        @pointerleave="hudHover = false"
      >
        <div class="galaxy-legend__head">📖 怎么读这张星图<i>每颗星 = 一部真实影片</i></div>
        <div class="galaxy-legend__row">
          <span class="gl-item"><i class="gl-item__bar" />颜色 = 影片口碑</span>
          <span class="gl-item">星星越大 = 讨论越热</span>
          <span class="gl-item">越靠核心 = 越热门</span>
          <span class="gl-item">每条旋臂 = 一个电影类型</span>
        </div>
        <div class="galaxy-legend__stats">
          采样 {{ movies.length }} 部 · 均分 {{ avgRating.toFixed(1) }} · {{ armCount }} 条类型旋臂 · 悬停任意星星查看影片详情
        </div>
      </div>

      <!-- ---- 05b 取景地图图例 / 地点影片卡（globe 视图，同一槽位切换） ---- -->
      <div v-else-if="mode === 'room' && view === 'globe' && !loc" class="globe-hud">
        <span><i class="globe-hud__dot globe-hud__dot--film" />拍摄地</span>
        <span><i class="globe-hud__dot globe-hud__dot--story" />故事发生地</span>
        <span>脉冲环 = 影片数最多的取景地</span>
        <span class="globe-hud__hint">拖动旋转 · 滚轮缩放 · 点击光点看当地影片</span>
      </div>
      <div v-else-if="mode === 'room' && view === 'globe' && loc" class="loc-card">
        <div class="loc-card__head">
          <b>{{ loc.name }}</b>
          <span>{{ loc.kind === 'filming' ? '拍摄地' : '故事发生地' }} · {{ loc.movies }} 部影片</span>
          <button type="button" title="关闭" @click="loc = null">✕</button>
        </div>
        <div class="loc-card__body">
          <span v-if="locLoading" class="loc-card__tip">加载中…</span>
          <template v-else-if="locMovies.length">
            <button
              v-for="mv in locMovies"
              :key="mv.movie_id"
              type="button"
              class="loc-card__movie"
              @click="$router.push(`/movie/${mv.movie_id}`)"
            >{{ mv.title_zh || mv.title || mv.movie_id }}</button>
          </template>
          <span v-else class="loc-card__tip">暂无关联影片</span>
        </div>
      </div>

      <!-- ---- 05c 中央悬浮提示条（图表视图） ---- -->
      <div v-else-if="mode === 'room'" class="center-hud">
        <i />{{ centerHint }}
      </div>

      <!-- ---- 06 底部真实影评流 ---- -->
      <footer
        v-show="mode === 'room'"
        class="bottom-bar"
        @pointerenter="hudHover = true"
        @pointerleave="hudHover = false"
      >
        <div class="bottom-bar__head">
          <span>◈ 真实影评流</span>
          <span>· 中文真实影评 · {{ reviews.length }} 条</span>
        </div>
        <div class="bottom-bar__track">
          <!-- 恒速滚动：时长由 JS 按轨道实测宽度反推（streamDur），内容增减速度不变 -->
          <div class="stream-track" :style="{ animationDuration: streamDur }">
            <span v-for="(c, i) in loopChips" :key="'s' + i" class="stream-chip">
              <i
                class="stream-chip__tag"
                :class="c.tone === 'neg' ? 'stream-chip__tag--neg' : 'stream-chip__tag--pos'"
              >{{ c.tone === 'neg' ? '差评' : '好评' }}</i><b v-if="c.title" class="stream-chip__title">《{{ c.title }}》</b>{{ c.text }}
            </span>
          </div>
        </div>
      </footer>

    </div>

    <!-- 手绘导览图（itomdev MAP 面板）：大厅=传送地图，展厅=当前位置 + 回大厅 -->
    <InsightMap
      v-if="mapOpen"
      :rooms="VIEWS"
      :mode="mode"
      :current="view"
      @enter="onMapEnter"
      @back="onMapBack"
      @close="mapOpen = false"
    />
  </div>
</template>

<script setup>
// ============================================================
// 影评洞察大屏 /screen（用户定调：洞察页 = 数据分析大屏本体）
//   · 数据：sentiment / trends / matrix / boxOffice / lexicon / movies / reviews /
//     mapPoints，全部真实接口（matrix = ES 类型×年代聚合；boxOffice = ES 票房
//     聚合 + TOP 影片，2026-10-22 起替代原「类型竞赛」展厅；
//     mapPoints = /fun/map，Wikidata 拍摄地坐标，3D 地球数据源）
//   · 视图：星图（3D 粒子，悬停可读单部影片）/ 票房（itomdev 式相框绳画廊）/
//     排名（口碑变化）/ 流向（桑基）/ 分歧（豆瓣对比）/ 地图（3D 地球取景地）
//   · 3D 层切走时只压暗不卸载：反复销毁 WebGL context 会掉显存
//   · globe.gl 体积大：取景地图视图用 defineAsyncComponent 懒加载，进视图才下载
// ============================================================
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import gsap from 'gsap'
import { api } from '../api'
import GalaxyStage from '../components/screen/GalaxyStage.vue'
import BoxOfficeGallery from '../components/screen/BoxOfficeGallery.vue'
import BoxOfficeRank from '../components/screen/BoxOfficeRank.vue'
import BoxOfficeTrend from '../components/screen/BoxOfficeTrend.vue'
import BumpChart from '../components/screen/BumpChart.vue'
import SankeyFlow from '../components/screen/SankeyFlow.vue'
import EchoChamber from '../components/screen/EchoChamber.vue'
import WordCloudCard from '../components/screen/WordCloudCard.vue'
import StoryTimeline from '../components/screen/StoryTimeline.vue'
import GenreRankCard from '../components/screen/GenreRankCard.vue'
import DivergenceChart from '../components/screen/DivergenceChart.vue'
import DoubanPanel from '../components/screen/DoubanPanel.vue'
import CoveragePanel from '../components/screen/CoveragePanel.vue'
import RollingNumber from '../components/screen/RollingNumber.vue'
import InsightHouse from '../components/screen/InsightHouse.vue'
import InsightMap from '../components/screen/InsightMap.vue'
// 取景地地球散点面板（重建版，迁入 screen 目录）
const GlobeMapPanel = defineAsyncComponent(() => import('../components/screen/GlobeMapPanel.vue'))

const root = ref(null)
const hudHover = ref(false)

const movies = ref([])
const sentiment = ref(null)
const trends = ref(null)
const matrix = ref(null)
const boxOffice = ref(null)  // 票房分析（/insights/box-office）
const boxPick = ref(null)    // 左翼票房榜点选 → 中央画廊打开同一部档案
const lexicon = ref(null)
const reviews = ref([])
const mapPoints = ref([])   // 取景地坐标（/fun/map）
const douban = ref(null)    // 豆瓣联合洞察（/douban/insights，并入本大屏）

const reviewTotal = computed(() => sentiment.value?.total || 0)
const movieTotal = computed(() => trends.value?.total_movies || 0)

/* ---------- 星图图例统计（与 GalaxyStage 内部同口径） ---------- */
const avgRating = computed(() => {
  const ms = movies.value
  return ms.length ? ms.reduce((s, m) => s + (Number(m.rating) || 0), 0) / ms.length : 0
})
const armCount = computed(() => {
  const c = new Map()
  for (const m of movies.value) {
    const g = (m.genres_zh || [])[0] || '其他'
    c.set(g, (c.get(g) || 0) + 1)
  }
  return Math.min(6, c.size)
})

/* ---------- 视图切换（含 16s 自动轮播） ---------- */
// 命名原则（用户 2026-10-19）：从用户视角说清"这是做什么的"，不用抽象词
/* ---------- 房间（展厅）与大厅 ----------
   itomdev.com 的房间式导航：大屏的六个分类 = 六扇门，推开就是一间展厅。
   glow = 门缝里透出的展厅光，desc = 门牌提示（悬停时显示在底部条）。
   left / right = 这间展厅两翼的配套数据面板（与中央图表同主题，避免每间房都摆同一套）。
   每个面板 key 对应一个已实现的子组件（见 panelMeta）。 */
const VIEWS = [
  { key: 'galaxy', zh: '口碑星图', icon: '🌌', desc: '每颗星是一部影片，越亮越热', glow: '#3B2F63', tint: '#6D28D9',
    left: ['echo'], right: ['story'] },
  { key: 'box', zh: '票房分析', icon: '🎬', desc: '全球票房 TOP 挂在绳上，点框看档案', glow: '#8B4513', tint: '#C2410C',
    left: ['boxrank'], right: ['boxtrend'] },
  { key: 'rank', zh: '口碑排名', icon: '📈', desc: '各类型口碑位次变化', glow: '#A0522D', tint: '#B45309',
    left: ['douban'], right: ['rank'] },
  { key: 'flow', zh: '年代流向', icon: '🌊', desc: '类型与年代之间的影片流向', glow: '#0F766E', tint: '#0F766E',
    left: ['story'], right: ['coverage'] },
  { key: 'diverge', zh: '口碑分歧', icon: '⚖️', desc: '豆瓣评分与本站情感的分歧', glow: '#7D3C1E', tint: '#A67C2E',
    left: ['douban'], right: ['echo'] },
  { key: 'globe', zh: '取景地图', icon: '🌍', desc: '全球取景地分布，可点光点看影片', glow: '#1E4E6B', tint: '#2563EB',
    left: ['coverage'], right: ['story'] },
]

/* 六个配套面板：标题 / 副题 / 标签名 / 对应组件。
   两翼面板不再写死成"回声廊+叙事轴"一套，而是按当前展厅取 curView.left/right。 */
const panelMeta = {
  echo:    { zh: '跨文化回声廊', en: '情感分布 · 归纳词典', tab: '情感分布', comp: 'EchoChamber' },
  cloud:   { zh: '高频词云',     en: '归纳词典词频',       tab: '高频词云', comp: 'WordCloudCard' },
  douban:  { zh: '豆瓣口碑',     en: '评分分歧 · 高分榜',   tab: '豆瓣口碑', comp: 'DoubanPanel' },
  story:   { zh: '叙事时间轴',   en: '年代影片叙事',       tab: '年代故事', comp: 'StoryTimeline' },
  rank:    { zh: '类型口碑榜',   en: '各类型口碑评分',     tab: '类型口碑', comp: 'GenreRankCard' },
  coverage:{ zh: '预告覆盖',     en: '高分片预告触达',     tab: '预告覆盖', comp: 'CoveragePanel' },
  boxrank: { zh: '全球票房榜',   en: 'TOP 10', tab: '票房榜',   comp: 'BoxOfficeRank' },
  boxtrend:{ zh: '年度票房',     en: '上映年合计 · 亿美元', tab: '年度趋势', comp: 'BoxOfficeTrend' },
}
const view = ref('galaxy')

/* house = 大厅（六扇门）；room = 展厅（图表 + 两翼面板）。
   每个展厅相互独立：进展厅后只能「回大厅」再进其他门，展厅内不提供跳到其他展厅的入口。 */
const mode = ref('house')
const roomIdx = computed(() => Math.max(0, VIEWS.findIndex((v) => v.key === view.value)))
const curView = computed(() => VIEWS[roomIdx.value] || VIEWS[0])

function enterRoom(key) {
  view.value = key
  mode.value = 'room'
  syncTabs()
  playRoomIntro()
}
function backToHouse() {
  mode.value = 'house'
}
/* 导览图（itomdev MAP 面板）：大厅模式点房间=传送进门；展厅模式只回大厅 */
const mapOpen = ref(false)
function onMapEnter(key) {
  mapOpen.value = false
  enterRoom(key)
}
function onMapBack() {
  mapOpen.value = false
  backToHouse()
}
/* 切房间时，把两翼标签复位到该房间声明的第一组面板
   （若该房间不含当前标签才重置，减少不必要的切换动画） */
function syncTabs() {
  const v = curView.value
  if (v.left?.length && !v.left.includes(leftTab.value)) leftTab.value = v.left[0]
  if (v.right?.length && !v.right.includes(rightTab.value)) rightTab.value = v.right[0]
}

/* 展厅入场：从大厅推门进来，各区块错峰落位（与大厅的推近动画首尾相接） */
function playRoomIntro() {
  nextTick(() => {
    gsap.from(['.room-nav'], { y: -18, opacity: 0, duration: 0.55, ease: 'power2.out' })
    gsap.from(['.left-panel'], { x: -34, opacity: 0, duration: 0.65, delay: 0.08, ease: 'power2.out' })
    gsap.from(['.right-panel'], { x: 34, opacity: 0, duration: 0.65, delay: 0.16, ease: 'power2.out' })
    gsap.from(['.bottom-bar'], { y: 30, opacity: 0, duration: 0.6, delay: 0.24, ease: 'power2.out' })
  })
}

const centerHint = computed(() => `${curView.value.zh} · ${curView.value.desc} · 顶部可串门或回大厅`)

/* ---------- 左右面板小切换 ---------- */
const leftTab = ref('echo')
const rightTab = ref('story')

/* ---------- 取景地图：点击光点 → 当地影片卡 ---------- */
const loc = ref(null)
const locLoading = ref(false)
const locMovies = ref([])
async function onMapSelect(l) {
  loc.value = l
  locLoading.value = true
  locMovies.value = []
  try {
    const d = await api.mapMovies(l.name, 8)
    locMovies.value = d?.hits || []
  } catch { /* 接口失败时保留空列表，不影响地球交互 */ }
  locLoading.value = false
}

/* 两遍拼接实现无缝循环（内容相同，位移 -50% 时视觉无跳变） */
const chips = computed(() => reviews.value.map((r) => ({
  title: r.title,
  text: r.text,
  tone: r.sentiment === 'negative' ? 'neg' : 'pos',
})))
const loopChips = computed(() => (chips.value.length ? [...chips.value, ...chips.value] : []))

/* ---------- 影评流恒速（用户三次反馈"太快/慢一点"） ----------
   固定秒数在内容量变化时会漂：174 条长文 + 95s 实测 1319px/s（≈110 字/秒），
   快成老虎机。改为测量轨道实际宽度，按恒定像素速度反推 animation-duration：
   45px/s ≈ 3.5 字/秒（比 75px/s 再降四成，中文慢读节奏），内容增减速度恒定。
   注意 keyframes 位移是 -50%（一圈=一份 chips），所以每圈内容宽 = scrollWidth/2。 */
const STREAM_PX_PER_SEC = 45
const streamDur = ref('160s') // CSS 兜底值：JS 测量完成前先用它
watch(loopChips, async () => {
  await nextTick()
  const track = document.querySelector('.stream-track')
  if (!track) return
  const oneLoop = track.scrollWidth / 2 // 位移 -50% = 一份内容的宽度
  if (oneLoop > 0) streamDur.value = `${Math.max(60, Math.round(oneLoop / STREAM_PX_PER_SEC))}s`
}, { flush: 'post' })

/* 中文影评兜底打标：库内中文影评 sentiment 多为 None，
   用高频情感词做轻量判断（负面词优先——负面表达更具体、误判成本更低） */
const ZH_NEG = ['烂', '差劲', '难看', '无聊', '失望', '尴尬', '睡着', '催眠', '糟蹋', '狗血', '退票', '翻车', '吐槽', '莫名其妙', '看不下去', '浪费']
const ZH_POS = ['好看', '精彩', '震撼', '经典', '推荐', '喜欢', '感动', '完美', '神作', '惊喜', '优秀', '封神', '治愈', '牛', '杰作', '不错']
function guessZhTone(text) {
  const t = text || ''
  if (ZH_NEG.some((w) => t.includes(w))) return 'negative'
  if (ZH_POS.some((w) => t.includes(w))) return 'positive'
  return 'positive' // 无明显倾向时按好评计（流式氛围位，不承担判定职责）
}
/** CJK 字符占比：>0.3 视为中文文本（兜底过滤，即使脏数据绕过 lang 也不会漏进流里） */
function cjkRatio(text) {
  const t = (text || '').replace(/\s/g, '')
  if (!t) return 0
  let n = 0
  for (const ch of t) if (ch >= '\u4e00' && ch <= '\u9fff') n++
  return n / t.length
}

onMounted(async () => {
  document.body.classList.add('u-body-lock')
  document.documentElement.classList.add('u-body-lock')
  // 大厅模式：只落顶栏（两翼/底带属于展厅，等推门时再由 playRoomIntro 落位）
  gsap.from(['.top-bar'], { y: -26, opacity: 0, duration: 0.7, ease: 'power2.out' })

  // 深链直达展厅：/screen?room=rank（答辩演示/回归脚本用，避免每次从大厅点进去）
  const q = new URLSearchParams(location.search).get('room')
  if (q && VIEWS.some((v) => v.key === q)) {
    view.value = q
    mode.value = 'room'
    syncTabs()
    playRoomIntro()
  }

  // 星系粒子：4 页并发（单页上限 50）
  const pages = await Promise.all(
    [1, 2, 3, 4].map((page) =>
      api.searchMovies({ size: 50, sort: 'popularity', with_facets: false, page }).catch(() => null),
    ),
  )
  const seen = new Set()
  const all = []
  for (const r of pages) {
    for (const m of r?.hits || []) {
      if (seen.has(m.movie_id)) continue
      seen.add(m.movie_id)
      all.push(m)
    }
  }
  movies.value = all

  // 面板数据
  api.sentimentStats().then((d) => { sentiment.value = d }).catch(() => {})
  api.trends().then((d) => { trends.value = d }).catch(() => {})
  api.matrix().then((d) => { matrix.value = d }).catch(() => {})
  // 票房分析（2026-10-22：替代原「类型竞赛」展厅）
  api.boxOffice(24).then((d) => { boxOffice.value = d }).catch(() => {})
  api.lexicon(40).then((d) => { lexicon.value = d }).catch(() => {})
  // 取景地坐标（3D 地球数据源，Wikidata）
  api.map().then((d) => { mapPoints.value = d?.points || [] }).catch(() => {})
  // 豆瓣联合洞察（评分分歧 / 情感 / 高分 / 预告覆盖 / 类型情感）—— 并入本大屏
  api.doubanInsights().then((d) => { douban.value = d }).catch(() => {})

  // 底部真实影评流（中文化：lang=zh 走索引 lang 字段，库内共 87 条中文影评，
  // 取两页拿全；CJK 比例兜底过滤防脏数据；sentiment 为 None 的中文影评用
  // 内置情感词表前端打标，不再出现英文原文）
  try {
    const pages = await Promise.all(
      [1, 2].map((page) =>
        api.searchReviews({ q: null, lang: 'zh', size: 50, sort: 'relevance', with_facets: false, page }).catch(() => null),
      ),
    )
    const all = []
    for (const r of pages) for (const h of r?.hits || []) all.push(h)
    reviews.value = all
      .filter((r) => cjkRatio(r.text) > 0.3)
      .map((r) => ({
        title: (r.movie_title || '').trim(),
        text: (r.text || '').replace(/[*_>#`]+/g, '').replace(/\s+/g, ' ').trim().slice(0, 48) || '（空文本）',
        sentiment: r.sentiment || guessZhTone(r.text),
      }))
  } catch { /* 影评流不可用时静默降级，不影响大屏其余模块 */ }
})

onBeforeUnmount(() => {
  document.body.classList.remove('u-body-lock')
  document.documentElement.classList.remove('u-body-lock')
})

function toggleFs() {
  if (document.fullscreenElement) document.exitFullscreen()
  else root.value?.requestFullscreen?.().catch(() => {})
}
</script>

<style scoped>
/* 面板内内容需要撑满高度 */
.panel-scroll > :deep(*) { height: 100%; }

/* 大厅层：盖在星系 3D 之上、HUD 之下（顶栏靠 DOM 顺序压在它上面） */
.house-layer { z-index: 2; }

/* ---------- 馆内导览条（房间模式顶部） ---------- */
.room-nav {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  /* 允许换行：屏幕变窄时导览条会被挤出舞台区（stage-dock 左右各让 388px） */
  flex-wrap: wrap;
  row-gap: 6px;
  gap: 10px;
  margin-bottom: 12px;
  padding: 6px 12px;
  background: rgba(255, 253, 247, 0.92);
  border: 1.4px solid rgba(107, 78, 46, 0.32);
  border-radius: 26px;
  box-shadow: 0 6px 18px rgba(74, 40, 20, 0.14);
  backdrop-filter: blur(6px);
}
.room-nav button {
  font-family: inherit;
  cursor: pointer;
  border-radius: 20px;
  border: 1.2px solid rgba(107, 78, 46, 0.34);
  background: rgba(255, 253, 247, 0.9);
  color: #6B4E2E;
  transition: background 0.2s ease, color 0.2s ease, transform 0.16s ease;
}
.room-nav button:hover { background: #8B4513; color: #FFF6E9; transform: translateY(-1px); }

/* ★ 返回按钮：暖白纸面上必须高对比，否则看不见（用户反馈"进展厅没返回按钮"实为白底白字） */
.room-nav .room-nav__back {
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #FFF6E9;
  background: linear-gradient(160deg, #A0522D, #8B4513);
  border: 1.4px solid rgba(255, 246, 233, 0.55);
  box-shadow: 0 3px 10px rgba(139, 69, 19, 0.38);
}
/* ★ 返回按钮：大号 + 高对比 + 手绘抖边硬阴影（暖白纸上绝不可能看不见；
   用户 2026-10-22 第三次反馈"看不到返回按钮"→ 尺寸/边框/阴影全线加强） */
.room-nav .room-nav__back {
  padding: 10px 22px;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #FFF6E9;
  background: linear-gradient(160deg, #A0522D, #8B4513);
  border: 2.2px solid #5C4326;
  border-radius: 255px 16px 225px 16px / 16px 225px 16px 255px;
  box-shadow: 0 3px 10px rgba(139, 69, 19, 0.38), 4px 4px 0 rgba(74, 40, 20, 0.3);
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.2s ease;
}
.room-nav .room-nav__back:hover {
  background: linear-gradient(160deg, #B5651D, #A0522D);
  color: #FFF6E9;
  transform: translate(2px, 2px);
  box-shadow: 0 2px 6px rgba(139, 69, 19, 0.38), 1px 1px 0 rgba(74, 40, 20, 0.35);
}
.room-nav .room-nav__back:active {
  transform: translate(4px, 4px);
  box-shadow: 0 1px 3px rgba(139, 69, 19, 0.38);
}

/* 导览图圆钮（手绘纸质小圆牌，itomdev nav-btn 位） */
.room-nav__map {
  flex: none;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  cursor: pointer;
  background: #FFFDF7;
  border: 2px solid #3A2E20;
  border-radius: 16px 240px 14px 250px / 250px 14px 240px 16px;
  box-shadow: 3px 3px 0 rgba(74, 40, 20, 0.25);
  transition: transform 0.16s ease, background 0.2s ease, box-shadow 0.16s ease;
}
.room-nav__map svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: #4A2E16;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.room-nav__map:hover {
  background: linear-gradient(160deg, #FFE9C9, #FFD9A0);
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(74, 40, 20, 0.3);
}

/* 大厅悬浮导览图按钮（顶栏左下常驻，进大厅就能看到"馆内地图"入口） */
.house-map-btn {
  position: absolute;
  top: 84px;
  left: 24px;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px 9px 14px;
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #FFF6E9;
  background: linear-gradient(160deg, #A0522D, #8B4513);
  border: 2.2px solid #5C4326;
  border-radius: 255px 16px 225px 16px / 16px 225px 16px 255px;
  box-shadow: 0 4px 12px rgba(139, 69, 19, 0.34), 4px 4px 0 rgba(74, 40, 20, 0.28);
  cursor: pointer;
  transition: transform 0.16s ease, background 0.2s ease, box-shadow 0.16s ease;
}
.house-map-btn svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.house-map-btn:hover {
  background: linear-gradient(160deg, #B5651D, #A0522D);
  transform: translate(2px, 2px);
  box-shadow: 0 2px 8px rgba(139, 69, 19, 0.34), 1px 1px 0 rgba(74, 40, 20, 0.32);
}
@media (max-width: 900px) {
  .house-map-btn { top: 78px; left: 14px; padding: 8px 14px 8px 11px; font-size: 12.5px; }
}

.room-nav__plate { display: flex; align-items: baseline; gap: 6px; white-space: nowrap; }
.room-nav__icon { font-size: 15px; font-style: normal; }
.room-nav__plate b { font-size: 14.5px; font-weight: 800; color: #4A2E16; letter-spacing: 0.06em; }
.room-nav__plate span { font-size: 11px; color: var(--u-text-2, #7D6B52); letter-spacing: 0.05em; }

.room-nav__go { display: flex; gap: 5px; }
.room-nav__go button { padding: 4px 10px; font-size: 11.5px; }

.room-nav__doors { display: flex; gap: 4px; padding-left: 4px; margin-left: 2px; border-left: 1px solid rgba(107, 78, 46, 0.22); }
.room-nav__door {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  font-size: 13px;
  line-height: 1;
  opacity: 0.6;
}
.room-nav__door.is-on {
  opacity: 1;
  background: linear-gradient(160deg, #A0522D, #8B4513);
  border-color: #6B4E2E;
  color: #FFF6E9;
  box-shadow: 0 2px 6px rgba(139, 69, 19, 0.32);
}
.room-nav__door.is-on:hover { background: linear-gradient(160deg, #A0522D, #8B4513); }

/* 1280 左右舞台区只有 584px，全量导览条会换行把面板挤矮（实测 78px 两行）→ 收起次要项 */
@media (max-width: 1360px) {
  .room-nav__plate span, .room-nav__go { display: none; }
}

/* GlobeMapPanel 原为 /analytics 编写，复用 space.css 的变量名；
   这里把 --sp-* 映射到大屏色板，子组件内的 var() 沿继承链自动解析 */
.dashboard-container {
  --sp-cyan: var(--u-orange);
  --sp-gold: var(--u-gold);
  --sp-text-2: var(--u-text-2);
  --sp-font-tech: var(--u-font-tech);
}
/* 地球面板融入大屏舞台：去掉自带深底/切角/内边框（stage-panel 已提供）。
   2026-10-19 浅色版：舞台是暖白纸，这里给一圈极淡的暖晕衬托球体 */
:deep(.globe-stage) {
  min-height: 0;
  background: radial-gradient(ellipse 120% 90% at 50% 40%, rgba(255, 253, 247, 0.55), rgba(240, 232, 216, 0.3) 62%, transparent);
  clip-path: none;
}
:deep(.globe-stage::before) { display: none; }
</style>
