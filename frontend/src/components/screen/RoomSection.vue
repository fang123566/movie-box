<template>
  <!--
    ============================================================
    展厅章节标题 · 策展式节奏
    ------------------------------------------------------------
    每个数据板块前的小节标题：左侧大号编号 01/02/03 + 中文标题 + 英文小字，
    右侧一句引导语。统一"头—展品—数据"的节奏，让长页不再像平铺报表。
    ============================================================
  -->
  <div class="room-section" :class="{ 'room-section--bare': bare }">
    <div class="rs__head">
      <span class="rs__no">{{ no }}</span>
      <div class="rs__titles">
        <h2 class="rs__zh">{{ zh }}</h2>
        <p v-if="en" class="rs__en">{{ en }}</p>
      </div>
      <span class="rs__line" />
    </div>
    <p v-if="lead" class="rs__lead">{{ lead }}</p>
  </div>
</template>

<script setup>
defineProps({
  no: { type: [String, Number], default: '01' },
  zh: { type: String, required: true },
  en: { type: String, default: '' },
  lead: { type: String, default: '' },
  bare: { type: Boolean, default: false },
})
</script>

<style scoped>
.room-section {
  margin: 6px 0 10px;
}
.rs__head {
  display: flex;
  align-items: center;
  gap: 14px;
}
/* 大号章节编号：金橙双色描边，像展品标牌 */
.rs__no {
  flex: none;
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: clamp(28px, 3vw, 42px);
  font-weight: 800;
  line-height: 1;
  background: linear-gradient(120deg, #C2410C, #A67C2E);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  opacity: 0.92;
}
.rs__titles { flex: none; }
.rs__zh {
  margin: 0;
  font-family: var(--u-font-cn, 'Source Han Sans SC'), sans-serif;
  font-size: clamp(16px, 1.5vw, 21px);
  font-weight: 700;
  letter-spacing: 1.2px;
  color: var(--u-text, #3A2E20);
}
.rs__en {
  margin: 2px 0 0;
  font-family: var(--u-font-tech, 'Orbitron'), sans-serif;
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--u-text-2, #7D6B52);
}
.rs__line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, rgba(194, 65, 12, 0.4), transparent);
}
.rs__lead {
  margin: 8px 0 0;
  padding-left: calc(clamp(28px, 3vw, 42px) + 14px);
  font-size: 13px;
  line-height: 1.7;
  color: #5A4632;
}
</style>
