<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import earthMapUrl from '../../assets/textures/earth-blue-marble.jpg'
import earthWaterUrl from '../../assets/textures/earth-water.png'

// 取景地地球面板 —— 蓝色 3D 地球（NASA Blue Marble 贴图 + 海洋高光 + 大气边缘光）。
// 数据接口：props.points = /fun/map -> [{ name, kind:'filming'|'narrative', lat, lon, movies }]
// 交互：拖拽旋转（带惯性）、滚轮缩放、悬停高亮、点击光点 emit('select', point)
// 说明：贴图中 src/assets/textures/ 本地提供（源自 three-globe 自带资源），不依赖任何外网 CDN。
const props = defineProps({
  points: { type: Array, default: () => [] },
})
const emit = defineEmits(['select'])

const wrap = ref(null)
const tip = ref(null)          // { x, y, name, movies }
const hoverName = ref('')      // 供 aria/提示用

let renderer = null
let scene = null
let camera = null
let earth = null               // 地球组（自转 + 拖拽旋转都作用在它上面）
let globe = null               // 球体 mesh
let markerGroup = null
let markers = []               // { mesh, sprite, p, normal, base }
let raf = null
let ro = null
let disposed = false
let t0 = 0                      // 动画时间基准（避免 THREE.Clock 弃用警告）

// 视角 / 交互状态
const CAM_Z = 3.62
const CAM_MIN = 2.45
const CAM_MAX = 5.0
let camZ = CAM_Z
let dragging = false
let dragMoved = 0
let lastX = 0
let lastY = 0
let velX = 0                   // 拖拽惯性（rad/帧）
let velY = 0
let hovered = null
let suppressClick = false

const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
const tmpVec = new THREE.Vector3()

// 经纬度 -> 球面坐标（与等距圆柱贴图 UV 对齐，three-globe 同款公式）
function latLonToVec3(lat, lon, r) {
  const phi = ((90 - lat) * Math.PI) / 180
  const theta = ((lon + 180) * Math.PI) / 180
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta),
  )
}

// 脉冲环用的环形贴图（canvas 生成，避免额外资源）
function ringTexture() {
  const s = 128
  const c = document.createElement('canvas')
  c.width = c.height = s
  const g = c.getContext('2d')
  const grd = g.createRadialGradient(s / 2, s / 2, s * 0.3, s / 2, s / 2, s * 0.48)
  grd.addColorStop(0, 'rgba(255,255,255,0)')
  grd.addColorStop(0.72, 'rgba(255,255,255,0.9)')
  grd.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grd
  g.beginPath()
  g.arc(s / 2, s / 2, s / 2, 0, Math.PI * 2)
  g.fill()
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}
let ringTex = null

function size() {
  const el = wrap.value
  if (!el || !renderer) return
  const w = el.clientWidth || 640
  const h = el.clientHeight || 420
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
  renderer.setSize(w, h, false)
  renderer.domElement.style.width = '100%'
  renderer.domElement.style.height = '100%'
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

function buildScene() {
  scene = new THREE.Scene()
  t0 = performance.now()

  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100)
  camera.position.set(0, 0, CAM_Z)

  // ---- 地球本体：蓝大理石贴图 + 海水高光 ----
  const loader = new THREE.TextureLoader()
  const map = loader.load(earthMapUrl)
  map.colorSpace = THREE.SRGBColorSpace
  map.anisotropy = 4
  const water = loader.load(earthWaterUrl)

  globe = new THREE.Mesh(
    new THREE.SphereGeometry(1, 96, 64),
    new THREE.MeshPhongMaterial({
      map,
      // 只有海洋（water 图白色区域）反光，陆地保持哑光；
      // shininess 调高 = 高光收成一小点，否则中间会糊出一大片塑料灯箱感
      // 不要强高光：蓝色地球本身靠海洋色 + 陆地细节就够，高光会糊出塑料灯箱感
      specularMap: water,
      specular: new THREE.Color(0x0a1c2c),
      shininess: 260,
      bumpMap: water,
      bumpScale: 0.012,
    }),
  )
  earth = new THREE.Group()
  earth.add(globe)

  // ---- 大气边缘光：背面球壳 + 菲涅尔透明度（白底上用普通混合才不会糊成一片）----
  const atmo = new THREE.Mesh(
    new THREE.SphereGeometry(1.022, 64, 48),
    new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.BackSide,
      blending: THREE.NormalBlending,
      uniforms: { uColor: { value: new THREE.Color(0x6fb2ea) } },
      vertexShader: `
        varying vec3 vN;
        void main() {
          vN = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying vec3 vN;
        void main() {
          float f = pow(clamp(0.72 - dot(vN, vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 2.8);
          gl_FragColor = vec4(uColor, f * 1.05);
        }
      `,
    }),
  )
  atmo.renderOrder = -1
  earth.add(atmo)
  scene.add(earth)

  // ---- 光照：主光偏右上前方，补光偏冷，白底上保住海洋的蓝 ----
  scene.add(new THREE.AmbientLight(0xffffff, 0.52))
  // 半球光：上半天空蓝、下半暖白，暗部不死黑、海洋带一点天光
  scene.add(new THREE.HemisphereLight(0xd6e8fa, 0xefe2cd, 0.9))
  // 只留一盏主光：两盏方向光会打出两团高光斑，像塑料灯箱
  const key = new THREE.DirectionalLight(0xffffff, 1.0)
  key.position.set(1.6, 1.1, 2.2)
  scene.add(key)
}

