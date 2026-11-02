<template>
  <!--
    ============================================================
    口碑分歧展厅 · 左右分屏（参考 A24 影片展 vs 数据对照）
    ------------------------------------------------------------
    与"左中右三块"不同，这里是一刀切的左右分屏：
      左半 = 观众评分分化榜（A24 海报圆盘展）
      右半 = 上半「豆瓣 vs TMDB 分歧散点」+ 下半「豆瓣口碑」
    两张内容气质迥异，并排对照，一眼看懂"两个平台的口碑不一定一致"。
    ============================================================
  -->
  <div class="diverge-room">
    <section class="dr__left float-card">
      <PolarizingBoard :polarizing="polarizing" />
    </section>
    <div class="dr__right">
      <section class="dr__cell float-card">
        <DivergenceChart :divergence="divergence" />
      </section>
      <section class="dr__cell dr__cell--dbp float-card">
        <div class="dr__cell-h">豆瓣口碑</div>
        <div class="dr__cell-body">
          <DoubanPanel :douban="douban" />
        </div>
      </section>
      <section class="dr__cell dr__cell--gap float-card">
        <GapBoard :divergence="divergence" />
      </section>
    </div>
  </div>
</template>

<script setup>
// ============================================================
// 口碑分歧：左 = 分化榜（A24 圆盘展）；右 = 分歧散点 + 豆瓣口碑 + 平台分歧榜
// ============================================================
import PolarizingBoard from './PolarizingBoard.vue'
import DivergenceChart from './DivergenceChart.vue'
import DoubanPanel from './DoubanPanel.vue'
import GapBoard from './GapBoard.vue'

defineProps({
  divergence: { type: Array, default: () => [] },
  polarizing: { type: Object, default: null },
  douban: { type: Object, default: null },
})
</script>

<style scoped>
.diverge-room {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.dr__left { min-height: 0; overflow: hidden; }

.dr__right {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.dr__cell {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
/* 豆瓣口碑卡（情感环 + 12 行高分榜）内容最高，给它约两倍竖向空间，
   散点图与分歧榜各占一份 —— 三块都不需要滚动就能看全 */
.dr__cell--dbp { flex: 1.95 1 0; }
/* 平台分歧榜：右栏底部，再补一块真实数据 */
.dr__cell--gap { flex: 1.02 1 0; }
.dr__cell-h {
  flex: none;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--u-text);
  letter-spacing: 1px;
  padding-bottom: 8px;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(194, 65, 12, 0.22);
}
.dr__cell-body { flex: 1; min-height: 0; overflow: auto; }

@media (max-width: 1180px) {
  .diverge-room { grid-template-columns: 1fr 1fr; }
}
</style>
