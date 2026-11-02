<!--
  票房分析展厅 · 全宽舞台（参考 itomdev.com/gallery 的相框绳效果）
  ============================================================
  用户 2026-11-01 要求：不要每间数据页都套"左中右三块"，按数据实情调整。
  票房这间的"主角是挂在绳上的全球 TOP 相框"（itomdev 招牌交互），所以：
    · 上方 = 全宽相框绳画廊（BoxOfficeGallery），滚轮漂移、点框看档案
    · 下方 = 两栏附带面板：左「全球票房榜 TOP10」、右「年度票房趋势」
      （这两块原本是左翼/右翼，现在收到展厅底部做配套，腾出全宽给画廊）
  整间房不再有左右两翼，区别于其他"左图右表"的展厅。
-->
<template>
  <div class="box-stage">
    <div class="box-stage__gallery">
      <BoxOfficeGallery
        :gallery="gallery"
        :total-movies="totalMovies"
        :total-revenue="totalRevenue"
        :top-year="topYear"
        :pick="pick"
      />
    </div>
    <div class="box-stage__dock">
      <div class="box-stage__cell box-stage__cell--rank">
        <BoxOfficeRank
          :gallery="gallery"
          :total-movies="totalMovies"
          @pick="(g) => emit('pick', g)"
        />
      </div>
      <div class="box-stage__cell box-stage__cell--trend">
        <BoxOfficeTrend
          :years="years"
          :total-revenue="totalRevenue"
          :total-movies="totalMovies"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
// ============================================================
// 票房分析全宽舞台：画廊（主）+ 底部两栏配套（次）
// ============================================================
import BoxOfficeGallery from './BoxOfficeGallery.vue'
import BoxOfficeRank from './BoxOfficeRank.vue'
import BoxOfficeTrend from './BoxOfficeTrend.vue'

const props = defineProps({
  gallery: { type: Array, default: () => [] },
  totalMovies: { type: Number, default: 0 },
  totalRevenue: { type: Number, default: 0 },
  topYear: { type: Number, default: null },
  years: { type: Array, default: () => [] },
  /* 榜单点选联动：打开画廊里同一部的档案卡 */
  pick: { type: Object, default: null },
})
const emit = defineEmits(['pick'])
</script>

<style scoped>
.box-stage {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 10px;
  /* 抵消 styles/pages.css 里全局同名 .box-stage（盲盒页）的副作用：
     否则会继承 26px 内边距 / 虚线边框 / 渐变底 / 14px 下外边距，
     挤掉底部榜单高度并露出怪边框 */
  padding: 6px;
  margin: 0;
  background: none;
  border: 0;
  border-radius: 0;
  text-align: left;
}
/* 画廊（相框绳）固定占上部：相框约 200px，给到 ~252 让片名/票房完整露出；
   不再 flex:1 抢满，把剩余空间全留给下方两栏榜单，避免只显示 2/10 行。
   下方 dock 现在高度更足（舞台整体加高），可放心给画廊多留一点。 */
.box-stage__gallery { flex: 0 0 clamp(180px, 25vh, 225px); min-height: 0; }
/* 让画廊随舞台收缩（默认 min-height:420 会在窄舞台顶破容器） */
.box-stage__gallery :deep(.bog) { min-height: 0; }

/* 底部两栏配套：全球票房榜 + 年度票房趋势（收编自原左右两翼）。
   flex:1 吃掉画廊让出的全部剩余高度 —— 这样 TOP10 十条 + 趋势图都能完整显示，
   矮屏时榜单内部自行滚动，不再静默裁掉后面几行。 */
.box-stage__dock {
  flex: 1 1 0;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.box-stage__cell {
  min-width: 0;
  min-height: 0;
  padding: 8px 12px 6px;
  border-radius: 16px;
  background: linear-gradient(180deg, #FDFAF3 0%, #F8F2E6 60%, #F3EADA 100%);
  border: 1px solid rgba(139, 69, 19, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85), 0 8px 22px rgba(139, 69, 19, 0.06);
  overflow: hidden;
}
.box-stage__cell--trend { padding-bottom: 10px; }
</style>