// 光点：拍摄地=暖棕金，故事发生地=青；大小随影片数（对数压缩，避免大城市吞掉画面）
const COLOR_FILMING = 0xb45309
const COLOR_NARRATIVE = 0x0f766e

function buildMarkers() {
  if (!earth) return
  if (markerGroup) {
    earth.remove(markerGroup)
    markerGroup.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material && o.material !== ringTex) o.material.dispose()
    })
  }
  markerGroup = new THREE.Group()
  markers = []
  ringTex = ringTex || ringTexture()

  const pts = (props.points || []).filter(
    (p) => p && Number.isFinite(Number(p.lat)) && Number.isFinite(Number(p.lon)),
  )
  const top = [...pts].sort((a, b) => (b.movies || 0) - (a.movies || 0)).slice(0, 4).map((p) => p.name)

  pts.forEach((p) => {
    const n = Math.max(0, Number(p.movies) || 0)
    // 世界半径：0.008 ~ 0.019（对数压缩，33 部的地点也只有 ~0.019）
    const r = Math.min(0.019, 0.008 + Math.log2(n + 1) * 0.0026)
    const pos = latLonToVec3(Number(p.lat), Number(p.lon), 1.004)
    const color = p.kind === 'filming' ? COLOR_FILMING : COLOR_NARRATIVE

    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(r, 14, 12),
      new THREE.MeshBasicMaterial({ color }),
    )
    mesh.position.copy(pos)
    // 外圈浅色描边，让点在深蓝海洋上更清楚
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(r * 1.55, 14, 12),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.22 }),
    )
    mesh.add(halo)
    markerGroup.add(mesh)

    // 透明放大命中盒：视觉径只有 7~10px，直接拿小球做 raycast 很难点中
    const picker = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(r * 3.4, 0.028), 8, 6),
      new THREE.MeshBasicMaterial({ visible: false }),
    )
    picker.position.copy(pos)
    markerGroup.add(picker)

    let sprite = null
    if (top.includes(p.name)) {
      sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: ringTex,
          color: p.kind === 'filming' ? 0xe08a3c : 0x37b3a6,
          transparent: true,
          depthWrite: false,
          opacity: 0.75,
        }),
      )
      sprite.position.copy(pos.clone().multiplyScalar(1.006))
      sprite.scale.setScalar(r * 3.8)
      markerGroup.add(sprite)
    }

    const marker = {
      mesh,
      picker,
      sprite,
      p,
      normal: pos.clone().normalize(),
      base: r,
      phase: Math.random(),
    }
    picker.userData.marker = marker
    markers.push(marker)
  })
  earth.add(markerGroup)
}

function updatePulse(t) {
  markers.forEach((m) => {
    if (!m.sprite) return
    const ph = ((t * 0.55 + m.phase) % 1 + 1) % 1
    const k = 1 + ph * 2.2
    m.sprite.scale.setScalar(m.base * 3.8 * k)
    m.sprite.material.opacity = 0.5 * (1 - ph)
  })
}

