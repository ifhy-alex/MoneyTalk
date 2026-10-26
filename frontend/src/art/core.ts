// Utilidades del arte generativo: ruido determinista, colores del tema y movimiento reducido.
// Todo el arte de la app sale de la misma familia: grabado de billete (líneas finas, rosetas
// guilloché, relieves) dibujado con los datos reales de la persona.
import { useEffect, useState } from "react";

/** Número pseudoaleatorio estable a partir de una semilla (mulberry32). */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Ruido de valor 3D suave (suficiente para campos de flujo; sin dependencias). */
export function makeNoise(seed: number) {
  const perm = new Uint8Array(512);
  const r = rng(seed);
  const p = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [p[i], p[j]] = [p[j]!, p[i]!];
  }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255]!;
  const val = (x: number, y: number, z: number) => perm[(perm[(perm[x & 255]! + y) & 255]! + z) & 255]! / 255;
  const fade = (t: number) => t * t * (3 - 2 * t);
  const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
  return (x: number, y: number, z: number) => {
    const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
    const u = fade(x - xi), v = fade(y - yi), w = fade(z - zi);
    const c = (dx: number, dy: number, dz: number) => val(xi + dx, yi + dy, zi + dz);
    return lerp(
      lerp(lerp(c(0, 0, 0), c(1, 0, 0), u), lerp(c(0, 1, 0), c(1, 1, 0), u), v),
      lerp(lerp(c(0, 0, 1), c(1, 0, 1), u), lerp(c(0, 1, 1), c(1, 1, 1), u), v),
      w,
    );
  };
}

export function useReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduce, setReduce] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const mq = matchMedia(query);
    const on = () => setReduce(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduce;
}

/** Cambia cuando el sistema pasa de claro a oscuro: los lienzos releen sus colores. */
export function useSchemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => setV((x) => x + 1);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return v;
}

export function cssVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/** "#rrggbb" → [r, g, b]. */
export function rgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, (c) => c + c) : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export const isDark = (bg: [number, number, number]) => bg[0] * 0.299 + bg[1] * 0.587 + bg[2] * 0.114 < 128;

// ─── Datos → forma del campo ───

export interface DayFlow {
  income: number;
  spend: number;
}

export interface FieldShape {
  tilt: number[]; // -1 gastó más de lo que entró … +1 ahorró
  pace: number[]; // volumen relativo de gasto 0…1
  jolt: number[]; // turbulencia: cuánto se aleja el día del promedio
  incomeShare: number;
  topShare: number;
}

export function fieldShape(days: DayFlow[], topShare = 0.3): FieldShape {
  if (days.length === 0) days = [{ income: 0, spend: 0 }];
  const net = days.map((d) => d.income - d.spend);
  const spend = days.map((d) => d.spend);
  // Suavizado de ±3 días: la quincena se lee como un cambio de rumbo, no como un pico aislado.
  const smooth = (arr: number[], r: number) =>
    arr.map((_, i) => {
      let s = 0, n = 0;
      for (let j = Math.max(0, i - r); j <= Math.min(arr.length - 1, i + r); j++) {
        s += arr[j]!;
        n++;
      }
      return s / n;
    });
  const sn = smooth(net, 3), ss = smooth(spend, 2);
  const maxNet = Math.max(1, ...sn.map(Math.abs));
  const maxSpend = Math.max(1, ...ss);
  const totalIn = days.reduce((a, d) => a + d.income, 0);
  const totalOut = days.reduce((a, d) => a + d.spend, 0);
  const mean = totalOut / days.length || 1;
  return {
    tilt: sn.map((v) => v / maxNet),
    pace: ss.map((v) => v / maxSpend),
    jolt: spend.map((v) => Math.min(1.6, Math.abs(v - mean) / mean)),
    incomeShare: totalIn / Math.max(1, totalIn + totalOut),
    topShare,
  };
}

/** Forma del campo a partir del resumen de un periodo (la misma regla en Inicio y Resumen). */
export function shapeFromSummary(d?: {
  daily: { income: string; expenses: string }[];
  by_category: Record<string, string>;
  expenses: string;
}): FieldShape {
  if (!d) return fieldShape([]);
  // La categoría que más pesa, sin contar lo que todavía no está clasificado.
  const top = Object.entries(d.by_category).find(([name]) => name !== "Sin categoría");
  return fieldShape(
    d.daily.map((x) => ({ income: Number(x.income), spend: Number(x.expenses) })),
    top ? Number(top[1]) / (Number(d.expenses) || 1) : 0.3,
  );
}
