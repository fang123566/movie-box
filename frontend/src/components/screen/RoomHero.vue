<template>
  <!--
    ============================================================
    展厅 Hero · 策展式信息起点
    ------------------------------------------------------------
    每间数据展厅顶部统一的大标题区：左侧展示字标题 + 英文副题 + 一句洞察导语，
    右侧 3-4 个核心真实指标（数字滚动进场）。用于把"报表式长页"升级为有叙事起点的策展页。
    数字全部来自父组件传入的真实聚合（拒绝硬编码）。
    ============================================================
  -->
  <header class="room-hero">
    <div class="rh__glow" aria-hidden="true" />
    <div class="rh__left">
      <div class="rh__kicker">
        <span class="rh__icon">{{ icon }}</span>
        <span class="rh__kicker-zh">{{ kicker }}</span>
      </div>
      <h1 class="rh__title">{{ title }}</h1>
      <p class="rh__en">{{ en }}</p>
      <p class="rh__lead">{{ lead }}</p>
      <div v-if="tags && tags.length" class="rh__tags">
        <span v-for="(t, i) in tags" :key="i" class="rh__tag">{{ t }}</span>
      </div>
    </div>
    <div v-if="stats && stats.length" class="rh__stats">
      <div v-for="(s, i) in stats" :key="i" class="rh__stat">
        <div class="rh__num">
          <RollingNumber :value="s.value" :decimals="s.decimals || 0" :duration="s.duration || 1500" />
          <span v-if="s.suffix" class="rh__suffix">{{ s.suffix }}</span>
        </div>
        <div class="rh__label">{{ s.label }}</div>
      </div>
      <div class="rh__cue" aria-hidden="true">
        <span class="rh__cue-arrow">↓</span>
        <span class="rh__cue-text">下滑展开展品</span>
      </div>
    </div>
  </header>
</template>

<script setup>
// 展厅 Hero（独立的策展头，四间数据页复用）
import RollingNumber from './RollingNumber.vue'

defineProps({
  icon: { type: String, default: '' },
  kicker: { type: String, default: '' },
  title: { type: String, required: true },
  en: { type: String, default: '' },
  lead: { type: String, default: '' },
  // 左列策展关键词标签（填补标题区、强化引导）
  tags: { type: Array, default: () => [] },
  // 每项：{ value:Number, suffix?:String, label:String, decimals?:Number, duration?:Number }
  stats: { type: Array, default: () => [] },
})
</script>

<style scoped>
.room-hero {
  position: relative;
  /* 压在固定海报墙背景层（z-index:1）之上：Hero 是实心纸面入口，不蒙海报；
     下方数据卡仍保持半透明透出海报墙的策展设计 */
  z-index: 2;
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  align-items: center;
  gap: 28px;
  margin: 4px 0 24px;
  padding: 24px 32px 26px;
  border-radius: 18px;
  /* 近乎实心的纸面，隔绝背后雾化海报透出，保证标题/标签对比度稳定 */
  background:
    linear-gradient(135deg, rgba(254, 252, 247, 1), rgba(249, 243, 229, 0.99));
  border: 1.4px solid rgba(139, 69, 19, 0.22);
  box-shadow:
    0 18px 46px rgba(120, 90, 50, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  overflow: hidden;
}
/* 暖金光晕：左上角的策展灯光，暗示"这里是展厅入口" */
.room-hero__glow {
  position: absolute;
  left: -120px;
  top: -140px;
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(194, 65, 12, 0.16), rgba(166, 124, 46, 0.08) 45%, transparent 70%);
  pointer-events: none;
}

.rh__kicker {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: 11px;
  letter-spacing: 2.4px;
  color: var(--u-orange-deep, #9A3412);
  text-transform: uppercase;
}
.rh__icon {
  font-size: 16px;
  filter: drop-shadow(0 0 8px rgba(194, 65, 12, 0.2));
}
.rh__kicker-zh { letter-spacing: 1px; }

/* 展示字标题：中文衬线感大字，clamp 响应式，层次分明 */
.rh__title {
  margin: 10px 0 4px;
  font-family: var(--u-font-cn, 'Source Han Sans SC'), sans-serif;
  font-size: clamp(30px, 3.8vw, 50px);
  font-weight: 800;
  line-height: 1.06;
  letter-spacing: 1px;
  background: linear-gradient(120deg, #7C2D12 0%, #9A3412 42%, #B45309 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.rh__en {
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--u-text-2, #7D6B52);
  text-transform: uppercase;
  margin: 0 0 12px;
}
.rh__lead {
  margin: 0;
  max-width: 46em;
  font-size: clamp(13px, 1.1vw, 15px);
  line-height: 1.75;
  color: var(--u-text, #3A2E20);
}
/* 左列策展关键词标签：小圆角橙棕 chip，填补标题区并强化引导 */
.rh__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.rh__tag {
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #7C2D12;
  padding: 5px 12px;
  background: rgba(194, 65, 12, 0.12);
  border: 1px solid rgba(194, 65, 12, 0.34);
  border-radius: 999px;
}

/* 右侧指标胶囊：数字滚动 + 标签，建立第一视觉锚点 */
.rh__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 14px;
  justify-content: flex-end;
  align-items: center;
}
.rh__stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 104px;
  padding: 12px 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(139, 69, 19, 0.28);
  border-radius: 14px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9), 0 5px 16px rgba(120, 90, 50, 0.12);
}
.rh__num {
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: clamp(26px, 3vw, 40px);
  font-weight: 800;
  line-height: 1.02;
  color: #7C2D12;
}
.rh__suffix {
  font-size: 0.5em;
  font-weight: 700;
  color: var(--u-text-2, #7D6B52);
  margin-left: 3px;
}
.rh__label {
  margin-top: 6px;
  font-size: 12px;
  letter-spacing: 1px;
  color: rgba(122, 92, 48, 0.95);
  font-weight: 500;
}
/* 下滑指引：呼应滚动揭示动效，填补右下留白 */
.rh__cue {
  align-self: flex-end;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
  font-size: 11px;
  letter-spacing: 1.5px;
  font-weight: 600;
  color: #6B4E2E;
}
.rh__cue-arrow {
  font-size: 15px;
  font-weight: 700;
  color: #8B2D0A;
  animation: rh-bob 1.8s ease-in-out infinite;
}
@keyframes rh-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(4px); }
}
@media (prefers-reduced-motion: reduce) {
  .rh__cue-arrow { animation: none; }
}

/* 窄屏：单栏堆叠，指标横排到底部 */
@media (max-width: 900px) {
  .room-hero {
    grid-template-columns: 1fr;
    gap: 18px;
    padding: 18px 18px 20px;
  }
  .rh__stats {
    justify-content: flex-start;
    gap: 12px 18px;
  }
  .rh__stat {
    align-items: flex-start;
    padding: 9px 0 0;
    background: none;
    border: none;
    border-top: 1px solid rgba(194, 65, 12, 0.18);
    border-radius: 0;
  }
}

/* 入场：标题区从左侧浮入、指标从右侧浮入（每次进房重新挂载自然重播） */
.room-hero {
  animation: rh-in 0.7s cubic-bezier(.16, .84, .44, 1) both;
}
@keyframes rh-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .room-hero { animation: none; }
}
</style>
