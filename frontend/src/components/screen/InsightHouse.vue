<template>
  <!--
    ============================================================
    影评洞察馆 · 大厅（/screen 入口层）—— 复刻 itomdev.com 手绘纸世界 + a24 漂浮光盘
    ------------------------------------------------------------
    用户要求"照两个参考站复刻，不要自己发挥"。据此：
      · itomdev：揉皱纸背景（feTurbulence 折痕 + 纸纹）、黑墨手绘抖动线条
        （feDisplacementMap 让所有描边"抖"起来，告别僵硬 CAD 线 / 廉价 clip-art）、
        蜿蜒虚线路径、六间手绘小屋沿路排布、角落手绘指南针 —— 对应"六间展厅"导航
      · a24：每间房上方一枚**漂浮倾斜 DVD 光盘**（盘芯孔 + 银环 + 缓慢呼吸/浮动），
        悬浮时随鼠标 3D 倾斜 —— 对应"数据页"的 A24 视觉语言
    交互：点小屋 = 朝该屋推近淡出进入展厅（沿用 enter/is-entering）；
          hover = 小屋轻浮 + 光盘放大倾斜；窄屏降级为可滚动竖排，不丢入口。
    全 CSS/SVG，零新依赖。扁平 2D（itomdev 本就是手绘插画，不做 3D 走廊，
    也避开旧版 preserve-3d 命中测试雷）。
    ============================================================
  -->
  <div
    ref="house"
    class="ih"
    :class="{ 'is-entering': entering, 'is-ready': ready }"
    :style="{ '--ex': enterX, '--ey': enterY }"
  >
    <!-- 揉皱纸背景（itomdev 纸感：折痕明暗 + 细噪点） -->
    <div class="ih__paper" aria-hidden="true" />
    <!-- 手绘抖动滤镜定义（全局复用） -->
    <svg class="ih__defs" aria-hidden="true" width="0" height="0">
      <defs>
        <filter id="ihSketch" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.018 0.022" numOctaves="2" seed="7" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>

    <!-- 手绘装饰：云 + 树（黑墨抖动线，纯点缀，不抢导航） -->
    <svg class="ih__cloud" viewBox="0 0 200 70" aria-hidden="true"><path class="sk" d="M20 50c-12 0-20-9-20-18 0-9 8-16 18-16 3-10 14-16 25-16 11 0 20 6 24 15 3-2 8-3 12-3 11 0 19 8 19 18 0 8-6 14-15 15z" /></svg>
    <svg class="ih__tree" viewBox="0 0 90 120" aria-hidden="true">
      <path class="sk" d="M45 118V52" />
      <path class="sk" d="M45 78c-10-4-16-12-18-22M45 66c9-4 15-12 17-22" />
      <path class="sk" d="M45 10c16 0 27 11 27 25 0 5-2 9-5 13 6 3 9 9 9 15 0 11-9 19-21 19-3 0-6-1-9-2-3 1-7 2-11 2-13 0-23-9-23-21 0-8 4-14 11-17-4-4-6-8-6-13 0-12 11-21 27-21z" />
    </svg>

    <div class="ih__inner">
      <!-- ---------- 手绘刊头 ---------- -->
      <header class="ih__masthead">
        <span class="ih__kicker">影评洞察馆 · THE INSIGHT ARCHIVE</span>
        <h1 class="ih__title">把五万条影评，<br />摊开成五间展厅</h1>
        <svg class="ih__rule" viewBox="0 0 260 14" aria-hidden="true"><path class="sk" d="M4 8C40 3 80 12 120 7c40-5 80 4 136-1" /></svg>
        <p class="ih__lede">每一间，都是一种读法。</p>
      </header>

      <!-- ---------- 手绘世界：路径 + 六间小屋 ---------- -->
      <div class="ih__map">
        <!-- 蜿蜒虚线路径（手绘抖动） -->
        <svg class="ih__path" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">
          <path class="sk ih__path-line" d="M140 200C220 270 240 360 300 420S420 120 480 210S580 520 640 430S740 120 800 210S880 360 930 420" />
        </svg>

        <button
          v-for="(r, i) in rooms"
          :key="r.key"
          class="ih__room"
          :class="{ 'is-open': hover === i }"
          type="button"
          :aria-label="`进入${r.zh}展厅`"
          :style="roomPos(i)"
          @pointerenter="hover = i"
          @pointerleave="hover = -1"
          @focus="hover = i"
          @blur="hover = -1"
          @click="enter(r, i, $event)"
        >
          <!-- a24 漂浮倾斜光盘（房顶上方） -->
          <span class="ih__disc" :style="discGrad(r.tint)" aria-hidden="true">
            <i class="ih__disc-hole" />
          </span>
          <!-- 手绘小屋（黑墨抖动线 + 屋顶白牌显示序号） -->
          <span class="ih__house-wrap">
            <svg class="ih__house" viewBox="0 0 120 134" aria-hidden="true">
              <g class="sk ih__house-lines" fill="none" stroke="#2A2118" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 74 20 46 60 20 100 46 100 74" />
                <rect x="20" y="74" width="80" height="42" />
                <rect x="33" y="86" width="19" height="17" />
                <rect x="70" y="86" width="19" height="17" />
                <path d="M53 116 53 93 73 93 73 116" />
                <rect x="33" y="4" width="54" height="17" fill="#FFFDF7" />
              </g>
            </svg>
            <span class="ih__sign-no">{{ String(i + 1).padStart(2, '0') }}</span>
          </span>
          <!-- 文案（HTML，清晰可读） -->
          <span class="ih__cap">
            <b class="ih__zh">{{ r.zh }}</b>
            <span class="ih__desc">{{ r.desc }}</span>
            <span class="ih__go">进入展厅 <i>→</i></span>
          </span>
        </button>
      </div>

      <!-- ---------- 馆长洞察（主编精选，收编进大厅底部流） ---------- -->
      <div class="ih__stories">
        <HallInsights :cards="cards" @enter="$emit('enter', $event)" />
      </div>
    </div>

    <!-- 手绘指南针（角落点缀，itomdev 地图感） -->
    <svg class="ih__compass" viewBox="0 0 100 100" aria-hidden="true">
      <g class="sk" fill="none" stroke="#2A2118" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="50" cy="50" r="34" />
        <path d="M50 16l8 30-8 8-8-8z" fill="#2A2118" />
        <path d="M50 84l-8-30 8-8 8 8z" />
        <path d="M16 50l30-8 8 8-8 8zM84 50l-30 8-8-8 8-8z" />
      </g>
      <text x="50" y="13" text-anchor="middle" class="ih__compass-t">N</text>
    </svg>

    <!-- 纸纹颗粒（叠加在纸上的细噪点） -->
    <div class="ih__grain" aria-hidden="true" />
  </div>
