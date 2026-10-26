import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { Icons } from "./components/icons";
import Ticker from "./components/Ticker";
import Alerts from "./pages/Alerts";
import Backtest from "./pages/Backtest";
import Budget from "./pages/Budget";
import Comparator from "./pages/Comparator";
import Dashboard from "./pages/Dashboard";
import Goals from "./pages/Goals";
import Ingestion from "./pages/Ingestion";
import Market from "./pages/Market";
import Portfolio from "./pages/Portfolio";
import Reports from "./pages/Reports";
import Rules from "./pages/Rules";
import Screener from "./pages/Screener";
import Transactions from "./pages/Transactions";
import Welcome from "./pages/Welcome";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  element: ReactNode;
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Finanzas",
    items: [
      { to: "/inicio", label: "Inicio", icon: Icons.flow, element: <Welcome /> },
      { to: "/resumen", label: "Resumen", icon: Icons.home, element: <Dashboard /> },
      { to: "/transacciones", label: "Transacciones", icon: Icons.list, element: <Transactions /> },
      { to: "/presupuesto", label: "Presupuesto", icon: Icons.wallet, element: <Budget /> },
      { to: "/metas", label: "Metas", icon: Icons.target, element: <Goals /> },
      { to: "/alertas", label: "Alertas y ajustes", icon: Icons.bell, element: <Alerts /> },
    ],
  },
  {
    group: "Inversiones",
    items: [
      { to: "/mercado", label: "Mercado", icon: Icons.pulse, element: <Market /> },
      { to: "/portafolio", label: "Portafolio", icon: Icons.pie, element: <Portfolio /> },
      { to: "/screener", label: "Screener", icon: Icons.filter, element: <Screener /> },
      { to: "/reportes", label: "Reportes trimestrales", icon: Icons.doc, element: <Reports /> },
      { to: "/comparador", label: "Comparador local", icon: Icons.scale, element: <Comparator /> },
      { to: "/backtesting", label: "Backtesting", icon: Icons.history, element: <Backtest /> },
    ],
  },
  {
    group: "Datos",
    items: [
      { to: "/reglas", label: "Reglas", icon: Icons.rules, element: <Rules /> },
      { to: "/ingesta", label: "Ingesta", icon: Icons.inbox, element: <Ingestion /> },
    ],
  },
];

export default function App() {
  return (
    <div className="layout">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <nav className="sidebar" aria-label="Navegación principal">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            ₡
          </div>
          <div>
            <div className="brand-name">MoneyTalk</div>
            <div className="brand-sub">Finanzas en Costa Rica</div>
          </div>
        </div>
        {NAV.map((g) => (
          <div key={g.group}>
            <div className="nav-group">{g.group}</div>
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to}>
                {i.icon}
                {i.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div className="side-foot">Local primero. Sin acceso a tu banca en línea: solo correos y PDFs.</div>
      </nav>
      <div className="content">
        <Ticker />
        <main id="contenido" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Navigate to="/inicio" replace />} />
            {NAV.flatMap((g) => g.items).map((i) => (
              <Route key={i.to} path={i.to} element={i.element} />
            ))}
          </Routes>
        </main>
      </div>
    </div>
  );
}
