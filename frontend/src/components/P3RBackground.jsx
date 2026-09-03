import { useEffect, useRef } from 'react'

// P3R 水下背景：渐变 + 光束 + 焦散纹理 + canvas 光斑/气泡 + 暗角
export default function P3RBackground() {
  const ref = useRef(null)

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    let W = 0, H = 0, blobs = [], bubbles = [], raf = 0

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = window.innerWidth; H = window.innerHeight
      cv.width = W * dpr; cv.height = H * dpr
      cv.style.width = W + 'px'; cv.style.height = H + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      blobs = Array.from({ length: 7 }, () => ({
        x: Math.random() * W, y: Math.random() * H, r: 120 + Math.random() * 220,
        a: .05 + Math.random() * .08, s: .15 + Math.random() * .25, p: Math.random() * 7,
      }))
      bubbles = Array.from({ length: 40 }, () => ({
        x: Math.random() * W, y: Math.random() * H, r: 1 + Math.random() * 3,
        v: .15 + Math.random() * .5, a: .1 + Math.random() * .3,
      }))
    }

    const frame = (now) => {
      const t = now / 1000
      ctx.clearRect(0, 0, W, H)
      ctx.globalCompositeOperation = 'lighter'
      blobs.forEach((b) => {
        const x = b.x + Math.sin(t * b.s + b.p) * 60
        const y = b.y + Math.cos(t * b.s * .8 + b.p) * 48
        const g = ctx.createRadialGradient(x, y, 0, x, y, b.r)
        g.addColorStop(0, `rgba(110,225,255,${b.a})`)
        g.addColorStop(1, 'rgba(110,225,255,0)')
        ctx.fillStyle = g
        ctx.beginPath(); ctx.arc(x, y, b.r, 0, 7); ctx.fill()
      })
      bubbles.forEach((bb) => {
        bb.y -= bb.v
        if (bb.y < -10) { bb.y = H + 10; bb.x = Math.random() * W }
        const x = bb.x + Math.sin(t + bb.y * .01) * 6
        ctx.fillStyle = `rgba(190,245,255,${bb.a})`
        ctx.beginPath(); ctx.arc(x, bb.y, bb.r, 0, 7); ctx.fill()
      })
      ctx.globalCompositeOperation = 'source-over'
      raf = requestAnimationFrame(frame)
    }

    resize()
    raf = requestAnimationFrame(frame)
    window.addEventListener('resize', resize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [])

  return (
    <div className="p3r-bg" aria-hidden="true">
      <div className="base" />
      <div className="rays" />
      <div className="caustic" />
      <canvas ref={ref} />
      <div className="vig" />
    </div>
  )
}
