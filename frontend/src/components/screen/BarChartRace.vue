<template>
  <div class="race">
    <!-- 头部：标题 + 播放控制 -->
    <div class="race__head">
      <div class="race__head-l">
        <i class="race__head-bar" />
        <span class="race__head-zh">类型竞赛</span>
        <span class="race__head-en">每 1.2 秒一个年代 · 从 2020 年代回溯</span>
      </div>
      <div class="race__ctrl">
        <button class="race__btn" type="button" @click="restart" title="从头播放">↺</button>
        <button class="race__btn race__btn--main" type="button" @click="playing = !playing">
          {{ playing ? '❚❚ 暂停' : '▶ 播放' }}
        </button>
      </div>
    </div>

    <!-- 主体：左图表 + 右上巨大年代数字 -->
    <div class="race__body">
      <div ref="el" class="race__chart" />
      <div class="race__era">
        <span :key="`${idx}-${eraLabel}`" class="race__era-num">{{ eraLabel }}</span>
        <span class="race__era-s">年代</span>
      </div>
      <p v-if="!frames.length" class="race__empty">暂无矩阵数据</p>
    </div>

    <!-- 底部年代刻度：当前帧高亮，可点击跳帧 -->
    <div class="race__dots">
      <button
        v-for="(f, i) in frames"
        :key="f.decade"
        class="race__dot"
        :class="{ 'is-on': i === idx }"
        type="button"
        :title="`${f.decade} 年代`"
        @click="idx = i"
      >
        <span class="race__dot-num">{{ String(f.decade).slice(2) }}</span>
        <i />
      </button>
    </div>
  </div>
</template>

<script setup>
// ============================================================
// 中央舞台 · 类型竞赛（Flourish Bar Chart Race 的深空 HUD 版）
// ------------------------------------------------------------
// 数据：GET /insights/matrix（类型×年代影片数矩阵，ES 聚合实时计算）
// 每 1.2s 推进一步年代，Top 8 类型横向条形带 realtimeSort 换位动画；
// 右上角巨大年代数字（Orbitron）随帧弹入；底部刻度可点击跳帧。
// 复用：ECharts 原生 bar + realtimeSort（ECharts 5 官方竞赛图方案）。
// ============================================================
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useChart, U } from './useChart.js'

const props = defineProps({
  matrix: { type: Object, default: null },
})

const playing = ref(true)
const idx = ref(0)

/* 把矩阵摊成"一帧一年代"：每帧 = 该年代 Top 8 类型（按影片数）。
   ★ 过滤无影片的年代（1930s-1960s 库内几乎没有片）：竞赛图一上来
     连着几帧空屏，用户会以为图表坏了。从第一个有数据的年代播起。 */
const frames = computed(() => {
  const rows = props.matrix?.rows || []
  const decades = props.matrix?.decades || []
  if (!rows.length || !decades.length) return []
  return decades
    .map((d) => {
      const list = rows
        .map((r) => {
          const cell = (r.cells || []).find((c) => c.decade === d)
          return { genre: r.genre, movies: cell?.movies || 0 }
        })
        .filter((x) => x.movies > 0)
        .sort((a, b) => b.movies - a.movies)
        .slice(0, 8)
        .map((x, i) => ({ ...x, rank: i }))
      return { decade: d, list }
    })
    .filter((f) => f.list.length > 0)
})

const eraLabel = computed(() => frames.value[idx.value]?.decade ?? '—')

/* 全局统一尺度：x 轴上限取所有年代的最大影片数。
   ★ 不能用 'dataMax' —— 那样 1970s 的 2 部影片也满格、2020s 的 108 部也满格，
     条形长度失去可比，"越拍越多"的竞赛叙事就没了。 */
const globalMax = computed(() => {
  const all = frames.value.flatMap((f) => f.list.map((x) => x.movies))
  return all.length ? Math.max(...all) * 1.04 : 10
})

/* 条形配色（2026-10-19 增彩）：榜首亮暖金，随后金→橙→青→天蓝→紫渐弱，
   整体从"金蓝双色"扩为五色彩虹，深蓝底上也跳得出来 */
const RANK_COLORS = ['#D9903A', '#C2410C', '#B45309', '#0F766E', '#0369A1', '#A78BFA', '#8FA9C9', '#7A86A0']

