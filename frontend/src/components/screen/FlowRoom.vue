<template>
  <!--
    ============================================================
    年代流向展厅 · 上主图 + 下双栏（参考 itomdev 一张大图配两张副卡）
    ------------------------------------------------------------
    与"左中右三块"不同：上方一整张类型→年代桑基流向图为主视觉，下方并排两张
    手绘副卡——左「年代故事」（StoryTimeline）、右「地区画像」（RegionsPanel），
    像展览里的两块说明牌，不再塞进左右两翼。
    ============================================================
  -->
  <div class="flow-room">
    <section class="fr__top float-card">
      <SankeyFlow :matrix="matrix" />
    </section>
    <div class="fr__bottom">
      <section class="fr__cell float-card">
        <StoryTimeline :trends="trends" />
      </section>
      <section class="fr__cell float-card">
        <CoveragePanel :douban="douban" />
      </section>
      <section class="fr__cell float-card">
        <RegionsPanel :regions="regions" />
      </section>
    </div>
  </div>
</template>

<script setup>
// ============================================================
// 年代流向：桑基主图 + 年代故事 / 预告覆盖 / 地区画像 三副卡
// ============================================================
import SankeyFlow from './SankeyFlow.vue'
import StoryTimeline from './StoryTimeline.vue'
import CoveragePanel from './CoveragePanel.vue'
import RegionsPanel from './RegionsPanel.vue'

defineProps({
  matrix: { type: Object, default: null },
  trends: { type: Object, default: null },
  regions: { type: Object, default: null },
  douban: { type: Object, default: null },
})
</script>

<style scoped>
.flow-room {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.fr__top {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}
.fr__bottom {
  flex: 1.5 1 0;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}
.fr__cell { min-height: 0; overflow: auto; }
</style>
