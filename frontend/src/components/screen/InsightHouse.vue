<template>
  <!--
    ============================================================
    影评洞察馆 · 大厅（/screen 入口层）—— 3D 动态交互版
    ------------------------------------------------------------
    参考 itomdev.com：可探索的 3D 走廊 + 交互式门（walkable corridor）。
    这里把大屏的六个分类做成六扇门，每扇门后是一间展厅。

    · 整屋放进 perspective 视锥，鼠标移动 = 环视走廊（rotateX/rotateY）
    · 地面 / 左右墙用 3D transform 向后退缩，形成"走得进去"的走廊纵深
    · 门 hover/聚焦 → 门板绕铰链整扇向内推开（rotateY -102°），露出泛光的展厅内景
    · 点击门 → 朝该门推近并淡出（走进去），父级接 enter(key) 切到展厅
    · 全部 CSS 3D / 内联 SVG，零新依赖、零网络请求；棕金手绘体系不变
    · 窄屏（≤900px）与 prefers-reduced-motion 下降级为平面（保证可用）
    ============================================================
  -->
  <div
    ref="house"
    class="ih"
    :class="{ 'is-entering': entering, 'is-ready': ready, 'is-dragging': dragging }"
    :style="{ '--ex': enterX, '--ey': enterY }"
    @pointerdown="onDragStart"
    @click.capture="onClickCapture"
  >
    <div class="ih__persp">
      <div class="ih__world" @pointermove="onMove" @pointerleave="onLeave">

        <!-- 远景天幕（在走廊最深处，给纵深厚底） -->
        <div class="ih__sky3d" aria-hidden="true" />

        <!-- 天花板 / 左右墙：3D 向后退缩，构成走廊 -->
        <div class="ih__ceil" aria-hidden="true" />
        <div class="ih__wall ih__wall--l" aria-hidden="true" />
        <div class="ih__wall ih__wall--r" aria-hidden="true" />

        <!-- 地面：向后退缩的石板路（走廊的"走得进去"感） -->
        <div class="ih__floor" aria-hidden="true"><i class="ih__floor-path" /></div>

        <!-- ---------- 正面立面（六扇门所在，保持平面清晰、可点） ---------- -->
        <div class="ih__facade">
          <!-- 天空：暖纸底 + 一抹淡晕 -->
          <div class="ih__sky" aria-hidden="true" />

          <!-- 远处的云（两层慢视差） -->
          <svg class="ih__cloud ih__cloud--a" viewBox="0 0 200 60" aria-hidden="true">
            <path d="M18 44c-10 0-16-7-16-15s7-14 16-14c3-11 13-18 24-18 11 0 20 6 24 15 3-2 7-3 11-3 12 0 21 9 21 20 0 9-7 15-17 15z" fill="currentColor" />
          </svg>
          <svg class="ih__cloud ih__cloud--b" viewBox="0 0 200 60" aria-hidden="true">
            <path d="M14 46c-8 0-13-6-13-13s6-12 13-12c2-9 11-15 20-15 9 0 17 5 20 13 2-1 5-2 8-2 10 0 18 7 18 17 0 7-6 12-14 12z" fill="currentColor" />
          </svg>

          <!-- 砖墙：SVG pattern 手绘缝 + 轻微色差（铅笔感靠低对比细线） -->
          <div class="ih__wall-face" aria-hidden="true">
            <svg width="100%" height="100%" aria-hidden="true">
              <defs>
                <pattern id="ih-brick" width="96" height="46" patternUnits="userSpaceOnUse">
                  <rect width="96" height="46" fill="#F2EAD9" />
                  <rect x="1" y="1" width="92" height="20" rx="2" fill="#EFE5D1" />
                  <rect x="-47" y="25" width="92" height="20" rx="2" fill="#F0E7D4" />
                  <rect x="49" y="25" width="92" height="20" rx="2" fill="#EDE3CE" />
                  <g stroke="#C0AF90" stroke-width="1.1" fill="none" opacity="0.55">
                    <path d="M0 1h96M0 24h96M0 47h96" />
                    <path d="M1 2v20M49 27v19M96 27v19" />
                  </g>
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#ih-brick)" />
            </svg>
          </div>

          <!-- 屋檐（压在墙上沿，给门一个"房子"的顶） -->
          <div class="ih__eave" aria-hidden="true" />

          <!-- 招牌：吊在屋檐下，风一吹轻轻摆 -->
          <div class="ih__sign" aria-hidden="true">
            <i class="ih__sign-rope ih__sign-rope--l" />
            <i class="ih__sign-rope ih__sign-rope--r" />
            <div class="ih__sign-board">
              <span class="ih__sign-zh">影评洞察馆</span>
              <span class="ih__sign-en">INSIGHT HOUSE</span>
            </div>
          </div>

          <!-- 左：树（树冠加铅笔轮廓线 + <use> 错位重画 = 手绘双线） -->
          <svg class="ih__tree" viewBox="0 0 160 220" aria-hidden="true">
            <path d="M78 218V96" stroke="#7A5B3A" stroke-width="11" stroke-linecap="round" />
            <path d="M78 150c-16-8-24-20-27-34" stroke="#7A5B3A" stroke-width="7" stroke-linecap="round" fill="none" />
            <path d="M78 132c15-7 23-19 26-33" stroke="#7A5B3A" stroke-width="6" stroke-linecap="round" fill="none" />
            <path id="ih-tree-c" d="M78 20c26 0 44 18 44 40 0 8-3 15-8 21 9 5 15 14 15 25 0 17-15 30-34 30-5 0-10-1-14-3-5 2-11 3-17 3-21 0-38-15-38-34 0-12 7-22 17-27-6-6-9-13-9-21 0-19 18-34 44-34z"
                fill="#8B7355" opacity="0.9" stroke="#6F5436" stroke-width="2.2" stroke-opacity="0.4" />
            <use href="#ih-tree-c" transform="translate(2.6 2.2)" opacity="0.18" />
            <g fill="#F6F1E6" opacity="0.35">
              <ellipse cx="62" cy="52" rx="14" ry="9" />
              <ellipse cx="96" cy="66" rx="10" ry="7" />
            </g>
          </svg>

          <!-- 右：窗（两扇，透光） -->
          <div class="ih__window" aria-hidden="true">
            <i class="ih__win-pane" /><i class="ih__win-pane" />
            <i class="ih__win-bar" />
          </div>
          <div class="ih__window ih__window--sm" aria-hidden="true">
            <i class="ih__win-pane" /><i class="ih__win-pane" />
            <i class="ih__win-bar" />
          </div>

          <!-- 六扇门：每扇后是一间展厅 -->
          <div class="ih__doors">
            <button
              v-for="(r, i) in rooms"
              :key="r.key"
              class="ih__door"
              :class="{ 'is-open': hover === i, 'is-tall': i % 2 === 1 }"
              type="button"
              :aria-label="`进入${r.zh}展厅`"
              @pointerenter="hover = i"
              @pointerleave="hover = -1"
              @focus="hover = i"
              @blur="hover = -1"
              @click="enter(r, i, $event)"
            >
              <!-- 门牌 -->
              <span class="ih__plate ih-sk-b"><b>{{ r.zh }}</b></span>
              <!-- 门洞（里面透出展厅的光 + 展厅名） -->
              <span class="ih__doorway" aria-hidden="true">
                <i class="ih__glow" :style="{ background: r.glow }" />
                <span class="ih__room-name">{{ r.zh }}</span>
              </span>
              <!-- 门板（hover 时整扇向内推开，露出展厅内景） -->
              <span class="ih__leaf ih-sk-a" aria-hidden="true">
                <i class="ih__leaf-line" /><i class="ih__leaf-line" /><i class="ih__leaf-line" />
                <i class="ih__knob" />
                <!-- 门上贴的分类贴纸 -->
                <i class="ih__sticker" :style="{ '--st': r.tint }">{{ r.icon }}</i>
              </span>
              <!-- 门前灯：hover 亮 -->
              <span class="ih__lamp" aria-hidden="true" />
            </button>
          </div>

          <!-- 花坛 + 猫（手绘小彩蛋；<use> 错位重画一遍 = 铅笔双线） -->
          <svg class="ih__cat" viewBox="0 0 90 70" aria-hidden="true">
            <g id="ih-cat">
              <path d="M20 62c0-14 8-24 20-24h6c11 0 19 9 20 21" fill="none" stroke="#5B4630" stroke-width="3.4" stroke-linecap="round" />
              <circle cx="30" cy="40" r="13" fill="#5B4630" />
              <path d="M21 32l-2-11 11 5M39 32l3-11-12 5" fill="#5B4630" />
              <path d="M66 62c6-4 12-4 18 2" fill="none" stroke="#5B4630" stroke-width="3.4" stroke-linecap="round" />
              <path d="M20 62h46" stroke="#5B4630" stroke-width="3" stroke-linecap="round" />
              <circle cx="26" cy="38" r="1.8" fill="#F6F1E6" />
              <circle cx="34" cy="38" r="1.8" fill="#F6F1E6" />
            </g>
            <use href="#ih-cat" transform="translate(2.4 2)" opacity="0.26" />
          </svg>

          <div class="ih__planter" aria-hidden="true">
            <svg viewBox="0 0 220 70" preserveAspectRatio="none">
              <path d="M4 40h212l-10 26H14z" fill="#8B7355" />
              <path d="M4 40h212l-3 7H7z" fill="#A08a68" />
              <g fill="#6F7A55" opacity="0.85">
                <ellipse cx="42" cy="34" rx="16" ry="14" />
                <ellipse cx="86" cy="30" rx="19" ry="16" />
                <ellipse cx="136" cy="34" rx="15" ry="13" />
                <ellipse cx="180" cy="31" rx="17" ry="14" />
              </g>
            </svg>
          </div>

          <!-- 地面 + 手绘石板路（一块块椭圆石头伸向门，itomdev 的石头小路） -->
          <div class="ih__ground" aria-hidden="true">
            <svg class="ih__stones" viewBox="0 0 1200 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
              <g class="ih__stones-g">
                <ellipse cx="600" cy="206" rx="128" ry="40" />
                <ellipse cx="600" cy="172" rx="104" ry="33" />
                <ellipse cx="600" cy="144" rx="84" ry="27" />
                <ellipse cx="600" cy="120" rx="66" ry="21" />
                <ellipse cx="600" cy="100" rx="51" ry="16" />
                <ellipse cx="600" cy="84" rx="39" ry="12" />
                <ellipse cx="600" cy="70" rx="29" ry="9" />
              </g>
              <g class="ih__grass">
                <path d="M150 212c-4-14-2-26 4-36M164 212c2-12 8-22 16-28M136 212c-6-10-8-20-6-30" />
                <path d="M1050 212c4-14 2-26-4-36M1036 212c-2-12-8-22-16-28M1064 212c6-10 8-20 6-30" />
              </g>
              <g class="ih__pebble">
                <ellipse cx="330" cy="196" rx="9" ry="5" />
                <ellipse cx="880" cy="182" rx="7" ry="4" />
                <ellipse cx="430" cy="150" rx="6" ry="3.4" />
              </g>
            </svg>
          </div>

          <!-- 底部提示（itomdev 探索者 Toast：标签 + 一句话） -->
          <div class="ih__hint">
            <span class="ih__hint-chip">探索者</span>
            <b>{{ hoverRoom ? hoverRoom.zh : '推门而入' }}</b>
            <span>{{ hoverRoom ? hoverRoom.desc : '滚轮走近 · 拖拽环视 · 点门进展厅' }}</span>
          </div>
        </div>

      </div>
    </div>
    <!-- 纸纹颗粒：feTurbulence 噪声，给整屋一层"画在纸上"的质感（itomdev paper-texture） -->
    <div class="ih__grain" aria-hidden="true" />
  </div>
