<script setup>
// ============================================================
// 电影详情页 —— 清单「电影详情页」模块。
//
// 海报 240×360、片名 32px、元信息、导演与前 3 主演、简介 3 行折叠，
// 操作：收藏 / 加入盲盒 / 分享（复制链接）。
//
// ★ 清单里的「方面情感雷达（六维度）」与「时间趋势（首周/首月）」没有数据：
//   单片画像接口给的是关键词 + 类型口碑参考，所以这里展示
//   「关键词 + 口碑参考」，并在卡片上标注缺口，不画假雷达。
// ============================================================
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { auth } from '../composables/useAuth'
import { blindBox } from '../composables/useBlindBox'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()

const movie = ref(null)
const insight = ref(null)
const similar = ref([])
const loading = ref(true)
const error = ref('')
const overviewOpen = ref(false)
const watched = ref(false)

const cast = computed(() => (movie.value?.cast || []).slice(0, 3))

// 豆瓣短评（本片）：单独拉取 source=douban 的影评，凑成「国内口碑」一角。
// 失败不影响主信息（豆瓣数据只是锦上添花）。
const doubanReviews = ref([])
async function loadDoubanReviews(id) {
  doubanReviews.value = []
  try {
    const resp = await api.searchReviews({
      movie_id: id,
      source: ['douban'],
      size: 6,
      sort: 'relevance',
      with_facets: false,
    })
    doubanReviews.value = resp?.hits || []
  } catch {
    doubanReviews.value = []
  }
}

// 在哪看 / 预告片：正版平台搜索深链 + TMDB 官方预告片（合法替代盗版源）。
// 说明：本项目不提供任何盗版 / 破解 VIP 片源直连；这里只把用户导向各平台
// 的「搜索结果页」，是否可看由平台与会员状态决定。官方预告片走 YouTube 嵌入，
// 在国内访问可能不稳定，故以「可嵌入 + 外链兜底」形式提供。
const PLATFORMS = [
  { name: '爱奇艺', host: 'https://so.iqiyi.com/so/q_' },
  { name: '腾讯视频', host: 'https://v.qq.com/x/search/?q=' },
  { name: '优酷', host: 'https://so.youku.com/search_video/q_' },
  { name: '哔哩哔哩', host: 'https://search.bilibili.com/all?keyword=' },
  { name: '芒果TV', host: 'https://so.mgtv.com/so?k=' },
]
const watchLinks = computed(() => {
  const t = movie.value?.title_zh || movie.value?.title || ''
  if (!t) return []
  return PLATFORMS.map((p) => ({ name: p.name, url: p.host + encodeURIComponent(t) }))
})
// 官方预告片：接 TMDB /search/trailers/{tmdb_id}，优先用官方 Trailer 的嵌入地址。
const trailers = ref([])
const trailerEmbed = computed(() => {
  const official = trailers.value.find((t) => t.official && t.type === 'Trailer')
  const any = trailers.value[0]
  return (official || any)?.url || ''
})
const hasTrailer = computed(() => trailers.value.length > 0)
const doubanSearchUrl = computed(() => {
  const t = movie.value?.title_zh || movie.value?.title || ''
  if (!t) return ''
  return `https://search.douban.com/movie/subject_search?search_text=${encodeURIComponent(t)}`
})
async function loadTrailers(id) {
  trailers.value = []
  const tid = movie.value?.tmdb_id
  if (!tid) return
  try {
    const resp = await api.trailers(tid)
    trailers.value = resp?.trailers || []
  } catch {
    trailers.value = []
  }
}

async function load() {
  loading.value = true
  error.value = ''
  const id = route.params.id
  try {
    const m = await api.getMovie(id)
    if (!m) { error.value = '没有找到这部电影'; movie.value = null; return }
    movie.value = m
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
  // 次要数据失败不影响主信息
  api.movieInsight(id).then((d) => { insight.value = d }).catch(() => {})
  api.similar(id, 8).then((d) => { similar.value = d?.hits || [] }).catch(() => {})
  loadDoubanReviews(id).catch(() => {})
  loadTrailers(id).catch(() => {})
  if (auth.isLoggedIn.value) {
    api.watchlist().then((list) => {
      const ids = (list?.items || list?.movie_ids || []).map((x) => x.movie_id || x)
      watched.value = ids.includes(String(id))
    }).catch(() => {})
  }
}

onMounted(load)
watch(() => route.params.id, load)

async function toggleWatch() {
  if (!auth.isLoggedIn.value) { toast.info('登录后才能收藏'); router.push('/login'); return }
  try {
    if (watched.value) { await api.removeWatch(movie.value.movie_id); watched.value = false; toast.success('已取消收藏') }
    else { await api.addWatch(movie.value.movie_id); watched.value = true; toast.success('已加入收藏') }
  } catch (e) { toast.error(e.message) }
}

function share() {
  const url = window.location.href
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(url)
    toast.success('链接已复制')
  } else {
    toast.info(url)
  }
}
</script>