</template>

<script setup>
// ============================================================
// 大厅：只负责"选展厅"。真正的内容在房间（UniverseScreen）里。
// 走进动画：把点击那间小屋的位置写进 --ex/--ey，整屋朝那个点推近并淡出，
// 父级在过渡结束后切到房间视图，观感上就是"穿过那间屋走进去了"。
// ============================================================
import { computed, onMounted, onUnmounted, ref } from 'vue'
import HallInsights from './HallInsights.vue'

const props = defineProps({
  /** 五间展厅：与 UniverseScreen 的 VIEWS 同源 */
  rooms: { type: Array, default: () => [] },
  /** 馆长洞察卡（UniverseScreen 从 /insights/story 取，向下传） */
  cards: { type: Array, default: () => [] },
})

const emit = defineEmits(['enter'])

const house = ref(null)
const ready = ref(false)
const entering = ref(false)
const hover = ref(-1)
const enterX = ref('50%')
const enterY = ref('50%')

// 五间小屋在"手绘地图"上的坐标（与虚线路径节点大致吻合，百分比）
// 底排两间（票房分析 / 年代流向）上提到 ~58–60%，给下方"馆长洞察"卡片留出净空，
// 否则其说明文字会被卡片盖住（1440×900 实测：底排 y=70/72 时说明文字 bottom 越过卡片 top）
const ROOM_POS = [
  { x: 14, y: 33 }, { x: 30, y: 58 }, { x: 48, y: 35 },
  { x: 64, y: 60 }, { x: 80, y: 35 },
]
function roomPos(i) {
  const p = ROOM_POS[i] || { x: 50, y: 50 }
  return { left: p.x + '%', top: p.y + '%' }
}

// a24 漂浮光盘渐变（用房的 tint 色）
function discGrad(tint) {
  return {
    background: `radial-gradient(circle at 36% 32%, ${tint} 0%, ${tint}cc 30%, ${tint}77 55%, ${tint}33 78%, transparent 86%)`,
  }
}

