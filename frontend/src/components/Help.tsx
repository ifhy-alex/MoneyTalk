import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { HELP } from "../help";

/** Botón "?" que abre un panel lateral con la explicación de la sección. */
export default function Help({ topic, label }: { topic: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const entry = HELP[topic];

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!entry) return null;
  return (
    <>
      <button
        className={label ? "help-btn wide" : "help-btn"}
        aria-label={`¿Qué es ${entry.title}?`}
        title={`¿Qué es ${entry.title}?`}
        onClick={() => setOpen(true)}
      >
        ?{label && <span>{label}</span>}
      </button>
      {open &&
        createPortal(
          <div className="drawer-backdrop" onClick={() => setOpen(false)}>
            <aside className="drawer" role="dialog" aria-modal="true" aria-label={entry.title} onClick={(e) => e.stopPropagation()}>
              <div className="drawer-head">
                <div>
                  <div className="eyebrow">Ayuda</div>
                  <h2>{entry.title}</h2>
                </div>
                <button className="nav" aria-label="Cerrar" onClick={() => setOpen(false)}>
                  ✕
                </button>
              </div>
              <p className="drawer-lead">{entry.what}</p>
              {entry.how && (
                <>
                  <h3>Cómo funciona</h3>
                  <ul>
                    {entry.how.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ul>
                </>
              )}
              {entry.terms && (
                <>
                  <h3>Qué significa cada cosa</h3>
                  <dl>
                    {entry.terms.map(([t, d]) => (
                      <div key={t}>
                        <dt>{t}</dt>
                        <dd>{d}</dd>
                      </div>
                    ))}
                  </dl>
                </>
              )}
              {entry.tip && <div className="drawer-tip">💡 {entry.tip}</div>}
            </aside>
          </div>,
          document.body,
        )}
    </>
  );
}