</template>

<script setup>
// ============================================================
// 大厅：只负责"选门"。真正的内容在房间（UniverseScreen）里。
// 走进动画：把点击那一刻门的位置写进 --ex/--ey，整屋朝那个点推近并淡出，
// 父级在过渡结束后切到房间视图，观感上就是"穿过门走进去了"。
// 鼠标视差：写 --mx/--my，立面各层按深度取不同系数；3D 世界按 --mx/--my 做环视旋转。
// ============================================================
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  /** 六间展厅：与 UniverseScreen 的 VIEWS 同源 */
  rooms: { type: Array, default: () => [] },
})

const emit = defineEmits(['enter'])

const house = ref(null)
const ready = ref(false)
const entering = ref(false)
const hover = ref(-1)
const enterX = ref('50%')
const enterY = ref('50%')
const dragging = ref(false)
const justDragged = ref(false)

const hoverRoom = computed(() => (hover.value >= 0 ? props.rooms[hover.value] : null))

/* 鼠标视差：写 --mx/--my，各层按深度取不同系数（与说明页天气剧场同套路） */
function onMove(e) {
  const el = house.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const mx = ((e.clientX - r.left) / r.width - 0.5) * 2
  const my = ((e.clientY - r.top) / r.height - 0.5) * 2
  el.style.setProperty('--mx', mx.toFixed(3))
  el.style.setProperty('--my', my.toFixed(3))
}
function onLeave() {
  const el = house.value
  if (!el) return
  el.style.setProperty('--mx', '0')
  el.style.setProperty('--my', '0')
}

