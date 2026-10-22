// 取景地图（蓝色地球）视觉验证：切到「取景地图」视图，等地球转起来后截全屏 + 局部放大
// 用法：node scripts/shot_globe.js [baseUrl]
const puppeteer = require('puppeteer-core')

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const BASE = process.argv[2] || 'http://localhost:8080'
const OUT = '.workbuddy/screenshots'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox'],
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 2 },
  })
  const page = await browser.newPage()
  const errors = []
  const failed = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('requestfailed', (r) => failed.push(`${r.url()} :: ${r.failure()?.errorText}`))

  await page.goto(`${BASE}/screen`, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('.stage-tab', { timeout: 30000 })

  // 点「取景地图」tab
  const tabs = await page.$$eval('.stage-tab', (els) =>
    els.map((e) => ({ text: e.textContent.trim(), x: e.getBoundingClientRect().x + e.getBoundingClientRect().width / 2, y: e.getBoundingClientRect().y + e.getBoundingClientRect().height / 2 })))
  const globeTab = tabs.find((t) => t.text.includes('取景地图'))
  if (!globeTab) throw new Error('未找到「取景地图」tab: ' + JSON.stringify(tabs))
  await page.mouse.click(globeTab.x, globeTab.y)

  // 等异步组件 + 纹理加载
  await page.waitForFunction(() => !!document.querySelector('.globe-stage canvas'), { timeout: 30000 })
  await sleep(3200)

  // 量取地球 canvas 的实际尺寸，以及 WebGL 是否真的画出了东西（非透明像素占比）
  const info = await page.evaluate(() => {
    const cv = document.querySelector('.globe-stage canvas')
    const r = cv.getBoundingClientRect()
    const gl = cv.getContext('webgl2') || cv.getContext('webgl')
    const w = cv.width
    const h = cv.height
    const buf = new Uint8Array(w * h * 4)
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf)
    let opaque = 0
    let blueish = 0
    for (let i = 0; i < buf.length; i += 4) {
      if (buf[i + 3] > 8) opaque++
      // 取样：蓝通道明显高于红通道 = 海洋蓝
      if (buf[i + 3] > 40 && buf[i + 2] > buf[i] + 12) blueish++
    }
    const total = w * h
    return {
      canvas: { w: Math.round(r.width), h: Math.round(r.height), px: w + 'x' + h },
      opaqueRatio: +(opaque / total).toFixed(3),
      blueRatio: +(blueish / total).toFixed(3),
      renderer: gl.getParameter(gl.VERSION),
    }
  })
  console.log('MEASURE ' + JSON.stringify(info))

  await page.screenshot({ path: `${OUT}/globe-screen.png` })

  // 局部放大：裁地球区域
  const box = await page.evaluate(() => {
    const cv = document.querySelector('.globe-stage canvas').getBoundingClientRect()
    return { x: Math.round(cv.x), y: Math.round(cv.y), w: Math.round(cv.width), h: Math.round(cv.height) }
  })
  await page.screenshot({ path: `${OUT}/globe-crop.png`, clip: { x: box.x, y: box.y, width: box.w, height: box.h } })

  // 拖拽旋转一帧，确认交互生效
  const cx = box.x + box.w / 2
  const cy = box.y + box.h / 2
  await page.mouse.move(cx + 120, cy)
  await page.mouse.down()
  for (let i = 0; i < 10; i++) { await page.mouse.move(cx + 120 - i * 16, cy); await sleep(16) }
  await page.mouse.up()
  await sleep(700)
  await page.screenshot({ path: `${OUT}/globe-dragged.png` })

  console.log('ERRORS ' + JSON.stringify(errors.slice(0, 5)))
  console.log('FAILED ' + JSON.stringify(failed.filter((f) => !f.includes('favicon')).slice(0, 5)))
  await browser.close()
})().catch((e) => { console.error('FAIL', e.message); process.exit(1) })
