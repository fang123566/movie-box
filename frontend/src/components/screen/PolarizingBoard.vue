<template>
  <!--
    ============================================================
    口碑分歧展厅 · 观众评分分化榜（左翼/右翼面板）
    ------------------------------------------------------------
    与中央「豆瓣 vs TMDB 跨平台分歧」互补：这条讲观众**内部**分歧——
    同一部片，有人打满分、有人打最低分。按评分标准差排名。
    · 上：可点榜单（标准差越大越两极分化）
    · 下：所选影片的真实好评引文 + 差评引文（A24 pull-quote 手法）
    · 交互：点片 → 引文交叉淡入；悬停榜单行高亮
    ============================================================
  -->
  <div class="pb">
    <div class="pb__head">
      <div class="pb__head-l">
        <i class="pb__bar" />
        <span class="pb__zh">观众评分分化榜</span>
        <span class="pb__en">RATING SPLIT</span>
      </div>
      <span class="pb__note">{{ items.length }} 部</span>
    </div>

    <!-- 榜单 -->
    <div class="pb__list" role="listbox" aria-label="评分波动最大的影片">
      <button
        v-for="(it, i) in items"
        :key="it.movie_id"
        class="pb__row"
        :class="{ 'is-on': i === sel }"
        type="button"
        role="option"
        :aria-selected="i === sel"
        @click="sel = i"
      >
        <span class="pb__no">{{ i + 1 }}</span>
        <span class="pb__meta">
          <b>{{ it.title }}</b>
          <small>{{ it.review_count }} 条评价 · 均分 {{ fmt(it.avg_rating) }}</small>
        </span>
        <span class="pb__sd">{{ fmt(it.std_dev) }}</span>
      </button>
    </div>

    <!-- 引文：所选影片的真实好评 / 差评 -->
    <Transition name="pb-fade" mode="out-in">
      <div v-if="cur" :key="cur.movie_id" class="pb__quotes">
        <div class="pb__film">
          <b>{{ cur.title }}</b>
          <span v-if="cur.year">{{ cur.year }} · </span>评分波动 {{ fmt(cur.std_dev) }}
        </div>

        <blockquote v-if="cur.pos_quote" class="pb__q pb__q--pos">
          <p>{{ cur.pos_quote.text }}</p>
          <footer>好评 · 该观众打 {{ scoreOf(cur.pos_quote.rating) }} 分</footer>
        </blockquote>
        <blockquote v-if="cur.neg_quote" class="pb__q pb__q--neg">
          <p>{{ cur.neg_quote.text }}</p>
          <footer>差评 · 该观众打 {{ scoreOf(cur.neg_quote.rating) }} 分</footer>
        </blockquote>
        <div v-if="!cur.pos_quote && !cur.neg_quote" class="pb__empty">该片暂无足够长的引文</div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
// ============================================================
// 观众评分分化榜（数据 /insights/polarizing，真实引文）
// ============================================================
import { computed, ref } from 'vue'

const props = defineProps({
  polarizing: { type: Object, default: null },
})

const items = computed(() => props.polarizing?.items || [])
const sel = ref(0)
const cur = computed(() => items.value[sel.value] || null)

const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toFixed(2))
const scoreOf = (r) => (r === null || r === undefined ? '?' : Math.round(Number(r)))
</script>

<style scoped>
.pb { display: flex; flex-direction: column; height: 100%; min-height: 0; padding: 4px 2px; }

.pb__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.pb__head-l { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.pb__bar { width: 4px; height: 15px; border-radius: 2px; background: var(--u-orange); }
.pb__zh { font-size: 14.5px; font-weight: 700; color: var(--u-text); }
.pb__en { font-family: var(--u-font-tech); font-size: 9px; letter-spacing: .16em; color: var(--u-text-2); }
.pb__note { font-size: 11.5px; color: var(--u-gold); font-weight: 600; white-space: nowrap; }

/* ---------- 榜单 ---------- */
.pb__list {
  flex: none;
  max-height: 46%;
  overflow-y: auto;
  scrollbar-width: thin;
  border: 1px solid rgba(154, 96, 40, .18);
  border-radius: 6px;
  background: rgba(255, 253, 247, .5);
  margin-bottom: 10px;
}
.pb__row {
  display: grid;
  grid-template-columns: 22px 1fr auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-bottom: 1px dashed rgba(154, 96, 40, .16);
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background .15s ease;
}
.pb__row:last-child { border-bottom: 0; }
.pb__row:hover { background: rgba(166, 124, 46, .1); }
.pb__row.is-on { background: linear-gradient(90deg, rgba(194, 65, 12, .12), rgba(166, 124, 46, .06)); }
.pb__no { font-family: "Kaiti SC", KaiTi, STKaiti, serif; font-size: 16px; font-weight: 700; color: var(--u-gold); }
.pb__row.is-on .pb__no { color: var(--u-orange); }
.pb__meta { min-width: 0; }
.pb__meta b {
  display: block;
  font-size: 12.5px; font-weight: 700; color: var(--u-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pb__meta small { font-size: 10px; color: var(--u-text-2); }
.pb__sd { font-family: var(--u-font-tech); font-size: 13px; font-weight: 700; color: var(--u-orange); }

/* ---------- 引文（A24 pull-quote） ---------- */
.pb__quotes { flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; }
.pb__film { font-size: 11px; color: var(--u-text-2); margin-bottom: 8px; }
.pb__film b { font-size: 13px; color: var(--u-text); margin-right: 6px; }

.pb__q {
  position: relative;
  margin: 0 0 10px;
  padding: 10px 12px 9px 30px;
  background: rgba(246, 241, 230, .55);
  border-radius: 0 8px 8px 0;
}
.pb__q::before {
  content: '“';
  position: absolute;
  left: 8px; top: 2px;
  font-family: "Kaiti SC", KaiTi, STKaiti, serif;
  font-size: 30px;
  line-height: 1;
}
.pb__q--pos { border-left: 3px solid var(--u-orange); }
.pb__q--pos::before { color: var(--u-orange); }
.pb__q--neg { border-left: 3px solid var(--u-cyan); }
.pb__q--neg::before { color: var(--u-cyan); }
.pb__q p {
  font-family: "Kaiti SC", KaiTi, STKaiti, "Songti SC", serif;
  font-size: 13px;
  font-style: italic;
  line-height: 1.6;
  color: #3A2E20;
  margin: 0 0 6px;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pb__q footer { font-size: 10px; letter-spacing: .03em; color: var(--u-text-2); }
.pb__q--pos footer b, .pb__q--pos footer { color: var(--u-orange); }
.pb__q--neg footer { color: var(--u-cyan); }
.pb__q footer { font-weight: 600; }

.pb__empty { font-size: 11.5px; color: var(--u-text-2); padding: 16px 4px; text-align: center; }

/* 交叉淡入 */
.pb-fade-enter-active, .pb-fade-leave-active { transition: opacity .22s ease, transform .22s ease; }
.pb-fade-enter-from { opacity: 0; transform: translateY(8px); }
.pb-fade-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  .pb-fade-enter-active, .pb-fade-leave-active { transition: none; }
}
</style>
