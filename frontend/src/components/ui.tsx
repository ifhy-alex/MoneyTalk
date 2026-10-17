import type { ReactNode } from "react";

export const CHART = {
  accent: "#1f8a70",
  accent2: "#5b7fd1",
  warn: "#d08a1f",
  danger: "#c2453c",
  grid: "#8883",
  palette: ["#1f8a70", "#5b7fd1", "#d08a1f", "#9b59b6", "#c2453c", "#2a9db5", "#7f8c3a", "#b5651d", "#6c757d"],
};

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="muted small">{hint}</div>}
    </div>
  );
}

export function Progress({ ratio }: { ratio: number }) {
  const cls = ratio >= 1 ? "bad" : ratio >= 0.8 ? "warn" : "";
  return (
    <div className={`progress ${cls}`} title={`${(ratio * 100).toFixed(0)} %`}>
      <div style={{ width: `${Math.min(ratio, 1) * 100}%` }} />
    </div>
  );
}

export function ErrorNotice({ error }: { error?: string }) {
  return error ? <div className="notice error">{error}</div> : null;
}

export function Disclaimer() {
  return (
    <div className="disclaimer">
      <b>No es asesoría financiera.</b> Las señales se calculan con criterios que vos definís y se muestran con su
      evidencia. Los datos de mercado pueden tener errores o retrasos. Verificá con fuentes oficiales antes de
      decidir.
    </div>
  );
}
