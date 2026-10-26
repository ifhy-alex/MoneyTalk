import { useEffect, useRef } from "react";

import { cssVar, isDark, makeNoise, rgb, useReducedMotion, useSchemeVersion, type FieldShape } from "./core";

interface Props {
  shape: FieldShape;
  /** Variable CSS del fondo sobre el que se dibuja (los rastros se desvanecen hacia ese color). */
  bg?: string;
  /** Partículas por cada 1000 px² de lienzo. */
  density?: number;
  className?: string;
}

type Kind = "income" | "top" | "rest";
interface Particle {
  x: number;
  y: number;
  life: number;
  kind: Kind;
}

/**
 * Campo de flujo: cada columna es un día. Las líneas suben los días en que entró más de lo
 * que salió, bajan cuando se gastó de más y se agitan con los gastos fuera de lo normal.
 * Verde = ingresos, dorado = la categoría que más pesa, tinta = lo demás.
 */
export default function FlowField({ shape, bg = "--paper", density = 0.75, className }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  const scheme = useSchemeVersion();
  // El dibujo vive fuera de React: el estado de la animación cambia 60 veces por segundo.
  const state = useRef<{ target: FieldShape; prev: FieldShape; mix: number; redraw?: () => void }>({
    target: shape,
    prev: shape,
    mix: 1,
  });

  useEffect(() => {
    const s = state.current;
    s.prev = s.target;
    s.target = shape;
    s.mix = 0;
    s.redraw?.(); // movimiento reducido: redibujar la imagen quieta con los datos nuevos
  }, [shape]);

  useEffect(() => {
    const el = host.current, cv = canvas.current;
    if (!el || !cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const noise = makeNoise(20261025);
    const fade = rgb(cssVar(el, bg) || "#eceee8");
    const dark = isDark(fade);
    const colors: Record<Kind, string> = {
      income: cssVar(el, "--accent"),
      top: cssVar(el, "--gold"),
      rest: cssVar(el, "--muted"),
    };
    const alpha: Record<Kind, number> = { income: dark ? 0.75 : 0.7, top: dark ? 0.8 : 0.75, rest: dark ? 0.4 : 0.38 };
    let w = 0, h = 0, t = 0, raf = 0, tick = 0, visible = true;
    let parts: Particle[] = [];
    const s = state.current;

    const kindFor = (f: FieldShape): Kind => {
      const r = Math.random();
      const inc = f.incomeShare * 0.9;
      return r < inc ? "income" : r < inc + f.topShare * 0.55 ? "top" : "rest";
    };
    const spawn = (p: Particle) => {
      p.x = Math.random() * w;
      p.y = Math.random() * h;
      p.life = 60 + Math.random() * 160;
      p.kind = kindFor(s.target);
      return p;
    };
    const at = (arr: number[], x: number) => {
      const f = Math.max(0, Math.min(arr.length - 1, (x / w) * (arr.length - 1)));
      const i = Math.floor(f), k = f - i;
      return arr[i]! * (1 - k) + (arr[Math.min(arr.length - 1, i + 1)] ?? arr[i]!) * k;
    };
    const flow = (x: number, y: number): [number, number] => {
      let tilt = at(s.target.tilt, x), pace = at(s.target.pace, x), jolt = at(s.target.jolt, x);
      if (s.mix < 1) {
        const m = s.mix;
        tilt = at(s.prev.tilt, x) * (1 - m) + tilt * m;
        pace = at(s.prev.pace, x) * (1 - m) + pace * m;
        jolt = at(s.prev.jolt, x) * (1 - m) + jolt * m;
      }
      const n = noise(x * 0.0042, y * 0.0042, t);
      const angle = -tilt * 0.85 + (n - 0.5) * Math.PI * (0.9 + jolt * 1.1);
      const speed = 1.1 + pace * 2.4;
      return [Math.cos(angle) * speed, Math.sin(angle) * speed];
    };
    const clear = () => {
      ctx.fillStyle = `rgb(${fade.join(",")})`;
      ctx.fillRect(0, 0, w, h);
    };
    const step = () => {
      for (const kind of ["rest", "income", "top"] as Kind[]) {
        ctx.strokeStyle = colors[kind];
        ctx.globalAlpha = alpha[kind];
        ctx.beginPath();
        for (const p of parts) {
          if (p.kind !== kind) continue;
          const [vx, vy] = flow(p.x, p.y);
          ctx.moveTo(p.x, p.y);
          p.x += vx;
          p.y += vy;
          ctx.lineTo(p.x, p.y);
          if (--p.life < 0 || p.x < -4 || p.x > w + 4 || p.y < -4 || p.y > h + 4) spawn(p);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    };
    const still = () => {
      // Movimiento reducido: el mismo dibujo, quieto (trazos acumulados sin animar).
      s.mix = 1;
      clear();
      parts.forEach(spawn);
      for (let i = 0; i < 160; i++) step();
    };
    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = el.clientWidth;
      h = el.clientHeight;
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.lineWidth = w < 640 ? 1.3 : 1.15;
      const n = Math.round(Math.min(1400, ((w * h) / 1000) * density));
      parts = Array.from({ length: n }, () => spawn({ x: 0, y: 0, life: 0, kind: "rest" }));
      clear();
      if (reduce) still();
      else {
        // Precalentar: que el dibujo aparezca ya formado y no como un lienzo vacío.
        for (let i = 0; i < 70; i++) {
          ctx.globalAlpha = 0.04;
          clear();
          step();
        }
      }
    };
    const frame = () => {
      // Fundido lento: rastros largos, el mes se lee como corrientes y no como rayitas. Cada
      // tanto un fundido más fuerte limpia los restos que deja el redondeo de 8 bits.
      ctx.globalAlpha = ++tick % 90 === 0 ? 0.18 : 0.022;
      clear();
      ctx.globalAlpha = 1;
      if (s.mix < 1) {
        s.mix = Math.min(1, s.mix + 0.012);
        // Al cambiar de periodo, la mitad de las líneas adopta los colores nuevos de a poco.
        if (Math.random() < 0.05) parts.forEach((p) => Math.random() < 0.08 && (p.kind = kindFor(s.target)));
      }
      step();
      t += 0.0016;
      raf = requestAnimationFrame(frame);
    };
    const sync = () => {
      cancelAnimationFrame(raf);
      if (!reduce && visible && !document.hidden) raf = requestAnimationFrame(frame);
    };

    s.redraw = reduce ? still : undefined;
    resize();
    const ro = new ResizeObserver(() => {
      if (el.clientWidth !== w || el.clientHeight !== h) resize();
    });
    ro.observe(el);
    // No gastar batería cuando el dibujo no se ve.
    const io = new IntersectionObserver(([e]) => {
      visible = Boolean(e?.isIntersecting);
      sync();
    });
    io.observe(el);
    document.addEventListener("visibilitychange", sync);
    if (reduce) still();
    sync();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", sync);
    };
  }, [bg, density, reduce, scheme]);

  return (
    <div ref={host} className={`flowfield ${className ?? ""}`} aria-hidden>
      <canvas ref={canvas} />
    </div>
  );
}
