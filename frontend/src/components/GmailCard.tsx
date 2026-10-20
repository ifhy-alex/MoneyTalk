import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, type IngestResult } from "../api";
import { useApi } from "../hooks";

interface GmailStatus {
  has_credentials: boolean;
  connected: boolean;
  email: string | null;
  mode: string;
  banks: { name: string; domains: string[]; parser: boolean }[];
  extra_senders: string[];
  error: string | null;
}

const RESULT_MSG: Record<string, [string, string]> = {
  conectado: ["info", "Gmail quedó conectado con permiso de solo lectura."],
  cancelado: ["warn", "Cancelaste la autorización de Google; Gmail no se conectó."],
  error: ["error", "Google rechazó la autorización. Revisá que el cliente OAuth sea tipo Escritorio y que tu cuenta esté como usuario de prueba."],
};

export default function GmailCard({ onResult }: { onResult: (r: IngestResult) => void }) {
  const status = useApi<GmailStatus>("/gmail/status");
  const [params, setParams] = useSearchParams();
  const [msg, setMsg] = useState<[string, string]>();
  const [busy, setBusy] = useState(false);
  const [showBanks, setShowBanks] = useState(false);

  useEffect(() => {
    const r = params.get("gmail");
    if (r && RESULT_MSG[r]) {
      setMsg(RESULT_MSG[r]);
      params.delete("gmail");
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setMsg(undefined);
    try {
      await fn();
    } catch (e) {
      setMsg(["error", (e as Error).message]);
    } finally {
      setBusy(false);
      status.reload();
    }
  }

  const uploadCredentials = (file: File) =>
    act(async () => {
      const form = new FormData();
      form.append("file", file);
      await api.post("/gmail/credentials", form);
      setMsg(["info", "Credenciales cargadas. Ahora tocá «Conectar Gmail»."]);
    });

  const connect = () =>
    act(async () => {
      const { auth_url } = await api.get<{ auth_url: string }>(
        `/gmail/connect?origin=${encodeURIComponent(window.location.origin)}`,
      );
      window.location.href = auth_url;
    });

  const sync = () =>
    act(async () => {
      onResult(await api.post<IngestResult>("/ingestion/gmail"));
    });

  const s = status.data;
  const step = !s ? 0 : !s.has_credentials ? 1 : !s.connected ? 2 : 3;

  return (
    <div className="card">
      <div className="card-head">
        <h2>Gmail</h2>
        {s?.connected ? <span className="badge ok">Conectado</span> : <span className="badge">Sin conectar</span>}
      </div>
      {msg && <div className={`notice ${msg[0]}`}>{msg[1]}</div>}
      {s?.error && <div className="notice warn">{s.error}</div>}

      {step === 3 && s && (
        <>
          <p className="small">
            Cuenta: <b>{s.email}</b>
            <br />
            <span className="muted">
              Filtro: {s.mode}. Se revisa sola cada 30 minutos; la primera vez lee los últimos 120 días.
            </span>
          </p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={sync}>
              {busy ? "Sincronizando…" : "Sincronizar ahora"}
            </button>
            <button className="link small" onClick={() => act(() => api.post("/gmail/disconnect"))}>
              Desconectar
            </button>
          </div>
        </>
      )}

      {step > 0 && step < 3 && (
        <ol className="steps">
          <li className={step > 1 ? "done" : "current"}>
            <b>Crear el acceso en Google</b> (una sola vez, 5 minutos)
            <div className="small muted">
              En{" "}
              <a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank" rel="noreferrer">
                Google Cloud Console
              </a>{" "}
              creá un proyecto y habilitá la <i>Gmail API</i>. En <i>Pantalla de consentimiento OAuth</i> elegí «Externo», modo
              prueba, y agregá tu correo como usuario de prueba. En <i>Credenciales → Crear credenciales → ID de cliente OAuth</i>{" "}
              elegí tipo <b>App de escritorio</b> y descargá el JSON.
            </div>
            <label className="btn" style={{ display: "inline-block", marginTop: 8 }}>
              {s?.has_credentials ? "Reemplazar JSON" : "Subir JSON del cliente"}
              <input
                type="file"
                accept="application/json,.json"
                hidden
                onChange={(e) => e.target.files?.[0] && uploadCredentials(e.target.files[0])}
              />
            </label>
          </li>
          <li className={step === 2 ? "current" : ""}>
            <b>Autorizar tu cuenta</b>
            <div className="small muted">
              Se abre Google para que elijas tu cuenta y aceptes el permiso de <b>solo lectura</b>. MoneyTalk nunca puede enviar,
              borrar ni modificar correos.
            </div>
            <button className="primary" style={{ marginTop: 8 }} disabled={step !== 2 || busy} onClick={connect}>
              Conectar Gmail
            </button>
          </li>
        </ol>
      )}

      {s && (
        <>
          <p className="small muted" style={{ marginTop: 12, marginBottom: 4 }}>
            Busca correos de {s.banks.length} entidades de Costa Rica. Ya tienen lector:{" "}
            {s.banks.filter((b) => b.parser).map((b) => b.name).join(" y ")}; los demás se guardan para leerlos después.
          </p>
          <button className="link small" onClick={() => setShowBanks(!showBanks)}>
            {showBanks ? "Ocultar" : "Ver"} bancos que se buscan ({s.banks.length})
          </button>
          {showBanks && (
            <table className="small" style={{ marginTop: 8 }}>
              <tbody>
                {s.banks.map((b) => (
                  <tr key={b.name}>
                    <td>{b.name}</td>
                    <td className="muted mono">{b.domains.join(", ")}</td>
                    <td>
                      {b.parser ? (
                        <span className="badge ok">Lector listo</span>
                      ) : (
                        <span className="badge" title="Los correos se guardan y se procesan cuando exista el lector">
                          Se guarda
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
