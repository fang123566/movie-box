/**
 * 验证「采集流水线演示中心」（同学贡献的合并结果）
 * 用法：NODE_PATH=frontend/node_modules node scripts/verify_crawl_demo.js http://localhost:8080
 */
const puppeteer = require('puppeteer-core')

const BASE = process.argv[2] || 'http://localhost:8080'
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const SHOT = '.workbuddy/screenshots'

let pass = 0
let fail = 0
const errors = []
function check(name, ok, detail = '') {
  if (ok) { pass++; console.log(`  ✓ ${name}${detail ? ' — ' + detail : ''}`) }
  else { fail++; console.log(`  ✗ ${name}${detail ? ' — ' + detail : ''}`) }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox'],
    defaultViewport: { width: 1600, height: 1000 },
  })
  const page = await browser.newPage()
  page.on('pageerror', (e) => errors.push(String(e.message)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

  console.log('\n=== 采集演示页验证 ===')
  await page.goto(`${BASE}/dashboard/crawl`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('.crawl-demo', { timeout: 20000 })
  await sleep(600)

  const initial = await page.evaluate(() => ({
    title: document.title,
    h1: document.querySelector('.crawl-demo h1')?.textContent.trim(),
    nodes: document.querySelectorAll('.pipeline-node').length,
    metrics: document.querySelectorAll('.crawl-metrics article').length,
    logs: document.querySelectorAll('.terminal-line').length,
    startDisabled: document.querySelector('.crawl-demo__button--primary')?.disabled,
    resetDisabled: [...document.querySelectorAll('.crawl-demo__button')][1]?.disabled,
  }))
  check('标题正确', initial.title.includes('爬虫采集流水线'), initial.title)
  check('页面大标题', /爬虫采集流水线演示中心/.test(initial.h1 || ''), initial.h1)
  check('5 个流水线节点', initial.nodes === 5, `${initial.nodes}`)
  check('4 个指标卡', initial.metrics === 4, `${initial.metrics}`)
  check('初始无日志', initial.logs === 0, `${initial.logs}`)
  check('初始开始按钮可用', initial.startDisabled === false)
  check('初始重置按钮禁用', initial.resetDisabled === true)

  await page.screenshot({ path: `${SHOT}/crawl_demo_initial.png` })

  console.log('\n=== 启动演示 ===')
  await page.click('.crawl-demo__button--primary')
  await sleep(3400)
  const running = await page.evaluate(() => ({
    active: document.querySelectorAll('.pipeline-node.is-active').length,
    logs: document.querySelectorAll('.terminal-line').length,
    collected: document.querySelector('.crawl-metrics article strong')?.textContent,
    buttons: [...document.querySelectorAll('.crawl-demo__button')].map((b) => b.disabled),
  }))
  check('流水线节点激活', running.active >= 1, `active=${running.active}`)
  check('日志开始滚动', running.logs >= 3, `${running.logs} 行`)
  check('采集计数增长', Number(running.collected) >= 1, `collected=${running.collected}`)
  check('运行中开始按钮禁用', running.buttons[0] === true)
  check('运行中重置按钮可用', running.buttons[1] === false)
  await page.screenshot({ path: `${SHOT}/crawl_demo_running.png` })

  console.log('\n=== 重置演示 ===')
  await page.evaluate(() => [...document.querySelectorAll('.crawl-demo__button')][1].click())
  await sleep(600)
  const reset = await page.evaluate(() => ({
    logs: document.querySelectorAll('.terminal-line').length,
    collected: document.querySelector('.crawl-metrics article strong')?.textContent,
    active: document.querySelectorAll('.pipeline-node.is-active').length,
  }))
  check('日志清空', reset.logs === 0, `${reset.logs}`)
  check('指标归零', reset.collected === '0', reset.collected)
  check('节点取消激活', reset.active === 0, `${reset.active}`)

  console.log('\n=== 导航入口 ===')
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle2' })
  await sleep(500)
  const nav = await page.evaluate(() => {
    const a = [...document.querySelectorAll('a')].find((x) => x.textContent.includes('采集演示'))
    return { exists: !!a, href: a?.getAttribute('href') }
  })
  check('导航有采集演示入口', nav.exists, nav.href)
  if (nav.exists) {
    await page.evaluate(() => [...document.querySelectorAll('a')].find((x) => x.textContent.includes('采集演示')).click())
    await sleep(1200)
    const url = await page.url()
    check('点击导航跳转正确', url.includes('/dashboard/crawl'), url)
  }

  check('0 控制台错误', errors.length === 0, errors.slice(0, 3).join(' | '))

  console.log(`\n结果: ${pass} 通过 / ${fail} 失败`)
  await browser.close()
  process.exit(fail === 0 ? 0 : 1)
})().catch((e) => { console.error(e); process.exit(1) })