const OPEN_MS = 640 // 推近+淡出的时长，与父级切换时序对齐

function enter(room, i, ev) {
  if (entering.value) return
  // 以这间小屋为中心推近：算出它在大厅里的相对位置
  const el = house.value
  const btn = ev?.currentTarget
  if (el && btn) {
    const hr = el.getBoundingClientRect()
    const br = btn.getBoundingClientRect()
    enterX.value = `${(((br.left + br.width / 2 - hr.left) / hr.width) * 100).toFixed(2)}%`
    enterY.value = `${(((br.top + br.height / 2 - hr.top) / hr.height) * 100).toFixed(2)}%`
  }
  hover.value = i
  entering.value = true
  setTimeout(() => emit('enter', room.key), OPEN_MS - 140)
}

onMounted(() => {
  requestAnimationFrame(() => { ready.value = true })
})
onUnmounted(() => {})

defineExpose({ /** 便于父级在大厅重新挂载时复位 */ reset() { entering.value = false } })
</script>

<style scoped>
.ih {
  --paper: #F4EFE3;
  --paper-2: #ECE4D2;
  --ink: #2A2118;
  --text-2: #6B5B45;
  --gold: #A67C2E;
  --orange: #C2410C;
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--u-font-cn, 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif);
  opacity: 0;
  transform: scale(1.02);
  transition: opacity 0.5s ease, transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}
.ih.is-ready { opacity: 1; transform: scale(1); }

/* 走进去：朝点击的那间小屋推近并淡出 */
.ih.is-entering {
  transform-origin: var(--ex, 50%) var(--ey, 50%);
  transform: scale(2.6);
  opacity: 0;
  transition: transform 0.64s cubic-bezier(0.5, 0, 0.9, 0.4), opacity 0.5s ease 0.12s;
  pointer-events: none;
}

/* ---------- 揉皱纸背景（itomdev 纸感） ---------- */
.ih__paper {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    /* 折痕明暗：几道斜向柔光，模拟纸被揉过的起伏 */
    linear-gradient(118deg, rgba(255, 253, 247, 0.7) 0%, transparent 20%, rgba(120, 100, 70, 0.12) 44%, transparent 60%, rgba(255, 253, 247, 0.55) 100%),
    radial-gradient(58% 48% at 28% 26%, rgba(255, 253, 247, 0.6), transparent 70%),
    radial-gradient(52% 42% at 80% 74%, rgba(120, 100, 70, 0.14), transparent 72%),
    linear-gradient(160deg, #F7F2E6 0%, #EEE6D4 58%, #E4D9C2 100%);
}
/* 揉皱 mottle：低频 turbulence 生成柔和棕调斑驳，叠出"被揉过"的纸感（不用 mix-blend-mode） */
.ih__paper::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='700' height='700'%3E%3Cfilter id='w'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.011 0.015' numOctaves='3' seed='11'/%3E%3CfeColorMatrix type='matrix' values='0 0 0 0 0.20 0 0 0 0 0.15 0 0 0 0 0.09 0 0 0 0.5 0'/%3E%3C/filter%3E%3Crect width='700' height='700' filter='url(%23w)'/%3E%3C/svg%3E");
  background-size: 700px 700px;
  opacity: 0.4;
  pointer-events: none;
}

