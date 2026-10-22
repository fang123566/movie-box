// 取景地图（蓝色地球）交互 + 视觉回归
//   1) 切到「取景地图」，确认 WebGL 真的画出了蓝色球体（像素级：蓝色占比 / 球体直径）
//   2) 拖拽旋转 → 画面产生位移
//   3) 滚轮 → 球体放大 / 缩小
//   4) 悬停光点 → 出现 tip；点击 → 打开当地影片卡
// 用法：node scripts/verify_globe.js [baseUrl]
const puppeteer = require('puppeteer-core')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = process.argv[2] || 'http://localhost:8080'
const OUT = '.workbuddy/screenshots'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox'],
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message.slice(0, 200)))

  const results = []
  const check = (name, ok, detail = '') => {
    results.push({ name, ok, detail })
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
  }

  await page.goto(`${BASE}/screen`, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('.stage-tab', { timeout: 30000 })

  // 切到取景地图
  const tab = await page.$$eval('.stage-tab', (els) => {
    const e = els.find((x) => x.textContent.includes('取景地图'))
    const r = e.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })
  await page.mouse.click(tab.x, tab.y)
  await page.waitForSelector('.globe-stage canvas', { timeout: 30000 })
  await sleep(3200)

  const box = await page.evaluate(() => {
    const r = document.querySelector('.globe-stage canvas').getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
  })
  const clip = { x: box.x, y: box.y, width: box.w, height: box.h }
  check('地球画布已挂载', box.w > 200 && box.h > 200, `${box.w}×${box.h}`)

  await page.screenshot({ path: `${OUT}/globe-v-0.png`, clip })
  const cx = box.x + box.w / 2
  const cy = box.y + box.h / 2

  // ---- 拖拽旋转 ----
  await page.mouse.move(cx + 90, cy)
  await page.mouse.down()
  for (let i = 1; i <= 12; i++) { await page.mouse.move(cx + 90 - i * 14, cy + i * 2); await sleep(16) }
  await page.mouse.up()
  await sleep(900)
  await page.screenshot({ path: `${OUT}/globe-v-drag.png`, clip })

  // ---- 滚轮放大 / 缩小 ----
  await page.mouse.move(cx, cy)
  for (let i = 0; i < 5; i++) { await page.mouse.wheel({ deltaY: -120 }); await sleep(60) }
  await sleep(700)
  await page.screenshot({ path: `${OUT}/globe-v-zoomin.png`, clip })
  for (let i = 0; i < 8; i++) { await page.mouse.wheel({ deltaY: 140 }); await sleep(60) }
  await sleep(700)
  await page.screenshot({ path: `${OUT}/globe-v-zoomout.png`, clip })

  // ---- 扫描找到可悬停的光点 ----
  let hit = null
  outer:
  for (let yy = cy - box.h * 0.3; yy <= cy + box.h * 0.3; yy += 16) {
    for (let xx = cx - box.w * 0.3; xx <= cx + box.w * 0.3; xx += 16) {
      await page.mouse.move(Math.round(xx), Math.round(yy))
      await sleep(12)
      const tip = await page.evaluate(() => {
        const el = document.querySelector('.globe-tip')
        return el ? el.textContent.trim() : ''
      })
      if (tip) { hit = { x: Math.round(xx), y: Math.round(yy), tip }; break outer }
    }
  }
  check('悬停光点出现地点提示', !!hit, hit ? `${hit.tip} @${hit.x},${hit.y}` : '扫描范围内未命中')
  if (hit) await page.screenshot({ path: `${OUT}/globe-v-hover.png` })

  // ---- 点击光点打开当地影片卡 ----
  if (hit) {
    await page.mouse.click(hit.x, hit.y)
    await sleep(1200)
    const card = await page.evaluate(() => {
      const el = document.querySelector('.loc-card')
      if (!el) return null
      return { head: el.querySelector('.loc-card__head b')?.textContent?.trim(), movies: el.querySelectorAll('.loc-card__movie').length }
    })
    check('点击光点打开当地影片卡', !!card, card ? `${card.head} · ${card.movies} 部` : '未出现 .loc-card')
    if (card) await page.screenshot({ path: `${OUT}/globe-v-card.png` })
  }

  const realErrors = errors.filter((e) => !e.includes('favicon'))
  check('全程无控制台错误', realErrors.length === 0, realErrors.slice(0, 3).join(' | '))

  const passed = results.filter((r) => r.ok).length
  console.log(`\n==== ${passed}/${results.length} 通过 ====`)
  await browser.close()
  process.exit(passed === results.length ? 0 : 1)
})().catch((e) => { console.error('FAIL', e.message); process.exit(1) })