const OPEN_MS = 640 // 门开+推近的时长，与父级切换时序对齐

/* ---------- itomdev 式"走得进、看得见"：滚轮走近 + 拖拽环视 ----------
   --walk：滚轮累计 0→1，整屋朝观众推近最多 190px（穿过走廊的纵深感）
   --rx/--ry：拖拽时的环视角度，松手缓回正中
   ★ 这两个变量与轻浮动画一起编进 .ih__persp 的 keyframes（见样式区注释），
     所以平滑不能用 CSS transition（会被动画覆盖），改用 rAF 补间。 */
const isFlat = () => window.matchMedia('(max-width: 900px)').matches
const isCalm = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* rAF 补间：把 CSS 变量从当前值平滑送到目标值（easeOutCubic） */
function tweenVar(name, to, ms = 260) {
  const el = house.value
  if (!el) return
  const from = Number(el.style.getPropertyValue(name) || 0)
  if (Math.abs(from - to) < 0.002) { el.style.setProperty(name, String(to)); return }
  const t0 = performance.now()
  const step = (now) => {
    const p = Math.min(1, (now - t0) / ms)
    const e = 1 - Math.pow(1 - p, 3)
    el.style.setProperty(name, p < 1 ? (from + (to - from) * e).toFixed(3) : String(to))
    if (p < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

function onWheel(e) {
  if (isCalm() || isFlat()) return
  e.preventDefault()
  const cur = Number(house.value?.style.getPropertyValue('--walk') || 0)
  tweenVar('--walk', Math.min(1, Math.max(0, cur + (e.deltaY > 0 ? 0.16 : -0.16))))
}

function onDragStart(e) {
  if (isCalm() || isFlat() || e.button !== 0) return
  const el = house.value
  const start = { x: e.clientX, y: e.clientY }
  dragging.value = true
  const move = (ev) => {
    const r = el.getBoundingClientRect()
    const rx = Math.max(-6, Math.min(6, ((ev.clientX - start.x) / r.width) * 14))
    const ry = Math.max(-4, Math.min(4, (-(ev.clientY - start.y) / r.height) * 9))
    el.style.setProperty('--rx', rx.toFixed(2))
    el.style.setProperty('--ry', ry.toFixed(2))
  }
  const up = (ev) => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    dragging.value = false
    tweenVar('--rx', 0, 240)
    tweenVar('--ry', 0, 240)
    // 位移 > 6px 算拖拽：吞掉随后那一次 click（浏览器会把起落点不同的 click
    // 派发到公共祖先上，导致"拖一下反而点开门"——天气剧场同款坑）
    if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 6) {
      justDragged.value = true
      setTimeout(() => { justDragged.value = false }, 400)
    }
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}
function onClickCapture(e) {
  if (justDragged.value) {
    e.preventDefault()
    e.stopPropagation()
    justDragged.value = false
  }
}

function enter(room, i, ev) {
  if (entering.value) return
  // 以这扇门为中心推近：算出它在大厅里的相对位置
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
  house.value?.style.setProperty('--mx', '0')
  house.value?.style.setProperty('--my', '0')
  house.value?.addEventListener('wheel', onWheel, { passive: false })
  requestAnimationFrame(() => { ready.value = true })
})
onUnmounted(() => house.value?.removeEventListener('wheel', onWheel))

defineExpose({ /** 便于父级在大厅重新挂载时复位 */ reset() { entering.value = false } })
</script>

<style scoped>
.ih {
  --ink: #6B5D4A;
  --paper: #F6F1E6;
  --wood: #8B6B47;
  --wood-d: #6B4E2E;
  --brick: #F2EAD9;
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #FBF7EE 0%, var(--paper) 46%, #EDE3CF 100%);
  opacity: 0;
  transform: scale(1.02);
  transition: opacity 0.5s ease, transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
  perspective: 1700px;            /* ★ 整屋视锥：走廊纵深之源 */
  perspective-origin: 50% 46%;
}
.ih.is-ready { opacity: 1; transform: scale(1); }

/* 走进去：朝点击的那扇门推近并淡出 */
.ih.is-entering {
  transform-origin: var(--ex, 50%) var(--ey, 50%);
  transform: scale(2.4);
  opacity: 0;
  transition: transform 0.64s cubic-bezier(0.5, 0, 0.9, 0.4), opacity 0.5s ease 0.12s;
  pointer-events: none;
}

/* ---------- 3D 世界 ----------
   ★ 轻浮动画必须挂在 .ih__persp（preserve-3d 子树之外）：
     若挂在 preserve-3d 的 .ih__world 上，Chrome 跑约 3 秒后会把该层的命中测试
     交给合成器，preserve-3d + perspective 的回投影随之出错 —— 2026-10-22 实测
     等待 3 秒后悬停/点击门 0/5 全部失效且再动鼠标也不自愈；挪到 persp 后 2/2 通过。
     （上一版 3D 走廊就埋着这个雷，只因回归都在 3 秒内跑完才没暴露。）
   走近（--walk）+ 环视（--rx/--ry）在同一 keyframes 里读变量叠加，
     平滑由 rAF 补间负责（动画会覆盖 transition，不能用过渡）。 */
.ih__persp {
  position: absolute;
  inset: 0;
  animation: ih-float 16s ease-in-out infinite;
}
@keyframes ih-float {
  0%, 100% {
    transform: translateZ(calc(var(--walk, 0) * 190px)) rotateX(calc(var(--ry, 0) * 1deg)) rotateY(calc(var(--rx, 0) * 1deg)) rotateX(0.5deg) rotateY(-1.6deg);
  }
  50% {
    transform: translateZ(calc(var(--walk, 0) * 190px)) rotateX(calc(var(--ry, 0) * 1deg)) rotateY(calc(var(--rx, 0) * 1deg)) rotateX(-0.5deg) rotateY(1.6deg);
  }
}
/* 走进去：暂停轻浮 + 世界向前推，强化"穿过门"的纵深 */
.ih.is-entering .ih__persp { animation: none; transform: translateZ(220px); }

/* 世界本体：只保留 preserve-3d（纵深由子层级联提供），不挂任何动画 */
.ih__world {
  position: absolute;
  inset: 0;
  transform-style: preserve-3d;
}

/* 远景天幕：在最深处垫一层暖白晕，避免走廊尽头穿帮 */
.ih__sky3d {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 200%;
  height: 200%;
  transform: translate(-50%, -50%) translateZ(-520px) translate(calc(var(--mx, 0) * -14px), calc(var(--my, 0) * -8px));
  background: radial-gradient(60% 55% at 50% 46%, rgba(255, 253, 247, 0.96), rgba(255, 253, 247, 0) 72%);
  pointer-events: none;
}

/* 天花板 / 左右墙：3D 向后退缩，构成走廊（低对比、低存在感，不抢立面） */
.ih__ceil, .ih__wall, .ih__floor {
  position: absolute;
  pointer-events: none;
  backface-visibility: hidden;
}
.ih__ceil {
  left: -20%; right: -20%; top: -22%; height: 42%;
  transform-origin: top center;
  transform: translateZ(-260px) rotateX(-74deg) translate(calc(var(--mx, 0) * -10px), calc(var(--my, 0) * -5px));
  background:
    repeating-linear-gradient(90deg, rgba(107, 93, 74, 0.10) 0 1px, rgba(107, 93, 74, 0) 1px 46px),
    linear-gradient(180deg, #EFE6D3 0%, #E7DBC4 100%);
  box-shadow: inset 0 0 60px rgba(107, 93, 74, 0.12);
}
.ih__wall {
  top: -10%; bottom: -10%; width: 44%;
  background:
    repeating-linear-gradient(0deg, rgba(120, 100, 74, 0.12) 0 1px, rgba(120, 100, 74, 0) 1px 40px),
    linear-gradient(90deg, rgba(242, 234, 217, 0.0), rgba(214, 198, 168, 0.55));
}
.ih__wall--l { left: 0; transform-origin: left center; transform: translateZ(-260px) rotateY(64deg) translateY(calc(var(--my, 0) * -5px)); }
.ih__wall--r { right: 0; transform-origin: right center; transform: translateZ(-260px) rotateY(-64deg) translateY(calc(var(--my, 0) * -5px)); }

/* 地面：向后退缩的石板路（走廊"走得进去"的纵深感） */
.ih__floor {
  left: -30%; right: -30%; bottom: 0; height: 56%;
  transform-origin: bottom center;
  transform: translateZ(-260px) rotateX(76deg) translate(calc(var(--mx, 0) * -12px), 0);
  background:
    repeating-linear-gradient(0deg, rgba(160, 140, 110, 0.22) 0 1px, rgba(160, 140, 110, 0) 1px 38px),
    linear-gradient(180deg, #E9DCC2 0%, #DFCFB0 100%);
}
.ih__floor-path {
  position: absolute;
  left: 50%; bottom: 0; width: 26%;
  height: 100%;
  transform: translateX(-50%);
  background:
    repeating-linear-gradient(90deg, rgba(255, 253, 247, 0.5) 0 2px, rgba(255, 253, 247, 0) 2px 60px);
  clip-path: polygon(28% 0, 72% 0, 100% 100%, 0 100%);
  opacity: 0.85;
}

/* ---------- 正面立面（六扇门所在，保持平面、清晰、可点） ----------
   立面必须是"扁平 2D 层"，不能 preserve-3d —— 否则门打开后门板让位，
   3D 命中测试会让门后的砖墙 SVG 抢走点击（实测 inBtn=false），导致点门进不去展厅。
   立面作为走廊的"后墙"本就该是平面图；3D 纵深由同级的地面/左右墙提供。
   每扇门自身带 perspective，门板仍能在 3D 里整扇推开。 */
.ih__facade {
  position: absolute;
  inset: 0;
}

/* ---------- 手绘抖边（itomdev 绝技：不对称大圆角 = 纸上手画的框） ---------- */
.ih-sk-a { border-radius: 9px 34px 11px 30px / 11px 30px 9px 34px; }
.ih-sk-b { border-radius: 255px 16px 225px 16px / 16px 225px 16px 255px; }

/* ---------- 纸纹颗粒：画在纸上的质感（itomdev paper-texture.webp 的 CSS 版） ----------
   ★ 禁用 mix-blend-mode：混合模式会迫使 Chrome 把 preserve-3d 走廊并进混合层，
     之后视差/浮动造成的 transform 变化会令合成层命中测试错乱 —— 实测真实鼠标
     hover 门直接失效（elementFromPoint 命中立面、is-open 不触发）。噪声本就是
     半透明棕颗粒，普通 alpha 合成即可得到纸纹，无需混合。 */
.ih__grain {
  position: absolute;
  inset: 0;
  z-index: 6;
  pointer-events: none;
  opacity: 0.7;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='matrix' values='0 0 0 0 0.42 0 0 0 0 0.36 0 0 0 0 0.26 0 0 0 0.05 0'/%3E%3C/filter%3E%3Crect width='240' height='240' filter='url(%23n)'/%3E%3C/svg%3E");
}

.ih__scene { position: absolute; inset: 0; }

/* ---------- 天空 ---------- */
.ih__sky {
  position: absolute;
  inset: 0 0 26% 0;
  background:
    radial-gradient(80% 60% at 50% 12%, rgba(255, 253, 247, 0.95), rgba(255, 253, 247, 0) 70%),
    linear-gradient(180deg, #FDFAF3 0%, #F7F1E4 60%, #F3EBDC 100%);
  transform: translate3d(calc(var(--mx, 0) * -3px), calc(var(--my, 0) * -2px), 0);
  transition: transform 0.35s ease-out;
}

/* ---------- 云（视差最慢的一层） ---------- */
.ih__cloud {
  position: absolute;
  color: #FFFDF7;
  opacity: 0.9;
  filter: drop-shadow(0 2px 0 rgba(160, 140, 110, 0.12));
  transform: translate3d(calc(var(--mx, 0) * -6px), calc(var(--my, 0) * -4px), 0);
  transition: transform 0.35s ease-out;
}
.ih__cloud--a { width: clamp(140px, 17vw, 240px); left: 6%; top: 9%; }
.ih__cloud--b { width: clamp(110px, 13vw, 190px); right: 8%; top: 15%; opacity: 0.78; }

/* ---------- 砖墙 ---------- */
.ih__wall-face {
  position: absolute;
  left: 0;
  right: 0;
  top: 20%;
  bottom: 24%;
  overflow: hidden;
  transform: translate3d(calc(var(--mx, 0) * -8px), 0, 0);
  transition: transform 0.35s ease-out;
}
.ih__wall-face::after {
  /* 墙上的铅笔阴影：上浅下深，让墙有体积 */
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.32) 0%, rgba(255, 255, 255, 0) 30%, rgba(107, 93, 74, 0.07) 78%, rgba(107, 93, 74, 0.14) 100%);
  pointer-events: none;
}

/* ---------- 屋檐 ---------- */
.ih__eave {
  position: absolute;
  left: -2%;
  right: -2%;
  top: 18.5%;
  height: 4.2%;
  background: linear-gradient(180deg, #7A5B3A 0%, #6B4E2E 62%, #5C4326 100%);
  border-radius: 3px 3px 0 0;
  box-shadow: 0 6px 14px rgba(74, 40, 20, 0.16);
  transform: translate3d(calc(var(--mx, 0) * -10px), 0, 0);
  transition: transform 0.35s ease-out;
}

/* ---------- 招牌 ---------- */
.ih__sign {
  position: absolute;
  left: 50%;
  top: 21.5%;
  transform: translateX(-50%);
  transform-origin: 50% -14px;
  animation: ih-sway 6.5s ease-in-out infinite;
  z-index: 3;
}
.ih__sign-rope {
  position: absolute;
  top: -14px;
  width: 1.6px;
  height: 16px;
  background: #6B4E2E;
}
.ih__sign-rope--l { left: 14%; }
.ih__sign-rope--r { right: 14%; }
.ih__sign-board {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 7px 26px 8px;
  background: linear-gradient(165deg, #8B6B47 0%, #79563A 55%, #6B4E2E 100%);
  border: 2px solid #5C4326;
  box-shadow: 0 5px 12px rgba(74, 40, 20, 0.22), 3px 3px 0 rgba(74, 40, 20, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.16);
  transform: rotate(-0.6deg);
}
.ih__sign-zh {
  font-size: clamp(15px, 1.5vw, 21px);
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #FBF3E4;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.24);
}
.ih__sign-en {
  font-size: 8.5px;
  letter-spacing: 0.34em;
  color: rgba(251, 243, 228, 0.62);
}
@keyframes ih-sway {
  0%, 100% { transform: translateX(-50%) rotate(-0.9deg); }
  50% { transform: translateX(-50%) rotate(0.9deg); }
}

/* ---------- 树 ---------- */
.ih__tree {
  position: absolute;
  left: max(1%, 10px);
  bottom: 25%;
  width: clamp(84px, 9.5vw, 137px);
  height: auto;
  transform: translate3d(calc(var(--mx, 0) * -16px), calc(var(--my, 0) * -6px), 0);
  transition: transform 0.35s ease-out;
}

/* ---------- 窗 ---------- */
.ih__window {
  position: absolute;
  right: 4%;
  top: 26%;
  width: clamp(74px, 8.4vw, 118px);
  height: clamp(58px, 6.6vw, 92px);
  padding: 5px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  background: linear-gradient(180deg, #FBF6EC, #EFE5D2);
  border: 2.6px solid #6B4E2E;
  border-radius: 3px;
  box-shadow: 0 3px 8px rgba(74, 40, 20, 0.14), inset 0 0 0 1px rgba(255, 255, 255, 0.6);
  transform: translate3d(calc(var(--mx, 0) * -12px), 0, 0);
  transition: transform 0.35s ease-out;
}
.ih__window--sm { right: 15.5%; top: 25%; width: clamp(56px, 6vw, 86px); height: clamp(44px, 4.8vw, 68px); }
.ih__win-pane {
  background: linear-gradient(160deg, #DCEBF2 0%, #C8DCE6 55%, #BFD4E0 100%);
  border-radius: 1px;
}
.ih__win-bar {
  position: absolute;
  left: 5px;
  right: 5px;
  top: 50%;
  height: 2.4px;
  background: #6B4E2E;
  opacity: 0.75;
}

/* ---------- 门 ---------- */
.ih__doors {
  position: absolute;
  left: 0;
  right: 0;
  top: 36%;
  bottom: 24%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: clamp(8px, 1.4vw, 26px);
  padding: 0 clamp(12px, 5vw, 90px);
  transform: translate3d(calc(var(--mx, 0) * -14px), 0, 0);
  transition: transform 0.35s ease-out;
}

.ih__door {
  position: relative;
  flex: 0 1 clamp(96px, 13.6%, 168px);
  height: 82%;
  padding: 0;
  border: 0;
  background: none;
  cursor: pointer;
  perspective: 720px;          /* 门板自身的 3D 视角，让整扇门能真正"推开" */
  transform-style: preserve-3d;
}
.ih__door.is-tall { height: 88%; }

/* 门牌（手绘小木牌：抖边 + 硬阴影） */
.ih__plate {
  position: absolute;
  left: 50%;
  top: -26px;
  transform: translateX(-50%) translateY(4px);
  white-space: nowrap;
  padding: 3px 10px;
  background: #FFFDF7;
  border: 1.6px solid var(--wood-d);
  box-shadow: 0 2px 5px rgba(74, 40, 20, 0.16), 2px 2px 0 rgba(74, 40, 20, 0.14);
  /* 常驻可见：门上只挂图标的话，用户看不出这扇门后是什么 */
  opacity: 0.9;
  transition: opacity 0.24s ease, transform 0.24s ease, border-color 0.24s ease;
  z-index: 4;
}
.ih__plate b { font-size: 12px; font-weight: 700; color: #4A2E16; letter-spacing: 0.04em; }
.ih__door.is-open .ih__plate,
.ih__door:focus-visible .ih__plate {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
  border-color: #8B4513;
}

/* 门洞（里面的展厅光 + 展厅名）—— 抖边由 .ih-sk-a 提供 */
.ih__doorway {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border: 3px solid var(--wood-d);
  border-bottom: 0;
  background: #2E2418;
  box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.55);   /* 内凹的展厅深度 */
}
.ih__glow {
  position: absolute;
  inset: -10%;
  opacity: 0.42;
  filter: blur(10px);
  transition: opacity 0.4s ease;
}
.ih__door.is-open .ih__glow { opacity: 0.95; }
.ih__room-name {
  position: absolute;
  left: 50%;
  top: 52%;
  transform: translate(-50%, -50%) scale(0.9);
  font-size: clamp(12px, 1.4vw, 18px);
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #FFF6E9;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
  opacity: 0;
  transition: opacity 0.4s ease 0.08s, transform 0.4s ease 0.08s;
  white-space: nowrap;
}
.ih__door.is-open .ih__room-name { opacity: 0.96; transform: translate(-50%, -50%) scale(1); }

/* 门板：hover 时绕左侧铰链整扇向内推开（真正的 3D 开门）—— 抖边由 .ih-sk-a 提供 */
.ih__leaf {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14) 0%, rgba(255, 255, 255, 0) 18%),
    linear-gradient(180deg, #9A7A54 0%, var(--wood) 42%, #7A5B3A 100%);
  border: 3px solid var(--wood-d);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1);
  transform-origin: left center;
  transform: rotateY(0deg);
  transition: transform 0.5s cubic-bezier(0.34, 1.18, 0.64, 1), box-shadow 0.3s ease;
  overflow: hidden;
}
.ih__door.is-open .ih__leaf {
  transform: rotateY(-102deg);                 /* ★ 整扇门向内推开，露出展厅内景 */
  box-shadow: 14px 6px 26px rgba(74, 40, 20, 0.34);
}
.ih__leaf-line {
  position: absolute;
  left: 12%;
  right: 12%;
  height: 1.4px;
  background: rgba(60, 40, 22, 0.28);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.12);
}
.ih__leaf-line:nth-of-type(1) { top: 26%; }
.ih__leaf-line:nth-of-type(2) { top: 50%; }
.ih__leaf-line:nth-of-type(3) { top: 74%; }
.ih__knob {
  position: absolute;
  right: 9px;
  top: 52%;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: radial-gradient(circle at 34% 32%, #F0D9A8, #A9762E 70%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
}
/* 门上贴纸（每扇门贴得歪歪斜斜，像真随手贴上去的） */
.ih__sticker {
  position: absolute;
  left: 50%;
  top: 30%;
  transform: translate(-50%, -50%) rotate(var(--sr, -7deg));
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  font-size: 19px;
  font-style: normal;
  background: #FFFDF7;
  border: 1.6px solid rgba(107, 78, 46, 0.5);
  border-radius: 50%;
  box-shadow: 0 2px 5px rgba(74, 40, 20, 0.2);
  transition: transform 0.4s cubic-bezier(0.34, 1.18, 0.64, 1);
}
.ih__door:nth-child(1) { --sr: -9deg; }
.ih__door:nth-child(2) { --sr: 6deg; }
.ih__door:nth-child(3) { --sr: -4deg; }
.ih__door:nth-child(4) { --sr: 8deg; }
.ih__door:nth-child(5) { --sr: -10deg; }
.ih__door:nth-child(6) { --sr: 3deg; }
.ih__door.is-open .ih__sticker { transform: translate(-50%, -50%) rotate(calc(var(--sr, -7deg) + 11deg)) scale(1.06); }

/* 门前灯 */
.ih__lamp {
  position: absolute;
  left: 50%;
  top: -14px;
  transform: translateX(-50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(194, 65, 12, 0.22);
  box-shadow: 0 0 0 rgba(194, 65, 12, 0);
  transition: box-shadow 0.3s ease, background 0.3s ease;
}
.ih__door.is-open .ih__lamp,
.ih__door:focus-visible .ih__lamp {
  background: rgba(255, 196, 120, 0.95);
  box-shadow: 0 0 14px 5px rgba(240, 160, 60, 0.45);
}

/* ---------- 猫 ---------- */
.ih__cat {
  position: absolute;
  left: 3.5%;
  bottom: 15%;
  width: clamp(46px, 5vw, 70px);
  height: auto;
  transform: translate3d(calc(var(--mx, 0) * -22px), 0, 0) scaleX(-1);
  transition: transform 0.35s ease-out;
}

/* ---------- 花坛 ---------- */
.ih__planter {
  position: absolute;
  right: 3%;
  left: auto;
  bottom: 15%;
  width: clamp(120px, 16vw, 220px);
  height: clamp(46px, 6vw, 74px);
  transform: translate3d(calc(var(--mx, 0) * -26px), 0, 0);
  transition: transform 0.35s ease-out;
}
.ih__planter svg { width: 100%; height: 100%; }

/* ---------- 地面 ---------- */
.ih__ground {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 25%;
  background: linear-gradient(180deg, #E9DCC2 0%, #E2D3B6 55%, #D9C8A8 100%);
  box-shadow: inset 0 3px 0 rgba(107, 93, 74, 0.16);
  overflow: hidden;
  transform: translate3d(calc(var(--mx, 0) * -30px), 0, 0);
  transition: transform 0.35s ease-out;
}

/* 手绘石板路：椭圆石头由远及近伸向门口 + 路边草簇 + 零散石子 */
.ih__stones { position: absolute; inset: 0; width: 100%; height: 100%; }
.ih__stones-g ellipse {
  fill: rgba(255, 253, 247, 0.52);
  stroke: #A08B6A;
  stroke-width: 2.4;
  stroke-opacity: 0.55;
}
.ih__grass path {
  fill: none;
  stroke: #6F7A55;
  stroke-width: 3.2;
  stroke-linecap: round;
  opacity: 0.8;
}
.ih__pebble ellipse {
  fill: #D9C8A8;
  stroke: #A08B6A;
  stroke-width: 1.6;
  stroke-opacity: 0.6;
}

/* ---------- 底部提示（itomdev 探索者 Toast：手绘纸签 + 硬阴影） ---------- */
.ih__hint {
  position: absolute;
  left: 50%;
  bottom: 3.4%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 18px;
  background: rgba(255, 253, 247, 0.94);
  border: 2px solid rgba(58, 46, 32, 0.72);
  box-shadow: 3px 3px 0 rgba(74, 40, 20, 0.2);
  white-space: nowrap;
  z-index: 5;
}
.ih__hint-chip {
  flex: none;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 2px;
  color: #FFF6E9;
  background: linear-gradient(160deg, #A0522D, #8B4513);
  border: 1.4px solid #5C4326;
  padding: 2px 9px 3px;
  transform: rotate(-1.5deg);
}
.ih__hint b { font-size: 13.5px; color: #8B4513; letter-spacing: 0.05em; }
.ih__hint span { font-size: 11.5px; color: var(--u-text-2, #7D6B52); letter-spacing: 0.04em; }

/* ---------- 窄屏：扁平化（关掉 3D 走廊，保证门清晰可点） ---------- */
@media (max-width: 900px) {
  .ih { perspective: none; }
  .ih__world { transform: none !important; }
  .ih__sky3d, .ih__ceil, .ih__wall, .ih__floor { display: none; }
  .ih__doors { flex-wrap: wrap; gap: 10px; padding: 0 14px; align-content: flex-end; }
  .ih__door { flex: 0 1 30%; height: 40%; }
  .ih__door.is-tall { height: 42%; }
  .ih__plate { top: -20px; }
  .ih__plate b { font-size: 10.5px; }
  .ih__sticker { width: 30px; height: 30px; font-size: 15px; }
  .ih__tree { width: 74px; }
  .ih__planter { display: none; }
  .ih__cat { width: 40px; left: 3%; bottom: 14%; }
  .ih__window--sm { display: none; }
  .ih__hint span { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .ih, .ih.is-entering { transition-duration: 0.16s; }
  .ih__persp { animation: none; }
  .ih__sign { animation: none; }
  .ih__hint-chip { transform: none; }
  .ih__leaf, .ih__cloud, .ih__wall-face, .ih__eave, .ih__window, .ih__tree,
  .ih__cat, .ih__planter, .ih__ground, .ih__sticker { transition: none; }
}
</style>
