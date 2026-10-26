import { useMemo } from "react";
import { Link } from "react-router-dom";

import FlowField from "../art/FlowField";
import { shapeFromSummary } from "../art/core";
import { money } from "../format";
import { useApi } from "../hooks";
import type { Dashboard } from "../types-finance";

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

function monthKey(offset: number): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const isEmpty = (d: Dashboard) => Number(d.income) === 0 && Number(d.expenses) === 0;
// 409 = todavía no hay tipo de cambio: la primera vez se descarga en segundo plano.
const RETRY = { retryOn: [409] };

/** Portada de la app: el mes real dibujado como campo de flujo, y lo primero que hay que saber. */
export default function Welcome() {
  const current = useApi<Dashboard>(`/dashboard?period=${monthKey(0)}`, RETRY);
  // A inicio de mes todavía no hay movimientos: solo entonces se pide el mes anterior.
  const needPrevious = current.data !== undefined && isEmpty(current.data);
  const previous = useApi<Dashboard>(needPrevious ? `/dashboard?period=${monthKey(-1)}` : null, RETRY);

  const data = !needPrevious ? current.data : previous.data && !isEmpty(previous.data) ? previous.data : undefined;
  // Listo para decidir qué mostrar: hay un mes con datos, o ya se sabe que no hay ninguno.
  const ready = data !== undefined || (needPrevious && (previous.data !== undefined || previous.error !== undefined));
  const empty = ready && data === undefined;

  const month = data ? MONTHS[Number(data.period.slice(5, 7)) - 1] : "";
  const top = data ? Object.entries(data.by_category).find(([name]) => name !== "Sin categoría") : undefined;
  const expenses = Number(data?.expenses ?? 0);
  const net = Number(data?.net ?? 0);
  const days = data?.daily.length || 1;
  const shape = useMemo(() => shapeFromSummary(data), [data]);

  return (
    <section className="welcome">
      <FlowField shape={shape} density={0.85} />
      <div className="welcome-copy">
        <h1>Tu dinero tiene algo que decir</h1>
        <p className="welcome-lede">
          {!ready
            ? current.status === 409
              ? "Preparando tus datos: el tipo de cambio se descarga solo y necesita internet."
              : (current.error ?? "Leyendo tus movimientos…")
            : empty
              ? "Todavía no hay movimientos. Importá un estado de cuenta o conectá Gmail y este dibujo pasa a ser tu mes."
              : net >= 0
                ? `En ${month} te quedaron ${money(net, "CRC")} de lo que entró.`
                : `En ${month} salieron ${money(-net, "CRC")} más de lo que entró.`}
        </p>
        {ready && (
          <div className="welcome-actions">
            {empty ? (
              <Link className="btn primary" to="/ingesta">
                Importar movimientos
              </Link>
            ) : (
              <>
                <Link className="btn primary" to="/resumen">
                  Ver el resumen de {month}
                </Link>
                <Link to="/transacciones">Ver transacciones</Link>
              </>
            )}
          </div>
        )}
      </div>

      {data && (
        <dl className="welcome-figures">
          <div>
            <dt>{net >= 0 ? "Ahorro del mes" : "Gastaste de más"}</dt>
            <dd className={net < 0 ? "neg" : undefined}>{money(Math.abs(net), "CRC")}</dd>
          </div>
          <div>
            <dt>{top ? `Tu mayor gasto: ${money(top[1], "CRC")}` : "Tu mayor gasto"}</dt>
            <dd>{top?.[0] ?? "—"}</dd>
          </div>
          <div>
            <dt>Gasto promedio por día</dt>
            <dd>{money(Math.round(expenses / days), "CRC")}</dd>
          </div>
        </dl>
      )}
      <p className="welcome-legend">
        {data
          ? `El fondo es ${month}: cada línea cruza el mes de izquierda a derecha, sube cuando entró más de lo que salió y se agita con los gastos fuertes.`
          : "El fondo se dibuja con tus movimientos: cada línea cruza el mes de izquierda a derecha."}{" "}
        <span className="key income">ingresos</span> <span className="key top">{top ? top[0].toLowerCase() : "lo que más pesa"}</span>{" "}
        <span className="key rest">lo demás</span>
      </p>
    </section>
  );
}