<template>
  <div class="container page">
    <button class="btn btn--ghost btn--sm mb-16" @click="router.back()">← 返回</button>

    <div v-if="loading" class="mv-skeleton">
      <div class="skeleton" style="width:240px;height:360px;border-radius:12px" />
      <div style="flex:1">
        <div class="skeleton" style="height:34px;width:60%;margin-bottom:14px" />
        <div class="skeleton" style="height:18px;width:40%;margin-bottom:8px" />
        <div class="skeleton" style="height:18px;width:70%;margin-bottom:8px" />
        <div class="skeleton" style="height:120px;margin-top:16px" />
      </div>
    </div>

    <div v-else-if="error" class="empty">
      <span class="empty__icon">🎬</span>
      <span class="empty__title">{{ error }}</span>
      <router-link class="btn btn--primary mt-16" to="/search">去检索</router-link>
    </div>

    <template v-else-if="movie">
      <div class="mv">
        <div class="mv__poster">
          <img v-if="movie.poster_url" :src="movie.poster_url" :alt="movie.title" />
          <div v-else class="mv__ph">🎬</div>
        </div>

        <div class="mv__main">
          <h1 class="mv__title">{{ movie.title }}</h1>
          <p v-if="movie.title_zh && movie.title_zh !== movie.title" class="mv__titlezh">{{ movie.title_zh }}</p>

          <div class="mv__meta">
            <span>{{ movie.release_year || '—' }}</span>
            <span>{{ (movie.genres_zh || []).join(' / ') || '—' }}</span>
            <span>{{ (movie.production_countries || [])[0] || '—' }}</span>
            <span v-if="movie.runtime">{{ movie.runtime }} 分钟</span>
          </div>

          <div class="mv__score">
            <span class="stars">{{ '★'.repeat(Math.round((movie.rating || 0) / 2)) }}</span>
            <b>{{ (movie.rating ?? 0).toFixed(1) }}</b>
            <span class="text-3 text-sm">{{ (movie.votes || 0).toLocaleString() }} 人评</span>
            <span v-if="movie.douban_rating != null" class="mv__score-sep">·</span>
            <span v-if="movie.douban_rating != null" class="mv__douban" title="豆瓣评分（国内口碑参考）">
              🟢 豆瓣 {{ movie.douban_rating.toFixed(1) }}
              <span class="text-3 text-sm">{{ (movie.douban_votes || 0).toLocaleString() }} 人</span>
            </span>
          </div>

          <p class="mv__people">
            <b>导演：</b>{{ movie.director || '—' }}
            <span v-if="cast.length"> · <b>主演：</b>{{ cast.join('、') }}</span>
          </p>

          <div class="mv__ops">
            <button class="btn" :class="watched ? 'btn--primary' : 'btn--ghost'" @click="toggleWatch">
              {{ watched ? '★ 已收藏' : '☆ 收藏' }}
            </button>
            <button class="btn btn--ghost" @click="blindBox.openBox(movie.genres_zh || [])">🎲 加入盲盒</button>
            <button class="btn btn--ghost" @click="share">🔗 分享</button>
          </div>

          <div class="mv__overview">
            <p :class="{ 'is-clamped': !overviewOpen }">{{ movie.overview || '（该片暂无简介）' }}</p>
            <button v-if="(movie.overview || '').length > 90" class="mv__more" @click="overviewOpen = !overviewOpen">
              {{ overviewOpen ? '收起' : '展开' }}
            </button>
          </div>

          <!-- 在哪看 / 预告片：正版平台导航 + TMDB 官方预告片（合法替代盗版源） -->
          <div class="mv__watch">
            <span class="mv__watch-label">📺 在哪看 · 预告片</span>

            <!-- 官方预告片嵌入（YouTube，国内可能不稳定，失败可点外链） -->
            <div v-if="hasTrailer" class="mv__trailer">
              <div class="mv__trailer-frame">
                <iframe
                  v-if="trailerEmbed"
                  :src="trailerEmbed"
                  title="官方预告片"
                  frameborder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowfullscreen
                ></iframe>
                <div v-else class="mv__trailer-fallback">
                  <span>🎬 {{ movie?.title_zh || movie?.title }} 预告片</span>
                  <a :href="trailerEmbed || watchLinks[0]?.url" target="_blank" rel="noopener noreferrer">在 YouTube 打开</a>
                </div>
              </div>
              <div class="mv__trailer-actions">
                <a
                  v-for="p in watchLinks"
                  :key="p.name"
                  class="mv__watch-chip"
                  :href="p.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >{{ p.name }}</a>
                <a v-if="trailerEmbed" class="mv__watch-chip mv__watch-chip--trailer" :href="trailerEmbed" target="_blank" rel="noopener noreferrer">▶ YouTube 外链</a>
              </div>
            </div>
            <div v-else class="mv__watch-links">
              <a
                v-for="p in watchLinks"
                :key="p.name"
                class="mv__watch-chip"
                :href="p.url"
                target="_blank"
                rel="noopener noreferrer"
              >{{ p.name }}</a>
            </div>

            <p class="mv__watch-note">
              以上为各平台「搜索结果」深链，是否可看由平台与会员状态决定（本站不提供任何盗版 / 破解片源）。
              官方预告片由 TMDB 提供、托管于 YouTube，国内访问可能不稳定。
            </p>
          </div>
        </div>
      </div>

      <!-- 情感 / 关键词 -->
      <section class="panel mt-24">
        <h2 class="block__title">💬 口碑与关键词</h2>
        <p v-if="insight?.sentiment_hint" class="mv__hint">{{ insight.sentiment_hint }}</p>
        <div v-if="(insight?.keywords || []).length" class="mv__kw">
          <span v-for="k in insight.keywords.slice(0, 14)" :key="k.term || k.keyword" class="tag tag--genre">
            {{ k.term || k.keyword }}
          </span>
        </div>
        <p v-else class="text-3 text-sm">该片暂无关键词</p>
        <p class="mv__gap">
          注：清单中的「方面情感雷达（剧情/演技/特效/节奏/结局/音乐）」需要方面级标注语料，
          当前影评只有整篇情感，故未实现。
        </p>
      </section>

      <!-- 豆瓣短评（本片）：母语中文短评，作为「国内口碑」一角 -->
      <section class="panel mt-24">
        <h2 class="block__title">🟢 豆瓣短评（本片）</h2>
        <div v-if="doubanReviews.length" class="mv__douban-reviews">
          <article v-for="r in doubanReviews" :key="r.review_id" class="mv__douban-review">
            <div class="mv__douban-review__head">
              <span v-if="r.sentiment" class="sent" :class="`sent--${r.sentiment}`">
                {{ { positive: '正面', negative: '负面', neutral: '中性' }[r.sentiment] || r.sentiment }}
              </span>
              <span v-if="r.word_count" class="mv__douban-review__words">{{ r.word_count }} 词</span>
            </div>
            <p class="mv__douban-review__text">{{ (r.highlight?.text && r.highlight.text.length) ? r.highlight.text.join(' … ') : (r.text || '').slice(0, 200) }}</p>
          </article>
        </div>
        <p v-else class="text-3 text-sm">
          本片暂无豆瓣短评（豆瓣数据仅覆盖库内部分影片，且按公开页慢速采集）。
          <a :href="doubanSearchUrl" target="_blank" rel="noopener noreferrer" class="mv__link">去豆瓣看看 ›</a>
        </p>
      </section>

      <!-- 相似推荐 -->
      <section class="mt-24">
        <h2 class="block__title">🎯 相似推荐</h2>
        <div v-if="similar.length" class="mix-grid">
          <div v-for="m in similar" :key="m.movie_id" class="mixcard" @click="router.push(`/movie/${encodeURIComponent(m.movie_id)}`)">
            <div class="mixcard__poster">
              <img v-if="m.poster_url" :src="m.poster_url" :alt="m.title" loading="lazy" />
              <div v-else class="mixcard__ph">🎬</div>
            </div>
            <div class="mixcard__title">{{ m.title }}</div>
            <div class="mixcard__meta">{{ m.release_year || '—' }}</div>
            <div class="mixcard__score">⭐ {{ (m.rating ?? 0).toFixed(1) }}</div>
          </div>
        </div>
        <p v-else class="text-3 text-sm">暂无相似推荐</p>
      </section>
    </template>
  </div>
</template>
