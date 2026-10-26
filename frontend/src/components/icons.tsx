// Íconos de línea propios (24×24, trazo 1.7) para no depender de una librería externa.
import type { ReactNode } from "react";

const svg = (children: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {children}
  </svg>
);

export const Icons = {
  flow: svg(<path d="M3 8c3-3 6 3 9 0s6 3 9 0M3 13c3-3 6 3 9 0s6 3 9 0M3 18c3-3 6 3 9 0s6 3 9 0" />),
  close: svg(<path d="M6 6l12 12M18 6 6 18" />),
  check: svg(<path d="M5 12.5 10 17.5 19 7" />),
  cross: svg(<path d="M7 7l10 10M17 7 7 17" />),
  home: svg(<path d="M3 11.5 12 4l9 7.5M5.5 9.5V20h13V9.5" />),
  list: svg(<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />),
  wallet: svg(
    <>
      <rect x="3" y="6" width="18" height="13" rx="2.5" />
      <path d="M16 12.5h2M3 9h18" />
    </>,
  ),
  target: svg(
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.8" />
    </>,
  ),
  bell: svg(<path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16ZM10 20.5h4" />),
  pulse: svg(<path d="M3 12h4l2.5-6 4 12 2.5-6H21" />),
  pie: svg(
    <>
      <path d="M12 3v9h9" />
      <path d="M20.5 15A9 9 0 1 1 9 3.5" />
    </>,
  ),
  filter: svg(<path d="M4 5h16l-6 7.5V19l-4-2v-4.5L4 5Z" />),
  doc: svg(
    <>
      <path d="M7 3h7l5 5v13H7z" />
      <path d="M14 3v5h5M10 13h6M10 17h6" />
    </>,
  ),
  scale: svg(<path d="M12 4v16M5 20h14M6 8h12M6 8l-3 6a3 3 0 0 0 6 0L6 8Zm12 0-3 6a3 3 0 0 0 6 0l-3-6Z" />),
  history: svg(
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4" />
      <path d="M12 8v4.5l3 2" />
    </>,
  ),
  rules: svg(<path d="M5 7h9M5 12h14M5 17h7M17 5l2 2-2 2" />),
  inbox: svg(<path d="M3 13l2.5-8h13L21 13v6H3v-6Zm0 0h5l1.5 2.5h5L16 13h5" />),
};