/* 手绘抖动滤镜挂到所有 .sk 线稿上（黑墨线"抖"起来，去 CAD 感） */
.sk { filter: url(#ihSketch); }

/* ---------- 纸纹颗粒（叠加细噪点） ---------- */
.ih__grain {
  position: absolute;
  inset: 0;
  z-index: 7;
  pointer-events: none;
  opacity: 0.4;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='matrix' values='0 0 0 0 0.2 0 0 0 0 0.16 0 0 0 0 0.1 0 0 0 0.04 0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* ---------- 手绘装饰：云 + 树 ---------- */
.ih__cloud {
  position: absolute;
  z-index: 1;
  top: 12%;
  right: 8%;
  width: clamp(120px, 14vw, 200px);
  height: auto;
  color: #2A2118;
  opacity: 0.55;
}
.ih__tree {
  position: absolute;
  z-index: 1;
  left: 1.5%;
  top: 25%;
  bottom: auto;
  width: clamp(56px, 6vw, 88px);
  height: auto;
  opacity: 0.5;
}

/* ---------- 流布局 ---------- */
.ih__inner {
  position: relative;
  z-index: 3;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px clamp(20px, 4vw, 70px) 18px;
  box-sizing: border-box;
  overflow: hidden;
}

/* ---------- 手绘刊头（紧凑，给地图与洞察条留空间） ---------- */
.ih__masthead { flex: none; padding-top: 2px; margin-bottom: 2px; }
.ih__kicker {
  display: inline-block;
  font-family: var(--u-font-tech, 'Orbitron', sans-serif);
  font-size: 11px;
  letter-spacing: 0.3em;
  color: var(--gold);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.ih__title {
  margin: 0;
  font-family: "Kaiti SC", KaiTi, STKaiti, Georgia, "Songti SC", serif;
  font-weight: 700;
  font-size: clamp(22px, 2.8vw, 36px);
  line-height: 1.12;
  letter-spacing: 0.01em;
  color: #241B12;
}
.ih__rule { display: block; width: clamp(150px, 20vw, 260px); height: 13px; margin: 7px 0 5px; color: var(--orange); }
.ih__lede {
  margin: 0;
  max-width: 600px;
  font-family: "Kaiti SC", KaiTi, STKaiti, Georgia, serif;
  font-size: clamp(11px, 1vw, 14px);
  line-height: 1.5;
  color: var(--text-2);
}

/* ---------- 手绘世界：路径 + 六间小屋 ---------- */
.ih__map {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  margin: 6px 0 2px;
}
.ih__path {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
}
.ih__path-line {
  fill: none;
  stroke: #2A2118;
  stroke-width: 2.2;
  stroke-dasharray: 2 9;
  stroke-linecap: round;
  opacity: 0.5;
}

.ih__room {
  position: absolute;
  z-index: 2;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  width: clamp(104px, 11vw, 138px);
  padding: 0;
  background: none;
  border: 0;
  cursor: pointer;
  color: inherit;
  font-family: inherit;
  transition: transform 0.22s ease;
}
.ih__room:hover,
.ih__room:focus-visible { transform: translate(-50%, -54%); outline: none; }
.ih__room:hover .ih__house-lines,
.ih__room:focus-visible .ih__house-lines { stroke: var(--orange); }
.ih__room:hover .ih__disc { transform: scale(1.12) rotate(-8deg); }

/* a24 漂浮倾斜光盘（房顶上方） —— 尺寸压扁，更多塞进房顶后方，缩短整簇纵向高度 */
.ih__disc {
  position: relative;
  width: clamp(44px, 4.2vw, 60px);
  height: clamp(44px, 4.2vw, 60px);
  border-radius: 50%;
  margin-bottom: -16px;
  box-shadow:
    inset 0 0 0 5px rgba(255, 253, 247, 0.5),
    inset 0 0 18px rgba(42, 33, 24, 0.32),
    0 10px 20px rgba(74, 40, 20, 0.22);
  transform: perspective(500px) rotateX(46deg) rotateZ(-14deg);
  transition: transform 0.26s ease;
  animation: ih-disc-float 7s ease-in-out infinite;
}
.ih__disc-hole {
  position: absolute;
  left: 50%; top: 50%;
  width: 26%; height: 26%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(circle at 40% 38%, #FBF6EC, #E7DCC6 70%, #D8C9AC);
  box-shadow: 0 0 0 3px rgba(255, 253, 247, 0.55), inset 0 1px 3px rgba(74, 40, 20, 0.4);
}
@keyframes ih-disc-float {
  0%, 100% { transform: perspective(500px) rotateX(46deg) rotateZ(-14deg) translateY(0); }
  50% { transform: perspective(500px) rotateX(46deg) rotateZ(-14deg) translateY(-7px); }
}

/* 手绘小屋 */
.ih__house-wrap { position: relative; display: block; width: 100%; }
.ih__house { width: 100%; height: auto; display: block; }
.ih__house-lines { transition: stroke 0.22s ease; }
.ih__sign-no {
  position: absolute;
  left: 50%;
  top: 9.3%;                 /* 屋顶白牌中心（viewBox 0..134 中 12.5/134） */
  transform: translate(-50%, -50%);
  font-family: Georgia, "Times New Roman", serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #2A2118;
  pointer-events: none;
}

/* 文案 */
.ih__cap {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-top: 2px;
}
.ih__zh {
  font-family: "Kaiti SC", KaiTi, STKaiti, Georgia, serif;
  font-size: clamp(14px, 1.3vw, 18px);
  font-weight: 700;
  color: #241B12;
  letter-spacing: 0.02em;
}
.ih__desc {
  margin-top: 2px;
  font-size: clamp(9px, 0.9vw, 11px);
  line-height: 1.35;
  color: var(--text-2);
  max-width: 150px;
}
.ih__go {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--u-font-tech, 'Orbitron', sans-serif);
  font-size: 9px;
  letter-spacing: 0.12em;
  color: var(--gold);
  font-weight: 700;
  opacity: 0.7;
  transition: opacity 0.2s ease, gap 0.2s ease, color 0.2s ease;
}
.ih__go i { font-style: normal; transition: transform 0.2s ease; }
.ih__room:hover .ih__go { opacity: 1; gap: 9px; color: var(--orange); }
.ih__room:hover .ih__go i { transform: translateX(3px); }

/* ---------- 手绘指南针（置于地图左侧中部，避开底部馆长洞察条） ---------- */
.ih__compass {
  position: absolute;
  z-index: 4;
  left: clamp(10px, 1.6vw, 26px);
  top: 52%;
  transform: translateY(-50%);
  width: clamp(50px, 5vw, 74px);
  height: auto;
  color: #2A2118;
  opacity: 0.55;
}
.ih__compass-t { font-family: Georgia, serif; font-size: 13px; font-weight: 700; fill: #2A2118; }

/* ---------- 馆长洞察（主编精选，收编进大厅底部流） ---------- */
.ih__stories { flex: 0 0 auto; max-height: 232px; margin: 2px 0 8px; }
.ih__stories :deep(.hi) {
  position: static;
  left: auto;
  bottom: auto;
  transform: none;
  width: 100%;
  background: none;
  border: none;
  border-radius: 0;
  box-shadow: none;
  backdrop-filter: none;
  padding: 0;
  pointer-events: auto;
}
.ih__stories :deep(.hi__head) { margin: 0 4px 5px; }
.ih__stories :deep(.hi__row) { gap: clamp(8px, 1vw, 14px); }
.ih__stories :deep(.hi__card-in) { padding: 8px 12px 8px; }
.ih__stories :deep(.hi__q) { font-size: 14.5px; margin: 3px 0 1px; }
.ih__stories :deep(.hi__a) { margin-bottom: 4px; }
.ih__stories :deep(.hi__kicker) { font-size: 8.5px; }
.ih__stories :deep(.hi__credits) { margin-top: 4px; }
.ih__stories :deep(.hi__fact) { padding: 2px 0; }
.ih__stories :deep(.hi__fact:last-child) { padding-bottom: 0; }

/* ---------- 窄屏：竖排可滚动，保留全部入口 ---------- */
@media (max-width: 900px) {
  .ih__inner { overflow-y: auto; padding: 14px 16px 16px; }
  .ih__map { height: auto; min-height: 520px; }
  .ih__path { display: none; }
  .ih__room {
    position: relative;
    left: auto !important;
    top: auto !important;
    transform: none;
    width: 100%;
    max-width: 280px;
    margin: 0 auto 14px;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    text-align: left;
  }
  .ih__room:hover, .ih__room:focus-visible { transform: none; }
  .ih__room { flex-direction: row; }
  .ih__disc { flex: none; margin-bottom: 0; }
  .ih__cap { align-items: flex-start; text-align: left; }
  .ih__cloud, .ih__tree, .ih__compass { display: none; }
}

/* ---------- 矮屏（高度不足，desktop 布局也要塞下两排 + 卡片） ----------
   压缩光盘 / 说明文字，并收一点卡片高度，给地图让出纵向空间 */
@media (max-height: 820px) {
  .ih__disc {
    width: clamp(38px, 3.6vw, 50px);
    height: clamp(38px, 3.6vw, 50px);
    margin-bottom: -18px;
  }
  .ih__zh { font-size: clamp(13px, 1.1vw, 16px); }
  .ih__desc { font-size: clamp(8.5px, 0.8vw, 10px); }
  .ih__go { margin-top: 3px; }
  .ih__stories { max-height: 168px; }
}

@media (prefers-reduced-motion: reduce) {
  .ih, .ih.is-entering { transition-duration: 0.16s; }
  .ih__disc { animation: none; }
}
</style>
