import { useState } from "react";

import { api, type IngestResult, type RawDocument } from "../api";
import { useApi } from "../hooks";

const STATUS_CLASS = { parsed: "ok", failed: "bad", ignored: "", pending: "warn" };

export default function Ingestion() {
  const docs = useApi<RawDocument[]>("/ingestion/documents");
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<IngestResult>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<IngestResult>) {
    setBusy(true);
    setError(undefined);
    try {
      setResult(await fn());
      docs.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function upload() {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (password) form.append("password", password);
    void run(() => api.post<IngestResult>("/ingestion/pdf", form)).then(() => setPassword(""));
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Ingesta</h1>
          <div className="muted">Correos de notificación (Gmail, solo lectura) y estados de cuenta en PDF.</div>
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}
      {result && (
        <div className="notice info">
          {result.documents_new} documentos nuevos, {result.documents_skipped} ya existían,{" "}
          {result.documents_failed} con error · {result.transactions_created} transacciones nuevas,{" "}
          {result.transactions_merged} fusionadas como duplicadas.
          {result.errors.map((e) => (
            <div key={e} className="small">
              {e}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h2>Estado de cuenta (PDF)</h2>
          <div className="row end">
            <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <label className="field">
              Contraseña (si está protegido; no se guarda)
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button className="primary" disabled={!file || busy} onClick={upload}>
              Importar
            </button>
          </div>
        </div>
        <div className="card">
          <h2>Gmail</h2>
          <p className="small muted">
            Lee la etiqueta configurada en <code>GMAIL_LABEL</code>. El worker también lo hace cada 30 minutos.
          </p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => run(() => api.post("/ingestion/gmail"))}>
              Sincronizar ahora
            </button>
            <button disabled={busy} onClick={() => run(() => api.post("/ingestion/reprocess-outdated"))}>
              Reprocesar fallidos/desactualizados
            </button>
          </div>
        </div>
      </div>

      <div className="card table-wrap">
        <h2>Documentos recibidos</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Origen</th>
              <th>Asunto / archivo</th>
              <th>Parser</th>
              <th>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {docs.data?.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td>{d.source_type === "email" ? "Correo" : "PDF"}</td>
                <td>
                  {d.subject ?? "—"}
                  {d.error && <div className="small neg">{d.error}</div>}
                </td>
                <td className="small muted">{d.parser_name ? `${d.parser_name} v${d.parser_version}` : "—"}</td>
                <td>
                  <span className={`badge ${STATUS_CLASS[d.status]}`}>{d.status}</span>
                </td>
                <td>
                  <button
                    className="link small"
                    onClick={() => run(() => api.post(`/ingestion/documents/${d.id}/reprocess`))}
                  >
                    Reprocesar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
