<script setup>
// ============================================================
// 观影足迹地图 —— Leaflet + OSM 底图。
//
// 信息窗点开标记后，按需拉取该地点的影片列表（/fun/map/movies）：
// 小海报 + 片名 + 年份 + 评分，最多 10 部可滚动，点击进详情页。
// 为什么不并进地图接口：全量点位一次拉完，每点再挂 10 部影片
// 响应翻几倍，而用户同一时刻只点开一个标记。
//
// 标记用 circleMarker 而不是默认 marker：默认图标要引图片资源，
// 且 Vite 打包后图标路径经常丢，circleMarker 是纯 SVG，零资源依赖。
// ============================================================
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '../api'
import { toast } from '../composables/useToast'

const router = useRouter()
const mapEl = ref(null)
const panelOpen = ref(true)
let map = null
let layer = null

const points = ref([])
const note = ref('')
const skipped = ref(0)
const loading = ref(true)
const kindFilter = ref('all')     // all / filming / narrative
const minMovies = ref(1)
const kw = ref('')

const filtered = computed(() =>
  points.value.filter((p) => {
    if (kindFilter.value !== 'all' && p.kind !== kindFilter.value) return false
    if ((p.movies || 0) < minMovies.value) return false
    if (kw.value && !String(p.name || '').includes(kw.value.trim())) return false
    return true
  }),
)

// 地点名候选（搜索框下拉提示：用户不用猜库里有哪些地名）
const nameHints = computed(() => points.value.map((p) => p.name))

const KIND_COLOR = { filming: '#d2691e', narrative: '#3b7dd8', country: '#8c8c8c' }

function kindLabel(k) {
  return { filming: '拍摄地', narrative: '故事发生地', country: '制作国家' }[k] || '地点'
}

// ---- 信息窗：按需拉影片列表 ----
const popupMovies = ref([])        // 当前弹窗的影片
const popupTotal = ref(0)
const popupLoading = ref(false)
const popupName = ref('')

async function openLocationPopup(p, marker) {
  popupName.value = p.name
  popupMovies.value = []
  popupTotal.value = p.movies || 0
  popupLoading.value = true
  marker.bindPopup(popupHtml(), { maxWidth: 300 }).openPopup()
  try {
    const data = await api.mapMovies(p.name, 10)
    popupMovies.value = data?.hits || []
    popupTotal.value = data?.total ?? popupTotal.value
  } catch {
    /* 拉取失败时保留地点概览，不弹 toast 打断地图操作 */
  } finally {
    popupLoading.value = false
    // 异步回来时弹窗可能已被用户关掉：只在还开着同一个地点时刷新内容
    if (popupName.value === p.name) marker.setPopupContent(popupHtml())
  }
}

function popupHtml() {
  const rows = popupMovies.value.map((m) => `
    <button class="mappop__movie" data-mid="${m.movie_id}">
      <img class="mappop__poster" src="${m.poster_url || ''}" alt="" loading="lazy"
           onerror="this.style.visibility='hidden'" />
      <span class="mappop__minfo">
        <span class="mappop__mtitle">${m.title_zh || m.title || m.movie_id}</span>
        <span class="mappop__mmeta">${m.release_date ? m.release_date.slice(0, 4) : '—'} · ★ ${m.rating != null ? m.rating.toFixed(1) : '—'}</span>
      </span>
    </button>`).join('')
  const more = popupTotal.value > popupMovies.value.length
    ? `<div class="mappop__more">还有 ${popupTotal.value - popupMovies.value.length} 部，去检索页看全部</div>` : ''
  const body = popupLoading.value
    ? '<div class="mappop__loading">正在找这个地点的影片…</div>'
    : rows || '<div class="mappop__loading">这个地点暂未关联到影片</div>'
  return `
    <div class="mappop">
      <div class="mappop__name">${popupName.value}</div>
      <div class="mappop__list">${body}</div>
      ${more}
    </div>`
}

// 事件委托：弹窗里点影片 → 跳详情（innerHTML 生成的节点没法直接绑 Vue 事件）
function onPopupClick(e) {
  const btn = e.target.closest?.('.mappop__movie')
  if (!btn) return
  const mid = btn.getAttribute('data-mid')
  if (mid) router.push(`/movie/${encodeURIComponent(mid)}`)
}

