<template>
  <!--
    ============================================================
    口碑分歧展厅 · 观众评分分化榜（右翼面板）· A24 影片展
    ------------------------------------------------------------
    用真实电影数据复刻 A24 的"概念化影片展"：
    · 主视觉 = 漂浮的**海报圆盘**（真实 TMDB 海报，CD 质感：盘芯孔 + 边缘高光）
      鼠标移上去 = 3D 倾斜（parallax），平时轻轻上下浮动，像活着的碟片
    · 编辑式 credits：DIRECTED BY / YEAR / 评分，细横线分隔（A24 档案表）
    · 媒体星级 ★★★★★（由 vote_average 折算，支持半星）
    · 两条真实引文 = 嘶吼式衬线大字 + 引号（A24 pull-quote），好评橙 / 差评青
    · 底部"圆盘索引"：前十部分歧影片的小圆盘，点选切换主视觉（榜单联动保留）
    数据全部来自 /insights/polarizing（评分标准差排名 + 真实引文）。
    ============================================================
  -->
  <div class="pb">
    <header class="pb__head">
      <span class="pb__eyebrow">RATING SPLIT · 同一部片，有人打满分有人打最低分</span>
      <span class="pb__cnt">{{ items.length }} 部吵得最凶</span>
    </header>

    <div class="pb__scroll">
      <Transition name="pb-swap" mode="out-in">
        <div v-if="cur" :key="cur.movie_id" class="pb__feat">
          <!-- 片名：A24 式大衬线标题（影片展的主角） -->
          <div class="pb__film">{{ cur.title }}<small v-if="cur.title_en"> · {{ cur.title_en }}</small></div>

          <!-- 海报圆盘：真实海报 + CD 质感（盘芯孔 + 边缘高光） -->
          <div
            class="disc"
            :style="discStyle"
            @pointermove="onTilt"
            @pointerleave="onUntilt"
          >
            <div class="disc__face" :style="posterBg(cur)">
              <span v-if="!cur.poster_url" class="disc__label">{{ cur.title }}</span>
            </div>
            <i class="disc__hole" />
            <i class="disc__shine" />
          </div>

          <!-- 编辑式 credits（A24 档案表） -->
          <div class="credits">
            <div class="cr"><span class="cr__k">DIRECTED BY</span><span class="cr__v">{{ cur.director || '—' }}</span></div>
            <div class="cr"><span class="cr__k">YEAR</span><span class="cr__v">{{ cur.year || '—' }}</span></div>
            <div class="cr"><span class="cr__k">评分</span><span class="cr__v">{{ fmt(cur.vote_average) }}</span></div>
          </div>

          <!-- 媒体星级（由 vote_average/2 折算，支持半星） -->
          <div class="stars" :aria-label="`评分 ${fmt(cur.vote_average)} / 10`">
            <i v-for="(s, i) in stars" :key="i" class="star" :class="s">★</i>
            <span class="stars__num">{{ fmt(cur.vote_average) }}</span>
          </div>

          <!-- 分化指数：本榜的分析指标（标准差越大越两极） -->
          <div class="divind">
            <span class="divind__k">分化指数</span>
            <span class="divind__v">{{ fmt(cur.std_dev) }}</span>
            <span class="divind__hint">· {{ cur.review_count }} 条评价</span>
          </div>

          <!-- 两条真实引文（A24 嘶吼式衬线） -->
          <figure v-if="cur.pos_quote" class="quote quote--pos">
            <blockquote>{{ cur.pos_quote.text }}</blockquote>
            <figcaption>好评 · 该观众打 {{ scoreOf(cur.pos_quote.rating) }} 分</figcaption>
          </figure>
          <figure v-if="cur.neg_quote" class="quote quote--neg">
            <blockquote>{{ cur.neg_quote.text }}</blockquote>
            <figcaption>差评 · 该观众打 {{ scoreOf(cur.neg_quote.rating) }} 分</figcaption>
          </figure>
          <p v-if="!cur.pos_quote && !cur.neg_quote" class="pb__empty">该片暂无足够长的真实引文</p>
        </div>
      </Transition>
    </div>

    <!-- 圆盘索引：前十部分歧影片，点选切换主视觉 -->
    <div class="idx" role="tablist" aria-label="分歧影片索引">
      <button
        v-for="(it, i) in items"
        :key="it.movie_id"
        type="button"
        class="idx__d"
        :class="{ on: i === sel }"
        :style="thumbBg(it)"
        :title="it.title"
        :aria-selected="i === sel"
        @click="sel = i"
      >
        <span v-if="!it.poster_url" class="idx__no">{{ i + 1 }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
// ============================================================
// 观众评分分化 · A24 影片展（数据 /insights/polarizing）
// 圆盘 3D 倾斜：pointermove 写 --rx/--ry，transform 由 CSS 消费（与项目海报扇同款手法）
// ============================================================
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  polarizing: { type: Object, default: null },
})