// 只在“正面朝向相机”的光点上做悬停 / 点击（背面被球体遮住，不该响应）
function isFrontFacing(worldNormal) {
  tmpVec.copy(camera.position).sub(worldNormal.clone().multiplyScalar(1))
  return worldNormal.dot(tmpVec) > 0
}

function pick(ev, tolPx = 16) {
  if (!renderer) return null
  const rect = renderer.domElement.getBoundingClientRect()
  const px = ev.clientX - rect.left
  const py = ev.clientY - rect.top
  pointer.x = (px / rect.width) * 2 - 1
  pointer.y = -(py / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(markers.map((m) => m.picker), false)
  for (const h of hits) {
    const found = h.object.userData.marker
    if (!found) continue
    const wn = found.normal.clone().applyQuaternion(earth.quaternion).normalize()
    if (!isFrontFacing(wn)) continue
    // 屏幕坐标给提示条定位
    const sp = h.object.getWorldPosition(new THREE.Vector3()).project(camera)
    return {
      marker: found,
      x: ((sp.x + 1) / 2) * rect.width,
      y: ((1 - sp.y) / 2) * rect.height,
    }
  }

  // 兜底：光点投影到屏幕只有几像素，且地球一直在自转，直接 raycast 很容易差几像素落空。
  // 按屏幕距离取最近的正面光点，容差 tolPx。
  let best = null
  let bestD = tolPx
  markers.forEach((m) => {
    const wn = m.normal.clone().applyQuaternion(earth.quaternion).normalize()
    if (!isFrontFacing(wn)) return
    const sp = m.mesh.getWorldPosition(new THREE.Vector3()).project(camera)
    const sx = ((sp.x + 1) / 2) * rect.width
    const sy = ((1 - sp.y) / 2) * rect.height
    const d = Math.hypot(sx - px, sy - py)
    if (d < bestD) { bestD = d; best = { marker: m, x: sx, y: sy } }
  })
  return best
}

function setHover(hit) {
  if (hovered && hovered !== hit?.marker) {
    hovered.mesh.scale.setScalar(1)
    hovered = null
  }
  if (hit) {
    hit.marker.mesh.scale.setScalar(1.45)
    hovered = hit.marker
    hoverName.value = hit.marker.p.name
    tip.value = {
      x: hit.x,
      y: hit.y,
      name: hit.marker.p.name,
      movies: hit.marker.p.movies || 0,
    }
    renderer.domElement.style.cursor = 'pointer'
  } else {
    tip.value = null
    renderer.domElement.style.cursor = dragging ? 'grabbing' : 'grab'
  }
}

/* ---------------- 交互 ---------------- */
function onPointerDown(ev) {
  dragging = true
  dragMoved = 0
  lastX = ev.clientX
  lastY = ev.clientY
  velX = velY = 0
  renderer.domElement.style.cursor = 'grabbing'
  try { renderer.domElement.setPointerCapture?.(ev.pointerId) } catch { /* 合成事件可能无捕获权 */ }
}

function onPointerMove(ev) {
  if (!dragging) {
    setHover(pick(ev))
    return
  }
  const dx = ev.clientX - lastX
  const dy = ev.clientY - lastY
  lastX = ev.clientX
  lastY = ev.clientY
  dragMoved += Math.abs(dx) + Math.abs(dy)
  rotateBy(dx * 0.0052, dy * 0.0042)
  velX = dx * 0.0052
  velY = dy * 0.0042
}

function rotateBy(dx, dy) {
  earth.rotation.y += dx
  earth.rotation.x = Math.max(-0.62, Math.min(0.62, earth.rotation.x + dy))
}

function onPointerUp(ev) {
  if (!dragging) return
  dragging = false
  try { renderer.domElement.releasePointerCapture?.(ev.pointerId) } catch { /* 未捕获时忽略 */ }
  renderer.domElement.style.cursor = 'grab'
  // 拖过就压制后续 click，避免转完地球误跳地点卡
  if (dragMoved >= 6) {
    velX = velX * 0.85
    suppressClick = true
    // 兜底复位：拖到元素外时不产生 click，标记不能永久挂着
    setTimeout(() => { suppressClick = false }, 420)
  }
  setHover(pick(ev))
}

// 点击选中：用原生 click 而不是 pointerup，pointer capture 被系统干扰时也能稳定触发
function onClick(ev) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  const hit = pick(ev)
  if (hit) emit('select', hit.marker.p)
}

