import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, qs, type Category, type RuleSuggestion, type Transaction } from "../api";
import { currentMonth, money, shortDate } from "../format";
import { useApi } from "../hooks";

const STATUS_LABEL = { uncategorized: "Sin categoría", suggested: "Sugerida", confirmed: "Confirmada" };
const STATUS_CLASS = { uncategorized: "bad", suggested: "warn", confirmed: "ok" };

export default function Transactions() {
  const [params] = useSearchParams();
  const [month, setMonth] = useState(params.get("status") ? "" : currentMonth());
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [q, setQ] = useState("");
  const txns = useApi<Transaction[]>(`/transactions${qs({ month, status, q })}`);
  const cats = useApi<Category[]>("/categories");
  const [suggestion, setSuggestion] = useState<(RuleSuggestion & { category: string }) | null>(null);
  const [message, setMessage] = useState<string>();

  async function confirmCategory(txn: Transaction, categoryId: number) {
    const res = await api.post<{ transaction: Transaction; rule_suggestion: RuleSuggestion | null }>(
      `/transactions/${txn.id}/category`,
      { category_id: categoryId },
    );
    const category = cats.data?.find((c) => c.id === categoryId)?.name ?? "";
    setSuggestion(res.rule_suggestion ? { ...res.rule_suggestion, category } : null);
    txns.reload();
  }

  async function createRule(s: RuleSuggestion) {
    const res = await api.post<{ applied_to: number }>("/rules", {
      match_type: s.match_type,
      pattern: s.pattern,
      category_id: s.category_id,
    });
    setSuggestion(null);
    setMessage(`Regla creada; se aplicó a ${res.applied_to} transacciones pendientes.`);
    txns.reload();
  }

  const pending = txns.data?.filter((t) => t.category_status !== "confirmed").length ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Transacciones</h1>
          <div className="muted">{pending} pendientes de confirmar en la vista actual</div>
        </div>
        <div className="row">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todas</option>
            <option value="suggested">Sugeridas</option>
            <option value="uncategorized">Sin categoría</option>
            <option value="confirmed">Confirmadas</option>
          </select>
          <input placeholder="Buscar comercio" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {message && <div className="notice info">{message}</div>}
      {suggestion && (
        <div className="notice warn row">
          <span>
            ¿Crear la regla <b>“{suggestion.pattern}” → {suggestion.category}</b>? Afectaría{" "}
            {suggestion.would_affect} transacciones más sin confirmar.
          </span>
          <span className="spacer" />
          <button className="primary" onClick={() => createRule(suggestion)}>
            Crear regla
          </button>
          <button onClick={() => setSuggestion(null)}>No, gracias</button>
        </div>
      )}
      {txns.error && <div className="notice error">{txns.error}</div>}

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Comercio</th>
              <th>Cuenta</th>
              <th className="num">Monto</th>
              <th>Categoría</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {txns.data?.map((t) => (
              <tr key={t.id}>
                <td>{shortDate(t.txn_date)}</td>
                <td>
                  <div>{t.merchant_raw}</div>
                  {t.ai_reason && <div className="muted small">{t.ai_reason}</div>}
                  {t.sources.length > 1 && (
                    <div className="muted small">Visto en {t.sources.length} fuentes (deduplicado)</div>
                  )}
                </td>
                <td className="muted small">{t.account_label}</td>
                <td className={`num ${Number(t.amount) < 0 ? "neg" : "pos"}`}>
                  {money(t.amount, t.currency)}
                </td>
                <td>
                  <select
                    value={t.category_id ?? ""}
                    onChange={(e) => confirmCategory(t, Number(e.target.value))}
                  >
                    <option value="" disabled>
                      Elegir…
                    </option>
                    {cats.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <span className={`badge ${STATUS_CLASS[t.category_status]}`}>
                    {STATUS_LABEL[t.category_status]}
                  </span>{" "}
                  {t.category_status === "suggested" && t.category_id && (
                    <button className="link small" onClick={() => confirmCategory(t, t.category_id!)}>
                      Aceptar
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {txns.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  No hay transacciones para estos filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
