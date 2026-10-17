import { useState } from "react";

import { api } from "../api";
import { Disclaimer, ErrorNotice } from "../components/ui";
import { money, pct } from "../format";
import { useApi } from "../hooks";
import Help from "../components/Help";

interface Option {
  id: number;
  name: string;
  kind: string;
  institution: string | null;
  currency: string;
  annual_rate: string;
  tax_rate: string;
  term_months: number | null;
  compounding: string;
  rate_date: string | null;
}
interface Row {
  name: string;
  currency: string;
  gross_rate: string;
  gross_interest: string;
  tax: string;
  net_interest: string;
  final_value: string;
  final_value_base: string;
  net_annual_yield_base: string;
  real_annual_yield: string;
}
interface CompareResult {
  assumptions: { fx_rate_start: string; end_fx_rate: string; break_even_depreciation: string | null };
  rows: Row[];
}

const KINDS: Record<string, string> = {
  cdp: "CDP",
  bond: "Bono",
  fund: "Fondo",
  savings: "Ahorro",
  equity_assumption: "Supuesto acciones/ETF",
};

export default function Comparator() {
  const options = useApi<Option[]>("/investments/fixed-income");
  const [form, setForm] = useState({
    name: "",
    kind: "cdp",
    institution: "",
    currency: "CRC",
    annual_rate: "",
    tax_rate: "15",
    term_months: "12",
    compounding: "simple",
  });
  const [params, setParams] = useState({ amount: "1000000", currency: "CRC", months: "12", colon_depreciation: "1", inflation: "3" });
  const [selected, setSelected] = useState<number[]>([]);
  const [result, setResult] = useState<CompareResult>();
  const [tbp, setTbp] = useState<string>();
  const [error, setError] = useState<string>();

  async function run<T>(fn: () => Promise<T>) {
    setError(undefined);
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const addOption = () =>
    run(async () => {
      await api.post("/investments/fixed-income", {
        ...form,
        institution: form.institution || null,
        annual_rate: Number(form.annual_rate) / 100,
        tax_rate: Number(form.tax_rate) / 100,
        term_months: Number(form.term_months) || null,
        rate_date: new Date().toISOString().slice(0, 10),
      });
      setForm({ ...form, name: "", annual_rate: "" });
      options.reload();
    });

  const loadTbp = () =>
    run(async () => {
      const r = await api.get<{ date: string; rate: string }>("/investments/bccr/tbp");
      setTbp(`${pct(r.rate, 2)} al ${r.date}`);
      setForm({ ...form, name: "TBP (referencia BCCR)", annual_rate: String(Number(r.rate) * 100), currency: "CRC" });
    });

  const compare = () =>
    run(async () =>
      setResult(
        await api.post<CompareResult>("/investments/compare", {
          amount: params.amount,
          currency: params.currency,
          months: Number(params.months),
          colon_depreciation: Number(params.colon_depreciation) / 100,
          inflation: Number(params.inflation) / 100,
          option_ids: selected,
        }),
      ),
    );

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Comparador local</h1>
            <Help topic="comparador" />
          </div>
          <div className="muted">CDP, bonos y fondos en Costa Rica con las tasas que ingresés (o la TBP del BCCR).</div>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error} />

      <div className="card">
        <h2>Agregar alternativa</h2>
        <div className="row end">
          <label className="field">
            Nombre
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="field">
            Tipo
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {Object.entries(KINDS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Entidad
            <input value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} />
          </label>
          <label className="field">
            Moneda
            <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option>CRC</option>
              <option>USD</option>
            </select>
          </label>
          <label className="field">
            Tasa bruta anual (%)
            <input type="number" step="0.01" value={form.annual_rate} onChange={(e) => setForm({ ...form, annual_rate: e.target.value })} />
          </label>
          <label className="field">
            Impuesto (%)
            <input type="number" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} />
          </label>
          <label className="field">
            Capitalización
            <select value={form.compounding} onChange={(e) => setForm({ ...form, compounding: e.target.value })}>
              <option value="simple">Simple (cupón)</option>
              <option value="monthly">Mensual</option>
              <option value="annual">Anual</option>
            </select>
          </label>
          <button className="primary" disabled={!form.name || !form.annual_rate} onClick={addOption}>
            Agregar
          </button>
          <button onClick={loadTbp}>Traer TBP del BCCR</button>
        </div>
        {tbp && <p className="small muted">Tasa básica pasiva: {tbp}</p>}
      </div>

      <div className="card">
        <h2>Alternativas guardadas</h2>
        <table>
          <tbody>
            {options.data?.map((o) => (
              <tr key={o.id}>
                <td style={{ width: 30 }}>
                  <input
                    type="checkbox"
                    checked={selected.includes(o.id)}
                    onChange={(e) => setSelected(e.target.checked ? [...selected, o.id] : selected.filter((x) => x !== o.id))}
                  />
                </td>
                <td>
                  <b>{o.name}</b> <span className="muted small">{o.institution}</span>
                </td>
                <td>
                  <span className="badge">{KINDS[o.kind]}</span>
                </td>
                <td>{o.currency}</td>
                <td className="num">{pct(o.annual_rate, 2)} bruta</td>
                <td className="small muted">
                  impuesto {pct(o.tax_rate, 0)} · {o.compounding}
                  {o.rate_date && ` · tasa del ${o.rate_date}`}
                </td>
                <td>
                  <button
                    className="link small"
                    onClick={() =>
                      run(async () => {
                        await api.del(`/investments/fixed-income/${o.id}`);
                        options.reload();
                      })
                    }
                  >
                    Borrar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row end" style={{ marginTop: 14 }}>
          <label className="field">
            Monto
            <input type="number" value={params.amount} onChange={(e) => setParams({ ...params, amount: e.target.value })} />
          </label>
          <label className="field">
            Moneda base
            <select value={params.currency} onChange={(e) => setParams({ ...params, currency: e.target.value })}>
              <option>CRC</option>
              <option>USD</option>
            </select>
          </label>
          <label className="field">
            Plazo (meses)
            <input type="number" value={params.months} onChange={(e) => setParams({ ...params, months: e.target.value })} />
          </label>
          <label className="field">
            Variación cambiaria anual (%)
            <input
              type="number"
              step="0.1"
              value={params.colon_depreciation}
              onChange={(e) => setParams({ ...params, colon_depreciation: e.target.value })}
            />
          </label>
          <label className="field">
            Inflación anual (%)
            <input type="number" step="0.1" value={params.inflation} onChange={(e) => setParams({ ...params, inflation: e.target.value })} />
          </label>
          <button className="primary" disabled={selected.length === 0} onClick={compare}>
            Comparar
          </button>
        </div>
      </div>

      {result && (
        <div className="card table-wrap">
          <h2>Resultado</h2>
          <p className="small muted">
            Tipo de cambio inicial ₡{Number(result.assumptions.fx_rate_start).toFixed(2)}, final supuesto ₡
            {Number(result.assumptions.end_fx_rate).toFixed(2)}.
            {result.assumptions.break_even_depreciation !== null && (
              <>
                {" "}
                Punto de equilibrio: con una variación cambiaria anual de{" "}
                <b>{pct(result.assumptions.break_even_depreciation, 2)}</b> la mejor opción en colones y la mejor en dólares
                rinden lo mismo.
              </>
            )}
          </p>
          <table>
            <thead>
              <tr>
                <th>Alternativa</th>
                <th className="num">Interés bruto</th>
                <th className="num">Impuesto</th>
                <th className="num">Valor final</th>
                <th className="num">Valor final ({params.currency})</th>
                <th className="num">Rend. neto anual</th>
                <th className="num">Rend. real</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((r) => (
                <tr key={r.name}>
                  <td>
                    <b>{r.name}</b> <span className="muted small">{r.currency}</span>
                  </td>
                  <td className="num">{money(r.gross_interest, r.currency)}</td>
                  <td className="num neg">{money(r.tax, r.currency)}</td>
                  <td className="num">{money(r.final_value, r.currency)}</td>
                  <td className="num">
                    <b>{money(r.final_value_base, params.currency)}</b>
                  </td>
                  <td className="num">{pct(r.net_annual_yield_base, 2)}</td>
                  <td className={`num ${Number(r.real_annual_yield) < 0 ? "neg" : "pos"}`}>{pct(r.real_annual_yield, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