function onWheel(ev) {
  if (!renderer) return
  // 只处理纵向滚动；缩放到范围内
  ev.preventDefault()
  const d = ev.deltaY * 0.0016
  camZ = Math.max(CAM_MIN, Math.min(CAM_MAX, camZ + d))
  camera.position.z = camZ
}

function onLeave() {
  setHover(null)
  if (dragging) {
    dragging = false
    renderer.domElement.style.cursor = 'grab'
  }
}

function loop() {
  if (disposed) return
  raf = requestAnimationFrame(loop)
  const t = (performance.now() - t0) / 1000

  if (!dragging) {
    // 惯性衰减
    if (Math.abs(velX) > 0.0001 || Math.abs(velY) > 0.0001) {
      rotateBy(velX, velY)
      velX *= 0.94
      velY *= 0.94
    } else {
      // 静止后缓慢自转
      earth.rotation.y += 0.0013
    }
  }

  updatePulse(t)
  renderer.render(scene, camera)
}

watch(
  () => props.points,
  () => { buildMarkers() },
  { deep: false },
)

onMounted(() => {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setClearAlpha(0)
  renderer.domElement.style.display = 'block'
  renderer.domElement.style.cursor = 'grab'
  renderer.domElement.style.touchAction = 'none'
  wrap.value.appendChild(renderer.domElement)

  buildScene()
  buildMarkers()
  // 初始朝向：本初子午线略偏左，光点最密的大西洋两岸都在正面；地轴微倾更像地球仪
  earth.rotation.set(0.1, -Math.PI / 2 + 0.32, -0.16)
  size()

  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointercancel', onPointerUp)
  renderer.domElement.addEventListener('pointerleave', onLeave)
  renderer.domElement.addEventListener('click', onClick)
  renderer.domElement.addEventListener('wheel', onWheel, { passive: false })

  ro = new ResizeObserver(() => size())
  ro.observe(wrap.value)

  loop()
})

onBeforeUnmount(() => {
  disposed = true
  if (raf) cancelAnimationFrame(raf)
  if (ro) ro.disconnect()
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    renderer.domElement.removeEventListener('pointercancel', onPointerUp)
    renderer.domElement.removeEventListener('pointerleave', onLeave)
    renderer.domElement.removeEventListener('click', onClick)
    renderer.domElement.removeEventListener('wheel', onWheel)
    scene?.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) {
        const mats = Array.isArray(o.material) ? o.material : [o.material]
        mats.forEach((m) => {
          if (m.map) m.map.dispose()
          if (m.specularMap) m.specularMap.dispose()
          if (m.bumpMap) m.bumpMap.dispose()
          m.dispose()
        })
      }
    })
    renderer.dispose()
    renderer.domElement.remove()
    renderer = null
  }
})
</script>

<template>
  <div ref="wrap" class="globe-stage">
    <div
      v-if="tip"
      class="globe-tip"
      :style="{ left: `${tip.x}px`, top: `${Math.max(18, tip.y - 34)}px` }"
    >
      {{ tip.name }}<span v-if="tip.movies"> · {{ tip.movies }} 部</span>
    </div>
  </div>
</template>

<style scoped>
.globe-stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  overflow: hidden;
}
/* 地面柔和投影：让地球悬在暖白底上，不显得贴在纸上 */
.globe-stage::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 5%;
  width: 46%;
  height: 24px;
  transform: translateX(-50%);
  background: radial-gradient(ellipse at center, rgba(90, 58, 24, 0.2), rgba(90, 58, 24, 0) 70%);
  filter: blur(7px);
  pointer-events: none;
}
.globe-stage :deep(canvas) {
  position: relative;
  z-index: 1;
}
.globe-tip {
  position: absolute;
  z-index: 2;
  transform: translate(-50%, -100%);
  background: rgba(48, 34, 18, 0.86);
  color: #fff;
  padding: 4px 11px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 4px 14px rgba(40, 26, 10, 0.28);
}
</style>
