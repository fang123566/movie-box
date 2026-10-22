// ============================================================
// 影评洞察馆 · 大厅/房间导航回归（/screen）
// 用法：NODE_PATH=<frontend/node_modules> node scripts/verify_house.js http://localhost:8080
//
// 覆盖：大厅渲染 · 六扇门 · 门牌悬停 · 推门进展厅 · 展厅隔离（无串门/门牌直达跨厅入口）·
//       回大厅 · 展厅面板/影评流 · 3D 层按模式压暗 · 各房面板对应 · 移动端无溢出 · 0 报错
// ============================================================
const puppeteer = require('puppeteer-core')
const fs = require('fs')
const path = require('path')

const BASE = process.argv[2] || 'http://localhost:8080'
const OUT = path.resolve(__dirname, '..', '.workbuddy', 'screenshots')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

let pass = 0
let fail = 0
function check(name, ok, extra = '') {
  if (ok) { pass++; console.log(`  ✓ ${name}${extra ? ' — ' + extra : ''}`) }
  else { fail++; console.log(`  ✗ ${name}${extra ? ' — ' + extra : ''}`) }
}

;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900 },
  })
  const page = await browser.newPage()
  const errors = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('pageerror', (e) => errors.push(String(e)))

  console.log(`\n影评洞察馆回归 · ${BASE}\n`)
  await page.goto(BASE + '/screen', { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('.ih', { timeout: 20000 })
  await sleep(1400)

  /* ---------- 大厅 ---------- */
  const house = await page.evaluate(() => {
    const ih = document.querySelector('.ih')
    const r = ih.getBoundingClientRect()
    const doors = [...document.querySelectorAll('.ih__door')]
    return {
      w: Math.round(r.width),
      h: Math.round(r.height),
      doors: doors.length,
      plates: [...document.querySelectorAll('.ih__plate b')].map((e) => e.textContent.trim()),
      wall: !!document.querySelector('.ih__wall-face svg'),
      sign: (document.querySelector('.ih__sign-zh') || {}).textContent,
      hudHidden: getComputedStyle(document.querySelector('.stage-dock')).display === 'none',
      topBarShown: getComputedStyle(document.querySelector('.top-bar')).display !== 'none',
      canvasDim: document.querySelector('.three-canvas-layer').classList.contains('is-dim'),
      world: !!document.querySelector('.ih__world'),
      world3d: getComputedStyle(document.querySelector('.ih')).perspective !== 'none',
      doorW: doors.length ? Math.round(doors[0].getBoundingClientRect().width) : 0,
    }
  })
  check('大厅渲染满屏', house.w > 1200 && house.h > 500, `${house.w}×${house.h}`)
  check('六扇门', house.doors === 6, `${house.doors} 扇 / 宽 ${house.doorW}px`)
  check('门牌齐全', house.plates.join('/') === '口碑星图/票房分析/口碑排名/年代流向/口碑分歧/取景地图', house.plates.join('/'))
  check('砖墙 SVG 在位', house.wall)
  check('招牌文案', house.sign === '影评洞察馆', house.sign)
  check('大厅模式收起 HUD 图表区', house.hudHidden)
  check('大厅保留顶栏', house.topBarShown)
  check('大厅压暗 3D 星系层', house.canvasDim)
  check('3D 走廊世界在位', house.world)
  check('3D 视锥已启用（perspective）', house.world3d)
  await page.screenshot({ path: `${OUT}/screen-house.png` })

  /* ---------- 悬停门牌：提示条跟随 ----------
     大厅有轻微浮动动画，门坐标会缓慢漂移；多步移动 + 实时重算坐标 + 重试，
     确保真正悬停到门上（否则 stale 坐标会落进门缝、门不开 → getComputedStyle 拿到 null 崩脚本）。 */
  let d3 = { x: 0, y: 0 }
  let hoverState = { open: 0, hint: null, leaf: 'none' }
  for (let attempt = 0; attempt < 3 && hoverState.open !== 1; attempt++) {
    d3 = await page.evaluate(() => {
      const r = document.querySelectorAll('.ih__door')[2].getBoundingClientRect()
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
    })
    await page.mouse.move(d3.x, d3.y, { steps: 12 })
    await sleep(450)
    hoverState = await page.evaluate(() => {
      const openDoor = document.querySelector('.ih__door.is-open')
      const leaf = openDoor ? openDoor.querySelector('.ih__leaf') : null
      return {
        open: document.querySelectorAll('.ih__door.is-open').length,
        hint: (document.querySelector('.ih__hint b') || {}).textContent,
        leaf: leaf ? getComputedStyle(leaf).transform : 'none',
      }
    })
  }
  check('悬停门微开', hoverState.open === 1 && hoverState.leaf !== 'none', `transform=${String(hoverState.leaf).slice(0, 28)}`)
  check('提示条跟随门牌', hoverState.hint === '口碑排名', hoverState.hint)
  await page.screenshot({ path: `${OUT}/screen-house-hover.png` })

  /* ---------- 推门进入展厅（实时重算落点，避开浮动漂移） ---------- */
  const enterPt = await page.evaluate(() => {
    const r = document.querySelectorAll('.ih__door')[2].getBoundingClientRect()
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
  })
  await page.mouse.click(enterPt.x, enterPt.y)
  await sleep(1200)
  const room = await page.evaluate(() => ({
    houseGone: !document.querySelector('.ih'),
    nav: !!document.querySelector('.room-nav'),
    plate: (document.querySelector('.room-nav__plate b') || {}).textContent,
    leftPanel: getComputedStyle(document.querySelector('.left-panel')).display !== 'none',
    stream: !!document.querySelector('.stream-track'),
    canvasDim: document.querySelector('.three-canvas-layer').classList.contains('is-dim'),
    // 展厅内不应存在跳到其他展厅的入口（串门 / 门牌直达）
    goBtns: document.querySelectorAll('.room-nav__go button').length,
    doorBtns: document.querySelectorAll('.room-nav__door').length,
    backBtn: !!document.querySelector('.room-nav__back'),
    backBg: getComputedStyle(document.querySelector('.room-nav__back')).backgroundImage,
    backColor: getComputedStyle(document.querySelector('.room-nav__back')).color,
  }))
  check('进入展厅（大厅退场）', room.houseGone)
  check('馆内导览条出现', room.nav)
  check('门牌正确', room.plate === '口碑排名', room.plate)
  check('两翼面板回归', room.leftPanel)
  check('底部影评流回归', room.stream)
  check('进入的是图表厅 → 3D 星系层仍压暗', room.canvasDim)
  check('展厅内无串门入口（上一间/下一间）', room.goBtns === 0, `go=${room.goBtns}`)
  check('展厅内无直达其他门入口', room.doorBtns === 0, `door=${room.doorBtns}`)
  check('展厅内保留「回大厅」出口', room.backBtn)
  check('回大厅按钮高对比（实底渐变 + 浅色字，暖白纸上可见）', /gradient/.test(room.backBg) && /(255|254|253|252|251|250)/.test(room.backColor), `${room.backColor} · ${room.backBg.slice(0, 24)}`)
  await page.screenshot({ path: `${OUT}/screen-room-rank.png` })

  /* ---------- 展厅内不可跳其他展厅：仅校验隔离性，切换展厅须经「回大厅」 ---------- */

  /* ---------- 回大厅 ---------- */
  await page.evaluate(() => document.querySelector('.room-nav__back').click())
  await sleep(1000)
  const back = await page.evaluate(() => ({
    house: !!document.querySelector('.ih'),
    doors: document.querySelectorAll('.ih__door').length,
    hudHidden: getComputedStyle(document.querySelector('.stage-dock')).display === 'none',
  }))
  check('回大厅', back.house && back.doors === 6, `${back.doors} 扇`)
  check('回大厅后 HUD 图表区收起', back.hudHidden)

  /* ---------- 导览图（itomdev MAP 面板）---------- */
  const mapBtn = await page.evaluate(() => {
    const b = document.querySelector('.house-map-btn')
    if (!b) return { found: false }
    const cs = getComputedStyle(b)
    const r = b.getBoundingClientRect()
    return { found: true, inVP: r.top >= 0 && r.right <= innerWidth + 1, bg: cs.backgroundImage.slice(0, 16) }
  })
  check('大厅悬浮导览图按钮可见', mapBtn.found && mapBtn.inVP && /gradient/.test(mapBtn.bg), JSON.stringify(mapBtn))

  await page.evaluate(() => document.querySelector('.house-map-btn').click())
  await sleep(900)
  const mapHouse = await page.evaluate(() => {
    const rooms = [...document.querySelectorAll('.im__room')]
    return {
      open: !!document.querySelector('.im__card'),
      rooms: rooms.length,
      locked: rooms.filter((r) => r.classList.contains('is-locked')).length,
      cur: rooms.filter((r) => r.classList.contains('is-cur')).length,
      hall: (document.querySelector('.im__hall-t') || {}).textContent,
      backBtn: !!document.querySelector('.im__back'),
      corridor: !!document.querySelector('.im__corridor'),
    }
  })
  check('导览图打开（手绘纸卡 + 走廊）', mapHouse.open && mapHouse.corridor)
  check('导览图六间展厅', mapHouse.rooms === 6, `${mapHouse.rooms} 间`)
  check('大厅模式全部可点（无锁定）', mapHouse.locked === 0 && mapHouse.cur === 0, `locked=${mapHouse.locked}`)
  check('大厅图钉标注入口', mapHouse.hall === '大厅', mapHouse.hall)
  check('大厅模式无回大厅按钮（本就在大厅）', !mapHouse.backBtn)
  await page.screenshot({ path: `${OUT}/screen-map-house.png` })

  // 地图点第 3 间房 → 传送进入（SVG <g> 没有 .click()，须派发真实事件）
  await page.evaluate(() => {
    const g = document.querySelectorAll('.im__room')[2]
    g.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
  })
  await sleep(1300)
  const mapEnter = await page.evaluate(() => ({
    mapGone: !document.querySelector('.im__card'),
    plate: (document.querySelector('.room-nav__plate b') || {}).textContent,
    mapBtn: !!document.querySelector('.room-nav__map'),
  }))
  check('导览图点房间传送进展厅', mapEnter.mapGone && mapEnter.plate === '口碑排名', mapEnter.plate)
  check('展厅导览图圆钮在位', mapEnter.mapBtn)

  /* ---------- 返回按钮加强版：尺寸 + 高对比（用户 2026-10-22 第三次反馈） ---------- */
  const backSize = await page.evaluate(() => {
    const b = document.querySelector('.room-nav__back')
    const r = b.getBoundingClientRect()
    const cs = getComputedStyle(b)
    return { h: Math.round(r.height), w: Math.round(r.width), fs: cs.fontSize, text: b.textContent.trim(), bg: cs.backgroundImage.slice(0, 16) }
  })
  check('回大厅按钮加大（高 ≥36px、字号 ≥14px、高对比渐变）',
    backSize.h >= 36 && parseFloat(backSize.fs) >= 14 && /gradient/.test(backSize.bg), JSON.stringify(backSize))

  // 展厅模式打开地图：当前房高亮 + 图钉 + 其他锁定 + 回大厅
  await page.evaluate(() => document.querySelector('.room-nav__map').click())
  await sleep(900)
  const mapRoom = await page.evaluate(() => {
    const rooms = [...document.querySelectorAll('.im__room')]
    return {
      open: !!document.querySelector('.im__card'),
      cur: rooms.filter((r) => r.classList.contains('is-cur')).length,
      locked: rooms.filter((r) => r.classList.contains('is-locked')).length,
      here: (document.querySelector('.im__here') || {}).textContent,
      backBtn: !!document.querySelector('.im__back'),
      curName: (rooms.find((r) => r.classList.contains('is-cur'))?.querySelector('.im__room-name') || {}).textContent,
    }
  })
  check('展厅地图仅高亮当前房', mapRoom.cur === 1 && mapRoom.curName === '口碑排名', `cur=${mapRoom.cur} ${mapRoom.curName}`)
  check('展厅地图其余房锁定（不串门）', mapRoom.locked === 5, `locked=${mapRoom.locked}`)
  check('展厅地图「你在这里」图钉', mapRoom.here === '你在这里', mapRoom.here)
  check('展厅地图带回大厅按钮', mapRoom.backBtn)
  await page.screenshot({ path: `${OUT}/screen-map-room.png` })

  // 地图内回大厅
  await page.evaluate(() => document.querySelector('.im__back').click())
  await sleep(1100)
  const mapBack = await page.evaluate(() => ({
    house: !!document.querySelector('.ih'),
    mapGone: !document.querySelector('.im__card'),
  }))
  check('导览图内回大厅', mapBack.house && mapBack.mapGone)

  // Esc 关图
  await page.evaluate(() => document.querySelector('.house-map-btn').click())
  await sleep(700)
  await page.keyboard.press('Escape')
  await sleep(500)
  check('Esc 关闭导览图', await page.evaluate(() => !document.querySelector('.im__card')))

  /* ---------- itomdev 式交互：滚轮走近 + 拖拽环视不误点 ---------- */
  await page.mouse.move(720, 480)
  await page.mouse.wheel({ deltaY: 400 })
  await sleep(800)
  const walk = await page.evaluate(() => {
    const ih = document.querySelector('.ih')
    return { walk: ih.style.getPropertyValue('--walk'), t: getComputedStyle(document.querySelector('.ih__persp')).transform }
  })
  check('滚轮走近（--walk 推近整屋）', parseFloat(walk.walk) > 0 && /matrix/.test(walk.t), `--walk=${walk.walk}`)

  // 拖拽：门上按下 → 拖开 >6px → 松开，不应误进展厅；--rx 缓回 0
  const dragPt = await page.evaluate(() => {
    const r = document.querySelectorAll('.ih__door')[2].getBoundingClientRect()
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
  })
  await page.mouse.move(dragPt.x, dragPt.y)
  await page.mouse.down()
  await page.mouse.move(dragPt.x + 90, dragPt.y + 24, { steps: 10 })
  const draggingOn = await page.evaluate(() => ({
    rx: document.querySelector('.ih').style.getPropertyValue('--rx'),
    cls: document.querySelector('.ih').classList.contains('is-dragging'),
  }))
  await page.mouse.up()
  await sleep(1200)
  const afterDrag = await page.evaluate(() => ({
    house: !!document.querySelector('.ih'),
    rx: document.querySelector('.ih').style.getPropertyValue('--rx'),
  }))
  check('拖拽中环视跟手（--rx 变化 + is-dragging）', parseFloat(draggingOn.rx) !== 0 && draggingOn.cls, JSON.stringify(draggingOn))
  check('拖拽环视不误点进门', afterDrag.house, JSON.stringify(afterDrag))
  check('松手后环视缓回正中', Math.abs(parseFloat(afterDrag.rx || '0')) < 0.01, `--rx=${afterDrag.rx}`)

  /* ---------- 延迟交互回归（2026-10-22 抓到的 Chrome 雷） ----------
     preserve-3d 的 .ih__world 上挂 CSS 浮动动画时，Chrome 约 3 秒后把该层命中
     测试交给合成器，preserve-3d+perspective 回投影出错：悬停/点击门全部失效且
     不自愈。修复=动画挪到 persp。此处等页面存活 6 秒后再验一次悬停+点击，
     确保这类"越晚越坏"的层化 bug 不会再悄悄回来。 */
  await sleep(6000)
  const d6 = await page.evaluate(() => {
    const r = document.querySelectorAll('.ih__door')[4].getBoundingClientRect()
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
  })
  await page.mouse.move(d6.x, d6.y, { steps: 10 })
  await sleep(500)
  const lateHover = await page.evaluate(() => document.querySelectorAll('.ih__door.is-open').length)
  check('延迟 6s 后悬停门仍有效', lateHover === 1, `open=${lateHover}`)
  await page.mouse.click(d6.x, d6.y)
  await sleep(1300)
  const lateRoom = await page.evaluate(() => ({
    house: !!document.querySelector('.ih'),
    plate: (document.querySelector('.room-nav__plate b') || {}).textContent,
  }))
  check('延迟 6s 后点门仍能进展厅', !lateRoom.house && lateRoom.plate === '口碑分歧', lateRoom.plate)
  await page.evaluate(() => document.querySelector('.room-nav__back').click())
  await sleep(900)

  /* ---------- 星图厅：无面板、有读图指南 ---------- */
  await page.evaluate(() => document.querySelectorAll('.ih__door')[0].click())
  await sleep(1500)
  const galaxy = await page.evaluate(() => ({
    plate: (document.querySelector('.room-nav__plate b') || {}).textContent,
    legend: !!document.querySelector('.galaxy-legend'),
    panel: getComputedStyle(document.querySelector('.stage-panel')).display === 'none',
    canvasDim: document.querySelector('.three-canvas-layer').classList.contains('is-dim'),
  }))
  check('星图厅无图表面板', galaxy.plate === '口碑星图' && galaxy.panel, galaxy.plate)
  check('星图读图指南在位', galaxy.legend)
  check('星图厅点亮 3D 星系层', !galaxy.canvasDim)
  await page.screenshot({ path: `${OUT}/screen-room-galaxy.png` })

  /* ---------- 每间展厅的两翼面板与门"对应"（用户 2026-10-22 要求） ----------
     不再每间房都摆同一套"回声廊+叙事轴"，而是按门主题取各自专属面板。 */
  const PANEL_OK = {
    galaxy:  ['跨文化回声廊', '叙事时间轴'],
    box:     ['全球票房榜', '年度票房'],
    rank:    ['豆瓣口碑', '类型口碑榜'],
    flow:    ['叙事时间轴', '预告覆盖'],
    diverge: ['豆瓣口碑', '跨文化回声廊'],
    globe:   ['预告覆盖', '叙事时间轴'],
  }
  for (const key of Object.keys(PANEL_OK)) {
    await page.goto(BASE + '/screen?room=' + key, { waitUntil: 'networkidle2', timeout: 60000 })
    await page.waitForSelector('.room-nav', { timeout: 20000 })
    await sleep(900)
    const p = await page.evaluate(() => ({
      left: (document.querySelector('.left-panel .hud-title__zh') || {}).textContent,
      right: (document.querySelector('.right-panel .hud-title__zh') || {}).textContent,
      ltabs: [...document.querySelectorAll('.left-panel .panel-tab')].map((e) => e.textContent.trim()),
      rtabs: [...document.querySelectorAll('.right-panel .panel-tab')].map((e) => e.textContent.trim()),
    }))
    const [expL, expR] = PANEL_OK[key]
    check(`展厅[${key}] 左翼面板对应`, p.left === expL, `${p.left} (期望 ${expL})`)
    check(`展厅[${key}] 右翼面板对应`, p.right === expR, `${p.right} (期望 ${expR})`)
    check(`展厅[${key}] 标签精简为该房专属`, p.ltabs.length === 1 && p.rtabs.length === 1, `左 ${p.ltabs.length} / 右 ${p.rtabs.length}`)
  }

  /* ---------- 票房分析展厅：itomdev 式相框绳画廊（2026-10-22 新增） ---------- */
  await page.goto(BASE + '/screen?room=box', { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('.room-nav', { timeout: 20000 })
  await page.waitForSelector('.bog__frame', { timeout: 20000 })
  await sleep(1600)
  const bog = await page.evaluate(() => ({
    frames: document.querySelectorAll('.bog__frame').length,
    pins: document.querySelectorAll('.bog__pin').length,
    line: !!document.querySelector('.bog__line'),
    posters: [...document.querySelectorAll('.bog__mat img')].filter((i) => i.complete && i.naturalWidth > 0).length,
    caps: [...document.querySelectorAll('.bog__cap')].map((e) => e.textContent.trim()).slice(0, 3),
    summary: (document.querySelector('.bog__summary') || {}).textContent,
    rankRows: document.querySelectorAll('.borank__row').length,
    trendCanvas: (() => { const c = document.querySelector('.botrend__chart canvas'); return c ? c.width : 0 })(),
  }))
  check('票房画廊相框上架', bog.frames === 24 && bog.pins === 24 && bog.line, `frames=${bog.frames} pins=${bog.pins}`)
  check('相框海报加载', bog.posters >= 20, `posters=${bog.posters}/24`)
  check('相框 caption 为真实片名', bog.caps.length === 3 && bog.caps[0].length >= 2, JSON.stringify(bog.caps))
  check('总览条有收录数', /收录影片/.test(bog.summary || ''), (bog.summary || '').slice(0, 40))
  check('左翼票房榜十行', bog.rankRows === 10, `rows=${bog.rankRows}`)
  check('右翼年度趋势图渲染', bog.trendCanvas > 100, `canvas=${bog.trendCanvas}`)

  // 点相框 → 详情纸卡（票房/预算/ROI 四格）
  const framePt = await page.evaluate(() => {
    const r = document.querySelectorAll('.bog__frame')[2].getBoundingClientRect()
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
  })
  await page.mouse.click(framePt.x, framePt.y)
  await sleep(900)
  const card = await page.evaluate(() => {
    const p = document.querySelector('.bog-card__paper')
    if (!p) return { open: false }
    return {
      open: true,
      title: (p.querySelector('.bog-card__title') || {}).textContent,
      cells: [...p.querySelectorAll('.bog-card__cell')].map((c) => (c.querySelector('b') || {}).textContent),
      link: !!p.querySelector('.bog-card__link'),
    }
  })
  check('点相帧弹档案纸卡', card.open && card.cells.length === 4, JSON.stringify(card))
  check('档案卡票房数字真实', card.cells && card.cells[0] && /亿美元/.test(card.cells[0]), card.cells && card.cells[0])
  check('档案卡带影片链接', card.link)
  await page.screenshot({ path: `${OUT}/screen-box-gallery.png` })
  await page.keyboard.press('Escape')
  await sleep(500)
  const cardClosed = await page.evaluate(() => !document.querySelector('.bog-card__paper'))
  check('Esc 关闭档案卡', cardClosed)

  // 滚轮沿线漂移（桌面端）
  const drift = await page.evaluate(() => {
    const rail = document.querySelector('.bog__rail')
    return { t: getComputedStyle(rail).transform }
  })
  await page.mouse.move(700, 500)
  await page.mouse.wheel({ deltaY: 500 })
  await sleep(700)
  const drift2 = await page.evaluate(() => ({ t: getComputedStyle(document.querySelector('.bog__rail')).transform }))
  check('滚轮沿绳漂移', drift.t !== drift2.t, `${drift.t.slice(0, 24)} → ${drift2.t.slice(0, 24)}`)

  // 左翼榜单点选 → 中央画廊打开同一部档案（联动）
  await page.evaluate(() => document.querySelectorAll('.borank__row')[1].click())
  await sleep(900)
  const pickCard = await page.evaluate(() => {
    const p = document.querySelector('.bog-card__paper')
    return { open: !!p, title: p ? (p.querySelector('.bog-card__title') || {}).textContent : null }
  })
  check('票房榜点选联动画廊档案', pickCard.open && !!pickCard.title, JSON.stringify(pickCard))

  /* ---------- 键盘可达性 ---------- */
  await page.evaluate(() => document.querySelector('.room-nav__back').click())
  await sleep(900)
  const kb = await page.evaluate(() => {
    const d = document.querySelectorAll('.ih__door')[1]
    d.focus()
    return document.activeElement === d
  })
  await page.keyboard.press('Enter')
  await sleep(1200)
  const kbRoom = await page.evaluate(() => (document.querySelector('.room-nav__plate b') || {}).textContent)
  check('门可聚焦', kb)
  check('回车推门进展厅', kbRoom === '票房分析', kbRoom)

  /* ---------- 桌面无横向溢出 ---------- */
  const ovf = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  check('无横向溢出', ovf <= 0, `overflow=${ovf}`)

  /* ---------- 移动端 ---------- */
  const m = await browser.newPage()
  await m.setViewport({ width: 390, height: 844, isMobile: true, deviceScaleFactor: 2 })
  await m.goto(BASE + '/screen', { waitUntil: 'networkidle2', timeout: 60000 })
  await m.waitForSelector('.ih__door', { timeout: 20000 })
  await sleep(1200)
  const mob = await m.evaluate(() => {
    const r = document.querySelector('.ih').getBoundingClientRect()
    const hint = document.querySelector('.ih__hint').getBoundingClientRect()
    const doors = [...document.querySelectorAll('.ih__door')].map((d) => Math.round(d.getBoundingClientRect().width))
    return {
      w: Math.round(r.width),
      h: Math.round(r.height),
      ovf: document.documentElement.scrollWidth - window.innerWidth,
      doors,
      hintInside: hint.left >= 0 && hint.right <= window.innerWidth,
    }
  })
  check('移动端大厅铺满', mob.w >= 380 && mob.h > 500, `${mob.w}×${mob.h}`)
  check('移动端无横向溢出', mob.ovf <= 0, `overflow=${mob.ovf}`)
  check('移动端门宽合理', mob.doors.every((w) => w >= 84), mob.doors.join('/'))
  check('移动端提示条不越界', mob.hintInside)
  await m.screenshot({ path: `${OUT}/screen-house-mobile.png` })

  /* 移动端导览图：纸卡不溢出视口、可开可关 */
  await m.evaluate(() => document.querySelector('.house-map-btn').click())
  await sleep(900)
  const mobMap = await m.evaluate(() => {
    const c = document.querySelector('.im__card')
    if (!c) return { open: false }
    const r = c.getBoundingClientRect()
    return { open: true, inVP: r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1, w: Math.round(r.width) }
  })
  check('移动端导览图纸卡不溢出', mobMap.open && mobMap.inVP, JSON.stringify(mobMap))
  await m.screenshot({ path: `${OUT}/screen-map-mobile.png` })
  await m.evaluate(() => document.querySelector('.im__close').click())
  await sleep(500)

  /* 移动端进入展厅：顶部导航条的「回大厅」按钮必须可见（窄屏不再整条收起 .stage-dock） */
  await m.evaluate(() => document.querySelectorAll('.ih__door')[0].click())
  await sleep(1500)
  const mobRoom = await m.evaluate(() => {
    const exit = document.querySelector('.room-nav__back')
    if (!exit) return { exit: false }
    const cs = getComputedStyle(exit)
    const r = exit.getBoundingClientRect()
    return {
      exit: true,
      display: cs.display,
      visibility: cs.visibility,
      inViewport: r.width > 0 && r.height > 0 && r.top >= 0 && r.left >= 0 && r.right <= window.innerWidth,
    }
  })
  check('移动端展厅「回大厅」按钮可见', mobRoom.exit && mobRoom.display !== 'none' && mobRoom.visibility !== 'hidden' && mobRoom.inViewport, JSON.stringify(mobRoom))
  await m.screenshot({ path: `${OUT}/screen-room-mobile.png` })

  check('0 控制台错误', errors.length === 0, errors.slice(0, 2).join(' | '))

  await browser.close()
  console.log(`\n结果：${pass} 通过 / ${fail} 失败\n`)
  process.exit(fail === 0 ? 0 : 1)
})().catch((e) => { console.error('运行失败：', e); process.exit(1) })
