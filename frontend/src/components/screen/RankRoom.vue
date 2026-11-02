<template>
  <!--
    ============================================================
    口碑排名展厅 · 编辑式排版（参考 A24 编辑页：大图主导 + 侧栏精选）
    ------------------------------------------------------------
    与"左中右三块"不同：这里是一张占满主区的口碑变化大图（BumpChart），
    右上一块窄卡做「编辑精选 · 豆瓣口碑」，像杂志的副栏。两卡都用
    手绘纸框 + 硬阴影，直接铺在暖白纸面上（不含左右两翼）。
    ============================================================
  -->
  <div class="rank-room">
    <section class="rr__main float-card">
      <BumpChart :matrix="matrix" />
    </section>
    <aside class="rr__side float-card">
      <div class="rr__side-h">编辑精选 · 豆瓣口碑</div>
      <div class="rr__side-body">
        <DoubanPanel :douban="douban" />
      </div>
      <div class="rr__side-h rr__side-h--2">类型口碑榜</div>
      <div class="rr__side-body rr__side-body--2">
        <GenreRankCard :by-genre="sentiment?.by_genre || []" />
      </div>
    </aside>
  </div>
</template>

<script setup>
// ============================================================
// 口碑排名：主图（BumpChart） + 侧栏精选（DoubanPanel + 类型口碑榜）
// ============================================================
import BumpChart from './BumpChart.vue'
import DoubanPanel from './DoubanPanel.vue'
import GenreRankCard from './GenreRankCard.vue'

defineProps({
  matrix: { type: Object, default: null },
  douban: { type: Object, default: null },
  sentiment: { type: Object, default: null },
})
</script>

<style scoped>
.rank-room {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 14px;
}
.rr__main { min-height: 0; overflow: hidden; }

.rr__side {
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.rr__side-h {
  flex: none;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--u-text);
  letter-spacing: 1px;
  padding-bottom: 4px;
  margin-bottom: 3px;
  border-bottom: 1px solid rgba(194, 65, 12, 0.22);
}
.rr__side-h--2 { margin-top: 5px; }
/* 两卡都含 8 行列表：缩紧两节标题的留白（省出 ~19px 给列表），
   再按 1.32 / 1.0 分配 —— 两份都刚好够高，确保两张榜 8 行完整露出 */
.rr__side-body { flex: 1.32 1 0; min-height: 0; overflow: auto; }
.rr__side-body--2 { flex: 1 1 0; min-height: 0; overflow: auto; }

@media (max-width: 1180px) {
  .rank-room { grid-template-columns: 1fr 260px; }
}
</style>
