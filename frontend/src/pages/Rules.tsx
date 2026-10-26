import { useState } from "react";

import { api, type Category, type MatchType, type Rule } from "../api";
import StringArt from "../art/StringArt";
import { useApi } from "../hooks";
import Help from "../components/Help";

interface Preview {
  matches: number;
  examples: string[];
}

const MATCH_LABEL: Record<MatchType, string> = {
  exact: "Igual a",
  contains: "Contiene la palabra",
  regex: "Regex",
};

export default function Rules() {
  const rules = useApi<Rule[]>("/rules");
  const cats = useApi<Category[]>("/categories");
  const [form, setForm] = useState({ match_type: "contains" as MatchType, pattern: "", category_id: 0, priority: 100 });
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState<string>();
  const [newCat, setNewCat] = useState("");

  async function run<T>(fn: () => Promise<T>) {
    setError(undefined);
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const doPreview = () => run(async () => setPreview(await api.post<Preview>("/rules/preview", form)));
  const save = () =>
    run(async () => {
      await api.post("/rules", form);
      setForm({ ...form, pattern: "" });
      setPreview(undefined);
      rules.reload();
    });
  const toggle = (r: Rule) =>
    run(async () => {
      await api.patch(`/rules/${r.id}`, { ...r, is_active: !r.is_active });
      rules.reload();
    });
  const remove = (r: Rule) =>
    run(async () => {
      await api.del(`/rules/${r.id}`);
      rules.reload();
    });
  const addCategory = () =>
    run(async () => {
      await api.post("/categories", { name: newCat });
      setNewCat("");
      cats.reload();
    });

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Reglas de categorización</h1>
            <Help topic="reglas" />
          </div>
          <div className="muted">
            Se evalúan por prioridad (mayor primero) sobre el comercio normalizado. Gana la primera.
          </div>
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}

      {rules.data && rules.data.length > 0 && (
        <figure className="card art-band">
          <StringArt
            threads={rules.data.map((r) => ({ from: r.pattern, to: r.category_name, active: r.is_active }))}
            label={`Hilorama de ${rules.data.length} reglas hacia sus categorías`}
          />
          <figcaption>
            Cada hilo es una regla: une un comercio con su categoría. Los haces más densos son las categorías que MoneyTalk
            ya clasifica sola; las reglas desactivadas van punteadas. Pasá el mouse por un hilo para ver cuál es.
          </figcaption>
        </figure>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h2>Nueva regla</h2>
          <div className="row end">
            <label className="field">
              Tipo
              <select
                value={form.match_type}
                onChange={(e) => setForm({ ...form, match_type: e.target.value as MatchType })}
              >
                {Object.entries(MATCH_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Patrón
              <input value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} />
            </label>
            <label className="field">
              Categoría
              <select
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })}
              >
                <option value={0} disabled>
                  Elegir…
                </option>
                {cats.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Prioridad
              <input
                type="number"
                style={{ width: 80 }}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              />
            </label>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={doPreview} disabled={!form.pattern}>
              Probar
            </button>
            <button className="primary" onClick={save} disabled={!form.pattern || !form.category_id}>
              Guardar y aplicar a pendientes
            </button>
          </div>
          {preview && (
            <p className="small">
              Coincide con <b>{preview.matches}</b> comercios: {preview.examples.join(", ") || "—"}
            </p>
          )}
        </div>
        <div className="card">
          <h2>Categorías</h2>
          <div className="row">
            <input placeholder="Nueva categoría" value={newCat} onChange={(e) => setNewCat(e.target.value)} />
            <button onClick={addCategory} disabled={!newCat}>
              Agregar
            </button>
          </div>
          <ul className="tag-list">
            {cats.data?.map((c) => (
              <li key={c.id} className="badge">
                {c.name}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Prioridad</th>
              <th>Tipo</th>
              <th>Patrón</th>
              <th>Categoría</th>
              <th>Activa</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rules.data?.map((r) => (
              <tr key={r.id}>
                <td className="num">{r.priority}</td>
                <td>{MATCH_LABEL[r.match_type]}</td>
                <td>
                  <code>{r.pattern}</code>
                </td>
                <td>{r.category_name}</td>
                <td>
                  <input type="checkbox" checked={r.is_active} onChange={() => toggle(r)} />
                </td>
                <td>
                  <button className="danger small" onClick={() => remove(r)}>
                    Borrar
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
