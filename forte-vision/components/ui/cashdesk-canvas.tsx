"use client"

import { useI18n } from "@/components/locale-provider"
import { productMessages } from "@/lib/messages/product"

import { useEffect, useRef, useState } from "react"
import * as THREE from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js"
import SceneFallback from "./cashdesk-fallback"
import type { CashdeskSceneProps } from "./cashdesk-scene"
import { readMediaQuery } from "@/lib/browser-media"

export default function CashdeskCanvas({ className = "", compact = false, active = true }: CashdeskSceneProps) {
  const { t, locale } = useI18n(productMessages)
  const hostRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef(active)
  const [ready, setReady] = useState(false)
  useEffect(() => { activeRef.current = active }, [active])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" })
    } catch { setReady(false); return }

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(31, 1, 0.1, 60)
    camera.position.set(6.7, 5.7, 8)
    camera.lookAt(0, 0.6, 0)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8))
    renderer.setClearColor(0xffffff, 0)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.domElement.style.cssText = "width:100%;height:100%;display:block;outline:none;touch-action:pan-y;cursor:grab"
    renderer.domElement.setAttribute("aria-label", t("Трёхмерная схема анализа кассовых операций. Перетаскивайте, чтобы повернуть."))
    renderer.domElement.setAttribute("role", "img")
    renderer.domElement.tabIndex = -1
    host.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    // Let touch gestures scroll the page instead of capturing the miniature.
    controls.enableRotate = readMediaQuery("(pointer: coarse)")?.matches === false
    renderer.domElement.style.touchAction = "pan-y"
    controls.target.set(0, 0.65, 0)
    controls.enableDamping = true
    controls.dampingFactor = 0.065
    controls.enablePan = false
    controls.enableZoom = false
    controls.rotateSpeed = 0.45
    controls.minPolarAngle = 0.65
    controls.maxPolarAngle = 1.3
    controls.minAzimuthAngle = -0.8
    controls.maxAzimuthAngle = 1.25
    controls.update()

    scene.add(new THREE.HemisphereLight(0xffffff, 0xc7bdc6, 3.1))
    const light = new THREE.DirectionalLight(0xfffafb, 4)
    light.position.set(-4, 9, 7)
    light.castShadow = true
    light.shadow.mapSize.set(1024, 1024)
    Object.assign(light.shadow.camera, { left: -6, right: 6, top: 5, bottom: -5, near: 1, far: 25 })
    light.shadow.normalBias = 0.04
    light.shadow.bias = -0.0002
    scene.add(light)
    const rim = new THREE.DirectionalLight(0xeee5f1, 2)
    rim.position.set(5, 4, -6)
    scene.add(rim)

    const materials = new Set<THREE.Material>()
    const geometries = new Map<string, THREE.BufferGeometry>()
    const textures: THREE.Texture[] = []
    const material = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) => {
      const m = new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.08, ...extra })
      materials.add(m)
      return m
    }
    const M = {
      stone: material("#F6F2F2"), white: material("#FFFFFF"), edge: material("#E1D8DC"),
      burgundy: material("#A31551"), plum: material("#4A0221"), dark: material("#29232F"),
      paper: material("#F7F5ED"), cash: material("#D9DFD2"), mint: material("#6B9B84"),
      pink: material("#E2206F", { emissive: "#E2206F", emissiveIntensity: 0.25 }),
      glass: material("#DFC6D2", { transparent: true, opacity: 0.18, metalness: 0, depthWrite: false }),
    }
    const machine = new THREE.Group()
    scene.add(machine)
    function box(w: number, h: number, d: number, x: number, y: number, z: number, m: THREE.Material = M.stone, r = 0.055, parent: THREE.Object3D = machine) {
      const key = [w, h, d, r].join(",")
      if (!geometries.has(key)) geometries.set(key, new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 3, h / 3, d / 3)))
      const mesh = new THREE.Mesh(geometries.get(key)!, m)
      mesh.position.set(x, y, z)
      mesh.castShadow = true
      mesh.receiveShadow = true
      parent.add(mesh)
      return mesh
    }
    function cylinder(r: number, h: number, x: number, y: number, z: number, m = M.dark) {
      const key = `c${r},${h}`
      if (!geometries.has(key)) geometries.set(key, new THREE.CylinderGeometry(r, r, h, 24))
      const mesh = new THREE.Mesh(geometries.get(key)!, m)
      mesh.position.set(x, y, z)
      mesh.castShadow = true
      machine.add(mesh)
      return mesh
    }
    function printScreen(width: number, height: number, x: number, y: number, z: number, draw: (ctx: CanvasRenderingContext2D) => void) {
      const canvas = document.createElement("canvas")
      canvas.width = 512
      canvas.height = 320
      const ctx = canvas.getContext("2d")
      if (!ctx) return
      draw(ctx)
      const texture = new THREE.CanvasTexture(canvas)
      texture.colorSpace = THREE.SRGBColorSpace
      textures.push(texture)
      const m = new THREE.MeshBasicMaterial({ map: texture, toneMapped: false })
      materials.add(m)
      const geo = new THREE.PlaneGeometry(width, height)
      geometries.set(`screen-${textures.length}`, geo)
      const screen = new THREE.Mesh(geo, m)
      screen.position.set(x, y, z)
      machine.add(screen)
    }
    const text = (ctx: CanvasRenderingContext2D, value: string, x: number, y: number, size: number, color: string, weight = 600) => {
      ctx.font = `${weight} ${size}px "Open Sans", sans-serif`
      ctx.fillStyle = color
      ctx.fillText(value, x, y)
    }

    // One layered stone plinth joins the recording, analysis and evidence stations.
    box(6.7, 0.22, 3.75, 0, 0, 0, M.edge, 0.13)
    box(6.65, 0.1, 3.7, 0, 0.15, 0, M.white, 0.12)
    box(5.92, 0.018, 0.022, 0, 0.217, 1.45, M.edge, 0.005)
    box(1.66, 0.022, 0.034, -1.88, 0.223, 1.45, M.burgundy, 0.008)
    const floorGeo = new THREE.PlaneGeometry(30, 30)
    geometries.set("floor", floorGeo)
    const shadowMat = new THREE.ShadowMaterial({ opacity: 0.105 })
    materials.add(shadowMat)
    const floor = new THREE.Mesh(floorGeo, shadowMat)
    floor.rotation.x = -Math.PI / 2
    floor.position.y = -0.15
    floor.receiveShadow = true
    scene.add(floor)

    // Capture: a camera sits above a real miniature cashier desk.
    box(0.16, 1.7, 0.16, -2.55, 1.08, -0.85, M.edge)
    box(0.72, 0.12, 0.12, -2.27, 1.88, -0.85, M.edge)
    const cam = box(0.64, 0.33, 0.35, -1.94, 1.84, -0.85, M.white, 0.09)
    cam.rotation.z = -0.12
    box(0.11, 0.23, 0.28, -1.6, 1.8, -0.85, M.plum, 0.035)
    const lens = cylinder(0.072, 0.05, -1.54, 1.8, -0.85, M.dark)
    lens.rotation.z = Math.PI / 2
    box(2.2, 0.95, 0.75, -0.8, 0.73, 0.22, M.burgundy, 0.07)
    box(2.37, 0.13, 1.05, -0.8, 1.27, 0.2, M.white, 0.065)
    box(2.13, 0.025, 0.04, -0.8, 0.45, 0.605, M.plum, 0.006)
    box(0.28, 0.3, 0.22, -1.12, 1.5, -0.12, M.dark)
    box(0.48, 0.055, 0.36, -1.12, 1.36, -0.08, M.dark, 0.025)
    box(0.92, 0.65, 0.09, -1.12, 1.86, -0.1, M.dark, 0.055)
    printScreen(0.81, 0.52, -1.12, 1.86, -0.045, ctx => {
      ctx.fillStyle = "#FCFAFB"; ctx.fillRect(0, 0, 512, 320)
      text(ctx, "forte", 30, 70, 49, "#A31551", 700)
      ctx.fillStyle = "#F1E9ED"; ctx.fillRect(30, 103, 450, 2)
      for (let i = 0; i < 3; i++) { ctx.fillStyle = i === 1 ? "#A31551" : "#DDD2D7"; ctx.fillRect(34, 140 + i * 49, 165 + i * 55, 12) }
      ctx.fillStyle = "#E8F0EB"; ctx.fillRect(365, 137, 105, 130)
      text(ctx, "✓", 391, 222, 51, "#628871")
    })
    box(0.53, 0.035, 0.24, -1.02, 1.36, 0.45, M.edge, 0.016)
    // Cash bundles and their visible paper edges.
    for (let stack = 0; stack < 3; stack++) {
      const x = -0.16 + stack * 0.23
      for (let sheet = 0; sheet < 4; sheet++) box(0.34, 0.018, 0.2, x, 1.36 + sheet * 0.021, 0.19 + stack * 0.1, sheet % 2 ? M.cash : M.paper, 0.007)
      box(0.065, 0.085, 0.205, x, 1.395, 0.19 + stack * 0.1, M.burgundy, 0.005)
    }
    box(0.045, 1.1, 0.045, 0.32, 1.87, -0.44, M.edge, 0.01)
    box(1.8, 0.85, 0.025, -0.62, 1.99, -0.44, M.glass, 0.02)

    // Detection: a thin scan volume and corner marks above the cash area.
    const scan = new THREE.Group()
    machine.add(scan)
    const scanMat = new THREE.MeshBasicMaterial({ color: "#E2206F", transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false })
    materials.add(scanMat)
    box(0.73, 0.012, 0.8, 0.01, 1.61, 0.2, scanMat, 0.003, scan)
    for (const dx of [-0.4, 0.4]) for (const dz of [-0.33, 0.55]) {
      box(0.15, 0.018, 0.024, dx - Math.sign(dx) * 0.055, 1.35, dz, M.pink, 0.005)
      box(0.024, 0.018, 0.15, dx, 1.35, dz + (dz < 0 ? 0.055 : -0.055), M.pink, 0.005)
    }

    // Evidence: an independent review display and a small ordered card stack.
    box(1.6, 0.1, 1.3, 2.01, 0.29, 0, M.stone)
    box(0.18, 0.69, 0.19, 2.01, 0.68, -0.2, M.plum)
    box(0.61, 0.065, 0.43, 2.01, 0.39, -0.15, M.edge)
    box(1.62, 1.13, 0.13, 2.01, 1.25, -0.22, M.plum, 0.075)
    printScreen(1.45, 0.97, 2.01, 1.25, -0.145, ctx => {
      ctx.fillStyle = "#FCFAFB"; ctx.fillRect(0, 0, 512, 320)
      text(ctx, t("АНАЛИЗ ЗАВЕРШЁН"), 25, 39, 17, "#7B6B73", 600)
      ctx.fillStyle = "#F1E8ED"; ctx.fillRect(25, 60, 257, 188)
      ctx.fillStyle = "#D6C8CE"; ctx.fillRect(40, 119, 222, 102)
      ctx.fillStyle = "#A31551"; ctx.fillRect(56, 155, 190, 68)
      ctx.fillStyle = "#FBF8F9"; ctx.fillRect(56, 148, 190, 13)
      ctx.strokeStyle = "#E2206F"; ctx.lineWidth = 4; ctx.strokeRect(178, 127, 64, 57)
      for (let i = 0; i < 3; i++) {
        ctx.fillStyle = i === 0 ? "#A31551" : "#E5DCE1"; ctx.fillRect(306, 70 + 61 * i, 13, 13)
        ctx.fillStyle = "#6C5B66"; ctx.fillRect(332, 72 + 61 * i, 136, 6)
        ctx.fillStyle = "#DFD4DA"; ctx.fillRect(332, 89 + 61 * i, 100, 5)
      }
      text(ctx, "00:14", 28, 286, 19, "#A31551")
      ctx.fillStyle = "#D8CED4"; ctx.fillRect(111, 276, 364, 3)
      ctx.fillStyle = "#A31551"; ctx.fillRect(111, 276, 128, 3)
    })
    for (let i = 0; i < 3; i++) box(0.8, 0.045, 0.58, 2.05 + i * 0.045, 0.4 + i * 0.055, 0.73 - i * 0.025, i === 2 ? M.white : M.edge, 0.035)
    box(0.42, 0.009, 0.04, 2.13, 0.542, 0.67, M.burgundy, 0.009)
    box(0.3, 0.009, 0.025, 2.07, 0.542, 0.8, M.edge, 0.005)

    let frame = 0
    let visible = true
    let lost = false
    const reducedMotion = readMediaQuery("(prefers-reduced-motion: reduce)")
    const render = () => { if (!lost) renderer.render(scene, camera) }
    const resize = () => {
      const { width, height } = host.getBoundingClientRect()
      if (!width || !height) return
      camera.aspect = width / height
      // Preserve the whole miniature at both compact and wide hero proportions.
      camera.fov = width / height < 1.3 ? 39 : compact ? 34 : 31
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
      render()
    }
    const onLost = (event: Event) => { event.preventDefault(); lost = true; setReady(false) }
    const onRestored = () => { lost = false; render(); setReady(true) }
    renderer.domElement.addEventListener("webglcontextlost", onLost)
    renderer.domElement.addEventListener("webglcontextrestored", onRestored)
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true })
    intersection.observe(host)
    controls.addEventListener("change", render)
    const startedAt = performance.now()
    const animate = () => {
      frame = requestAnimationFrame(animate)
      if (!visible || document.hidden || lost) return
      controls.update()
      if (activeRef.current && reducedMotion?.matches === false) {
        scan.position.y = Math.sin((performance.now() - startedAt) * 0.0015) * 0.17
        render()
      }
    }
    resize()
    setReady(true)
    animate()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      intersection.disconnect()
      controls.removeEventListener("change", render)
      controls.dispose()
      renderer.domElement.removeEventListener("webglcontextlost", onLost)
      renderer.domElement.removeEventListener("webglcontextrestored", onRestored)
      geometries.forEach(geometry => geometry.dispose())
      textures.forEach(texture => texture.dispose())
      materials.forEach(m => m.dispose())
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [compact, locale, t])

  return (
    <div className={`cashdesk-scene ${className}`} style={{ position: "relative", width: "100%", height: "100%", minHeight: 0, overflow: "hidden" }}>
      <div aria-hidden={ready} style={{ position: "absolute", inset: 0, opacity: ready ? 0 : 1, transition: "opacity 300ms", pointerEvents: "none" }}>
        <SceneFallback />
      </div>
      <div ref={hostRef} aria-hidden={!ready} style={{ position: "absolute", inset: 0, opacity: ready ? 1 : 0, transition: "opacity 300ms" }} />
      <div aria-hidden="true" style={{ position: "absolute", bottom: compact ? 4 : 12, left: "12%", right: "8%", display: "flex", justifyContent: "space-between", pointerEvents: "none", gap: 8 }}>
        {["Запись", "Анализ", "Доказательства"].map((label, i) => <span key={label} style={{ fontSize: 9, fontWeight: 600, letterSpacing: ".03em", color: "var(--theme-muted, #6f5d6a)", display: "flex", gap: 5, alignItems: "center" }}><span style={{ color: "#A31551", fontSize: 8 }}>{String(i + 1).padStart(2, "0")}</span>{t(label)}</span>)}
      </div>
    </div>
  )
}