function buildOption() {
  const frame = frames.value[idx.value]
  return {
    grid: { left: 4, right: 52, top: 6, bottom: 2, containLabel: true },
    xAxis: { type: 'value', show: false, max: globalMax.value },
    yAxis: {
      type: 'category',
      inverse: true,
      data: frame ? frame.list.map((x) => x.genre) : [],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#4A3C2A',
        fontFamily: U.cn,
        fontSize: 12.5,
        fontWeight: 600,
        margin: 12,
      },
    },
    series: [{
      type: 'bar',
      realtimeSort: true,
      showBackground: true,
      backgroundStyle: { color: "rgba(120, 90, 50, 0.08)", borderRadius: [0, 3, 3, 0] },
      barWidth: 13,
      itemStyle: { borderRadius: [0, 3, 3, 0] },
      label: {
        show: true,
        position: 'right',
        distance: 6,
        color: '#D9903A',
        fontFamily: U.tech,
        fontSize: 12.5,
        fontWeight: 700,
      },
      data: frame ? frame.list.map((x) => ({
        value: x.movies,
        itemStyle: { color: RANK_COLORS[x.rank] || RANK_COLORS[RANK_COLORS.length - 1] },
      })) : [],
      animationDuration: 900,
      animationDurationUpdate: 1300,
      animationEasingUpdate: 'cubicOut',
    }],
  }
}

/* option 走 computed：帧切换 / 数据迟到 都靠 watch 补绘 */
const option = computed(buildOption)
const { el, set } = useChart(() => option.value)
watch(option, (o) => set(o))

let timer = null
onMounted(() => {
  // 倒序回溯：从数据最壮的 2020s 播回 1970s —— 切进来第一眼就是
  // 满屏长条（正序的话头四帧全是 1-3 部的稀疏短条，像图表坏了）。
  // 叙事也成立："从当下回溯，看类型影片的半世纪生长"。
  timer = setInterval(() => {
    if (!playing.value || frames.value.length < 2) return
    idx.value = (idx.value - 1 + frames.value.length) % frames.value.length
  }, 1200)
})
onBeforeUnmount(() => clearInterval(timer))

function restart() {
  idx.value = 0
  playing.value = true
}
</script>

<style scoped>
.race { display: flex; flex-direction: column; height: 100%; min-height: 0; }

.race__head { flex: none; display: flex; align-items: center; justify-content: space-between; }
.race__head-l { display: flex; align-items: center; gap: 8px; }
.race__head-bar { width: 3px; height: 13px; background: linear-gradient(to bottom, var(--u-orange), transparent); box-shadow: 0 0 8px rgba(194, 65, 12, 0.4); }
.race__head-zh { font-size: 13px; font-weight: 700; letter-spacing: 1.5px; color: var(--u-text); }
.race__head-en { font-family: var(--u-font-tech); font-size: 9px; letter-spacing: 1.4px; color: rgba(125, 107, 82, 0.9); text-transform: uppercase; }

.race__ctrl { display: flex; gap: 6px; }
.race__btn {
  height: 24px; padding: 0 10px;
  font-family: var(--u-font-tech); font-size: 10px; letter-spacing: 1px;
  color: var(--u-text-2);
  background: rgba(201, 169, 110, 0.06);
  border: 1px solid rgba(194, 65, 12, 0.3);
  clip-path: var(--u-poly); --u-cut: 6px;
  cursor: pointer;
  transition: color .2s ease, background .2s ease;
}
.race__btn:hover { color: #FFF8EC; background: var(--u-orange-deep); }
.race__btn--main { min-width: 62px; }

.race__body { position: relative; flex: 1; min-height: 0; margin-top: 6px; }
.race__chart { position: absolute; inset: 0; }
.race__empty {
  position: absolute; inset: 0;
  display: grid; place-items: center;
  font-size: 12px; color: var(--u-text-2);
}

/* 巨大年代数字：Flourish 竞赛图的标志性元素 */
.race__era {
  position: absolute; right: 2px; top: -6px;
  display: flex; align-items: baseline;
  pointer-events: none;
}
.race__era-num {
  font-family: var(--u-font-tech);
  font-size: 64px; font-weight: 700; line-height: 1;
  letter-spacing: 1px;
  color: rgba(58, 46, 32, 0.92);
  text-shadow: 0 0 26px rgba(201, 169, 110, 0.35);
  animation: u-era-in .7s cubic-bezier(0.16, 0.84, 0.44, 1);
}
.race__era-s {
  font-family: var(--u-font-tech);
  font-size: 22px; font-weight: 600;
  color: var(--u-orange);
  margin-left: 2px;
}
@keyframes u-era-in {
  from { opacity: 0; transform: translateY(10px) scale(0.94); }
  to { opacity: 1; transform: none; }
}

/* 底部年代刻度 */
.race__dots { flex: none; display: flex; gap: 4px; margin-top: 8px; }
.race__dot {
  flex: 1; position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 4px 0 0;
  background: none; border: none; cursor: pointer;
  font-family: var(--u-font-tech); font-size: 9px; letter-spacing: .5px;
  color: rgba(125, 107, 82, 0.8);
  transition: color .2s ease;
}
.race__dot i { width: 100%; height: 2px; background: rgba(125, 107, 82, 0.28); transition: background .3s ease, box-shadow .3s ease; }
.race__dot:hover { color: var(--u-text); }
.race__dot.is-on { color: var(--u-orange); }
.race__dot.is-on i { background: var(--u-orange); box-shadow: 0 0 8px rgba(194, 65, 12, 0.45); }
</style>