function drawMarkers() {
  if (!map) return
  if (layer) { map.removeLayer(layer); layer = null }
  layer = L.layerGroup().addTo(map)

  filtered.value.forEach((p) => {
    const color = KIND_COLOR[p.kind] || KIND_COLOR.country
    const c = L.circleMarker([p.lat, p.lon], {
      radius: 6,                 // 清单要求直径 12px → 半径 6
      color: '#fff',
      weight: 2,
      fillColor: color,
      fillOpacity: 0.95,
    })
    c.bindTooltip(`${p.name}（${p.movies || 0} 部）`, { direction: 'top' })
    c.on('mouseover', () => c.setRadius(9))     // 悬停放大 1.5 倍
    c.on('mouseout', () => c.setRadius(6))
    c.on('click', () => {
      map.flyTo([p.lat, p.lon], 8, { duration: 0.8 })
      openLocationPopup(p, c)
    })
    c.addTo(layer)
  })
}

function randomJump() {
  if (!filtered.value.length) return
  const p = filtered.value[Math.floor(Math.random() * filtered.value.length)]
  map.flyTo([p.lat, p.lon], 8, { duration: 1 })
  // 飞完直接弹信息窗：与点击标记同一套内容（异步拉影片列表）
  setTimeout(() => {
    popupName.value = p.name
    popupMovies.value = []
    popupTotal.value = p.movies || 0
    popupLoading.value = true
    const pop = L.popup({ maxWidth: 300 })
      .setLatLng([p.lat, p.lon])
      .setContent(popupHtml())
      .openOn(map)
    api.mapMovies(p.name, 10).then((data) => {
      popupMovies.value = data?.hits || []
      popupTotal.value = data?.total ?? popupTotal.value
      popupLoading.value = false
      if (popupName.value === p.name) pop.setContent(popupHtml())
    }).catch(() => { popupLoading.value = false })
  }, 1000)
}

onMounted(async () => {
  map = L.map(mapEl.value, { zoomControl: true, worldCopyJump: true }).setView([38, 25], 3)
  // 底图：原设计用 CartoDB Voyager，但 2025 起要求 API key，改用 OSM 标准 tile（免费无 key）
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map)
  // 弹窗内容是异步拼的 innerHTML，用事件委托接点击（见 onPopupClick）
  map.on('click', onPopupClick)

  try {
    const data = await api.map()
    points.value = data?.points || []
    note.value = data?.note || ''
    skipped.value = data?.skipped_no_coords || 0
  } catch (e) {
    toast.error(e.message)
  } finally {
    loading.value = false
    drawMarkers()
  }
})

onUnmounted(() => { if (map) { map.remove(); map = null } })

watch([kindFilter, minMovies, kw], drawMarkers)
</script>

<template>
  <div class="mapview">
    <!-- 筛选面板（左上，半透明白，可折叠） -->
    <div class="mapfilter" :class="{ 'is-collapsed': !panelOpen }">
      <div class="mapfilter__head">
        <span>筛选</span>
        <button @click="panelOpen = !panelOpen">{{ panelOpen ? '−' : '+' }}</button>
      </div>
      <div v-if="panelOpen" class="mapfilter__body">
        <label class="mf__label">地点类型</label>
        <select v-model="kindFilter" class="select">
          <option value="all">全部</option>
          <option value="filming">拍摄地</option>
          <option value="narrative">故事发生地</option>
        </select>

        <label class="mf__label">最少影片数：{{ minMovies }}</label>
        <input v-model.number="minMovies" type="range" min="1" max="10" class="mf__range" />

        <label class="mf__label">地点名</label>
        <input v-model="kw" class="input" list="map-name-hints" placeholder="如 伦敦、冰岛" />
        <datalist id="map-name-hints">
          <option v-for="n in nameHints" :key="n" :value="n" />
        </datalist>
      </div>
    </div>

    <!-- 随机跳转（右上） -->
    <button class="map-random" @click="randomJump">🎯 随便飞一个地方</button>

    <!-- 图例（右下） -->
    <div class="maplegend">
      <span><i style="background:#d2691e"></i>拍摄地</span>
      <span><i style="background:#3b7dd8"></i>故事发生地</span>
      <span><i style="background:#8c8c8c"></i>制作国家</span>
    </div>

    <div ref="mapEl" class="mapview__canvas"></div>

    <div v-if="loading" class="mapview__loading">正在加载取景地坐标…</div>

    <div class="mapstat">
      共 {{ points.length }} 个地点
      <span v-if="skipped"> · {{ skipped }} 条有地名无坐标（未上图）</span>
      <span v-if="note" class="text-3"> · {{ note }}</span>
    </div>
  </div>
</template>
