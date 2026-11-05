import { onBeforeUnmount, onMounted } from 'vue'

/**
 * 滚动揭示（scroll-reveal）：给展厅里「首屏以下」的板块加进入视口时的
 * 错峰淡入上移动画，让可纵向滚动的长数据页有逐层展开的高级感。
 *
 * 用法：在展厅根节点挂 ref="root"，给目标板块 class="u-reveal"（可配 style="--d:.1s" 错峰），
 *       然后 useReveal(root)。样式在 styles/universe.css 的 .u-reveal。
 *
 * 安全红线：
 *   · 不支持 IntersectionObserver 时立即全部显示 —— 绝不把内容藏没；
 *   · 一旦揭示就 unobserve（is-in 常驻），回滚不会反复触发；
 *   · 只挂「非 float-card 的容器」，避免和卡片自身的进场动画抢 transform/opacity。
 */
export function useReveal(rootRef) {
  let observer = null

  const revealAll = (root) =>
    root.querySelectorAll('.u-reveal').forEach((el) => el.classList.add('is-in'))

  onMounted(() => {
    const root = rootRef && rootRef.value
    if (!root) return
    if (!('IntersectionObserver' in window)) { revealAll(root); return }

    const targets = [...root.querySelectorAll('.u-reveal')]
    if (!targets.length) return

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in')
            observer.unobserve(entry.target)
          }
        }
      },
      // 提前一点触发，滚到位时动画已基本播完，不会出现「先空白再跳出」
      { threshold: 0.1, rootMargin: '0px 0px -6% 0px' }
    )
    targets.forEach((el) => observer.observe(el))
  })

  onBeforeUnmount(() => { observer && observer.disconnect() })
}