const items = computed(() => props.polarizing?.items || [])
const sel = ref(0)
const cur = computed(() => items.value[sel.value] || null)

const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toFixed(1))
const scoreOf = (r) => (r === null || r === undefined ? '?' : Math.round(Number(r)))

// 媒体星级：vote_average(/10) → /5，支持半星
const stars = computed(() => {
  const v = (cur.value?.vote_average || 0) / 2
  return Array.from({ length: 5 }, (_, i) => {
    if (v >= i + 1) return 'full'
    if (v >= i + 0.5) return 'half'
    return 'empty'
  })
})

// 真实海报圆盘背景
function posterBg(it) {
  return it?.poster_url
    ? { backgroundImage: `url("${it.poster_url}")`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : {}
}
function thumbBg(it) {
  return it?.poster_url
    ? { backgroundImage: `url("${it.poster_url}")`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : {}
}

// 圆盘 3D 倾斜
const tilt = reactive({ x: 0, y: 0 })
const discStyle = computed(() => ({ '--rx': tilt.x + 'deg', '--ry': tilt.y + 'deg' }))
function onTilt(e) {
  const r = e.currentTarget.getBoundingClientRect()
  const px = (e.clientX - r.left) / r.width - 0.5
  const py = (e.clientY - r.top) / r.height - 0.5
  tilt.y = (px * 16).toFixed(2)   // 绕 Y 轴
  tilt.x = (-py * 14).toFixed(2)  // 绕 X 轴
}
function onUntilt() {
  tilt.x = 0
  tilt.y = 0
}
</script>

<style scoped>
.pb { display: flex; flex-direction: column; height: 100%; min-height: 0; }

.pb__head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding: 2px 4px 9px; }
.pb__eyebrow {
  font-family: var(--u-font-tech); font-size: 9px; letter-spacing: .14em;
  color: var(--u-text-2); line-height: 1.3; text-transform: uppercase;
}
.pb__cnt { font-size: 10.5px; color: var(--u-gold); font-weight: 600; white-space: nowrap; flex: none; }

.pb__scroll { flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; padding: 2px 4px 6px; }

/* ---------- 主视觉：海报圆盘 ---------- */
.pb__feat { display: flex; flex-direction: column; align-items: center; text-align: center; }
.pb__film {
  font-family: "Kaiti SC", KaiTi, STKaiti, serif;
  font-size: 19px; font-weight: 700; line-height: 1.2; color: var(--u-text);
  margin: 2px 0 8px; max-width: 100%;
}
.pb__film small { display: block; font-family: var(--u-font-tech); font-size: 9px; letter-spacing: .12em; color: var(--u-text-2); margin-top: 2px; text-transform: uppercase; }
.disc {
  position: relative;
  width: 150px; height: 150px;
  margin: 4px 0 11px;
  border-radius: 50%;
  perspective: 700px;
  transform: rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg));
  transition: transform .2s ease;
  cursor: pointer;
  flex: none;
}
.disc__face {
  position: absolute; inset: 0;
  border-radius: 50%;
  background-color: #efe7d6;
  border: 2px solid rgba(74, 40, 20, .35);
  box-shadow: inset 0 0 0 6px rgba(255, 253, 247, .25),
              inset 0 0 22px rgba(74, 40, 20, .28),
              0 10px 24px rgba(74, 40, 20, .28);
  overflow: hidden;
  animation: disc-bob 5.5s ease-in-out infinite;
}
@keyframes disc-bob {
  0%, 100% { transform: translateY(0) rotate(-.6deg); }
  50% { transform: translateY(-7px) rotate(.6deg); }
}
.disc__label {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
  font-family: "Kaiti SC", KaiTi, STKaiti, serif;
  font-size: 15px; font-weight: 700; line-height: 1.25; color: #4A2E16;
}
/* 盘芯孔 */
.disc__hole {
  position: absolute; left: 50%; top: 50%;
  width: 26px; height: 26px; transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(circle at 40% 38%, #FBF6EC, #E7DCC6 70%, #D8C9AC);
  box-shadow: 0 0 0 4px rgba(255, 253, 247, .35), inset 0 1px 3px rgba(74,40,20,.4);
  pointer-events: none;
}
/* 边缘高光（碟片反光，不用 mix-blend-mode，避免手绘纸层合成问题） */
.disc__shine {
  position: absolute; inset: 0; border-radius: 50%; pointer-events: none;
  background: linear-gradient(125deg, rgba(255,255,255,.45) 0%, rgba(255,255,255,0) 30%, rgba(255,255,255,0) 68%, rgba(255,255,255,.2) 100%);
}
.disc:hover .disc__face { animation-play-state: paused; }

/* ---------- 编辑式 credits ---------- */
.credits { width: 100%; max-width: 250px; margin: 0 auto 8px; }
.cr {
  display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  padding: 4px 2px;
  border-bottom: 1px solid rgba(154, 96, 40, .22);
}
.cr:first-child { border-top: 1px solid rgba(154, 96, 40, .22); }
.cr__k { font-family: var(--u-font-tech); font-size: 8.5px; letter-spacing: .18em; color: var(--u-text-2); white-space: nowrap; }
.cr__v { font-size: 12px; font-weight: 700; color: var(--u-text); text-align: right; }

/* ---------- 媒体星级 ---------- */
.stars { display: flex; align-items: center; gap: 3px; margin: 2px 0 9px; }
.star { font-style: normal; font-size: 14px; line-height: 1; color: rgba(154, 96, 40, .28); }
.star.full { color: var(--u-gold); }
.star.half {
  color: transparent;
  background: linear-gradient(90deg, var(--u-gold) 50%, rgba(154, 96, 40, .28) 50%);
  -webkit-background-clip: text; background-clip: text;
}
.stars__num { font-size: 11px; font-weight: 700; color: var(--u-text-2); margin-left: 4px; }

/* ---------- 分化指数 ---------- */
.divind {
  display: inline-flex; align-items: baseline; gap: 5px;
  padding: 3px 10px; margin-bottom: 12px;
  border: 1px solid rgba(194, 65, 12, .35); border-radius: 999px;
  background: rgba(194, 65, 12, .06);
}
.divind__k { font-family: var(--u-font-tech); font-size: 8.5px; letter-spacing: .16em; color: var(--u-orange); }
.divind__v { font-family: "Kaiti SC", KaiTi, STKaiti, serif; font-size: 16px; font-weight: 700; color: var(--u-orange); line-height: 1; }
.divind__hint { font-size: 9.5px; color: var(--u-text-2); }

/* ---------- 嘶吼式引文（A24 pull-quote） ---------- */
.quote { margin: 0 0 14px; text-align: left; }
.quote blockquote {
  margin: 0;
  font-family: "Kaiti SC", KaiTi, STKaiti, "Songti SC", serif;
  font-weight: 700;
  font-size: 14.5px;
  line-height: 1.5;
  color: #3A2E20;
  padding: 4px 0 4px 20px;
  position: relative;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.quote blockquote::before {
  content: '“';
  position: absolute; left: -2px; top: -4px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 34px; line-height: 1;
}
.quote--pos blockquote::before { color: var(--u-orange); }
.quote--neg blockquote::before { color: var(--u-cyan); }
.quote figcaption {
  margin-top: 5px; padding-left: 20px;
  font-family: var(--u-font-tech); font-size: 8.5px; letter-spacing: .12em;
  text-transform: uppercase;
}
.quote--pos figcaption { color: var(--u-orange); }
.quote--neg figcaption { color: var(--u-cyan); }

.pb__empty { font-size: 11.5px; color: var(--u-text-2); text-align: center; padding: 18px 4px; }

/* ---------- 圆盘索引 ---------- */
.idx {
  flex: none;
  display: flex; gap: 7px; overflow-x: auto; padding: 9px 4px 4px;
  border-top: 1px solid rgba(154, 96, 40, .2);
  scrollbar-width: thin;
}
.idx__d {
  flex: 0 0 auto;
  width: 40px; height: 40px; border-radius: 50%;
  border: 2px solid transparent; background-color: #efe7d6;
  background-size: cover; background-position: center;
  cursor: pointer; padding: 0; position: relative;
  box-shadow: 0 2px 5px rgba(74, 40, 20, .2);
  transition: transform .15s ease, border-color .15s ease;
}
.idx__d:hover { transform: translateY(-3px); }
.idx__d.on { border-color: var(--u-orange); transform: translateY(-3px) scale(1.06); }
.idx__no {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-family: "Kaiti SC", KaiTi, serif; font-size: 13px; font-weight: 700; color: #4A2E16;
}

/* 切换交叉淡入 */
.pb-swap-enter-active, .pb-swap-leave-active { transition: opacity .26s ease, transform .26s ease; }
.pb-swap-enter-from { opacity: 0; transform: translateY(10px); }
.pb-swap-leave-to { opacity: 0; transform: translateY(-6px); }

@media (prefers-reduced-motion: reduce) {
  .disc__face { animation: none; }
  .pb-swap-enter-active, .pb-swap-leave-active { transition: none; }
}
</style>
