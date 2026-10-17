# Arquitectura y decisiones técnicas

Documento para quien quiera entender o modificar el código. Para instalar y usar la app,
mirá el [README](../README.md).

## Componentes

```
docker compose
├─ db      Postgres 17 (127.0.0.1:5433)
├─ api     FastAPI + SQLAlchemy 2 + Alembic (127.0.0.1:8000, documentación en /docs)
├─ worker  APScheduler: Gmail cada 30 min, carpeta de entrada cada 2 min, tipo de cambio,
│          alertas, cotizaciones y resumen semanal
└─ web     React 19 + Vite + TypeScript + Recharts (127.0.0.1:5173)
```

| Módulo | Ruta (`backend/src/moneytalk/`) | Qué hace |
|---|---|---|
| Ingesta | `ingestion/` | Lectores por banco (patrón estrategia), Gmail de solo lectura, PDF con PyMuPDF, enmascarado, deduplicación |
| Categorización | `categorization/` | Reglas → memoria por comercio → Claude (solo como sugerencia) |
| Finanzas | `finance/` | Tipo de cambio (BCCR o mercado), presupuesto, metas, alertas, resumen semanal |
| Inversiones | `investments/` | Proveedores de mercado con caché, panorama de mercado, SEC EDGAR, screener, portafolio, comparador, backtesting, reportes |
| API | `api/` | Endpoints REST, uno por área |

## Decisiones

- **Una transacción canónica con varias fuentes.** El correo y el estado de cuenta describen
  el mismo gasto con textos y fechas distintos. La deduplicación exige misma cuenta, moneda
  y monto, fecha a ±3 días y un **tipo de fuente distinto** (dos correos idénticos pueden
  ser dos compras reales). El puntaje queda en `match_confidence`.
- **Enmascarado antes de guardar.** Todo documento pasa por `ingestion/privacy.py`: IBAN
  (se conserva solo el código de banco y los últimos 4 dígitos), números largos, teléfonos
  de SINPE, nombre del titular y correos. Los lectores trabajan sobre el texto enmascarado,
  así reprocesar da el mismo resultado.
- **Cuentas bimoneda.** La moneda no identifica la tarjeta; cada transacción guarda la suya.
- **Dinero en `NUMERIC(14,2)`** con signo (negativo = salida); nunca `float`.
- **Enums como VARCHAR + CHECK**, más fáciles de migrar que los ENUM nativos de Postgres.
  `backend/scripts/clean_enum_checks.py` limpia los CHECK duplicados del autogenerate.
- **Transferencias** (pago de tarjeta, entre cuentas propias) no cuentan como gasto ni
  como ingreso, para no duplicar.
- **Tipo de cambio:** BCCR (venta) si hay token; si no, mercado (Yahoo `CRC=X`). Un dato
  de mercado nunca reemplaza uno oficial.
- **Backtesting point-in-time:** solo usa los 10-K *presentados* antes de cada fecha.
- **APScheduler en un proceso aparte** (`worker`): con `--reload` en la API los jobs se
  duplicarían. Celery no se justifica para un solo usuario.
- **Gmail con OAuth + PKCE** desde la interfaz; el callback pasa por el proxy de Vite
  (`/api/gmail/callback`), así el *redirect URI* es `http://localhost:5173/...`, permitido
  para clientes OAuth de tipo escritorio.
- **Sin acceso a banca en línea:** solo correos y PDFs. No se guardan contraseñas bancarias
  ni números completos (CHECK `last4 ~ '^[0-9]{4}$'`); los logs también enmascaran.

## Agregar un banco nuevo

1. Creá `ingestion/parsers/<banco>.py` con una clase que herede de `EmailParser` o
   `StatementParser` (`can_parse` + `parse` → `list[ParsedTransaction]`).
2. Registrala en `ingestion/parsers/__init__.py` y, si es por correo, agregá su dominio en
   `ingestion/banks.py` con `parser=True`.
3. Agregá un ejemplo **anonimizado** en `backend/tests/fixtures/` y su prueba.

Si cambiás un lector, subí su `version`: `moneytalk reprocess` vuelve a leer los documentos
viejos desde el texto guardado.

## CLI

Desde `backend/` (o en el contenedor: `docker compose exec api moneytalk ...`):

| Comando | Qué hace |
|---|---|
| `uv run moneytalk gmail-auth` | Autoriza Gmail por consola (alternativa a la interfaz) |
| `uv run moneytalk ingest-gmail` | Lee correos nuevos de bancos |
| `uv run moneytalk ingest-pdf archivo.pdf --password` | Importa PDFs |
| `uv run moneytalk reprocess` | Reprocesa documentos fallidos o leídos con un lector viejo |
| `uv run moneytalk fx-sync` | Actualiza el tipo de cambio |
| `uv run moneytalk alerts` | Evalúa alertas y notifica |
| `uv run moneytalk weekly-summary` | Envía el resumen semanal por Telegram |

## Calidad

`ruff`, `mypy --strict` y `pytest` contra un Postgres real (cada prueba corre en una
transacción que se revierte); ESLint y `tsc` en el frontend. La CI está en
`.github/workflows/ci.yml`.

```bash
cd backend && uv sync && uv run pytest
cd frontend && npm ci && npm run lint && npm run build
```
