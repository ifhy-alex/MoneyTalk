import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import Alerts from "./pages/Alerts";
import Budget from "./pages/Budget";
import Dashboard from "./pages/Dashboard";
import Goals from "./pages/Goals";
import Ingestion from "./pages/Ingestion";
import Rules from "./pages/Rules";
import Transactions from "./pages/Transactions";

const NAV: { group: string; items: { to: string; label: string }[] }[] = [
  {
    group: "Finanzas",
    items: [
      { to: "/resumen", label: "Resumen" },
      { to: "/transacciones", label: "Transacciones" },
      { to: "/presupuesto", label: "Presupuesto" },
      { to: "/metas", label: "Metas" },
      { to: "/alertas", label: "Alertas y ajustes" },
    ],
  },
  {
    group: "Datos",
    items: [
      { to: "/reglas", label: "Reglas" },
      { to: "/ingesta", label: "Ingesta" },
    ],
  },
];

export default function App() {
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">MoneyTalk</div>
        {NAV.map((g) => (
          <div key={g.group}>
            <div className="nav-group">{g.group}</div>
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to}>
                {i.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/resumen" replace />} />
          <Route path="/resumen" element={<Dashboard />} />
          <Route path="/transacciones" element={<Transactions />} />
          <Route path="/presupuesto" element={<Budget />} />
          <Route path="/metas" element={<Goals />} />
          <Route path="/alertas" element={<Alerts />} />
          <Route path="/reglas" element={<Rules />} />
          <Route path="/ingesta" element={<Ingestion />} />
        </Routes>
      </main>
    </div>
  );
}
