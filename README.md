# MoneyTalk

Sistema personal de finanzas e inversiones, local primero. Registra gastos a partir de
correos de notificación y estados de cuenta en PDF, los categoriza, controla presupuesto
y metas, y ayuda a analizar inversiones con criterios explícitos y auditables.

> **Aviso:** las secciones de inversiones muestran señales calculadas con criterios que
> vos definís, con su evidencia. No son asesoría financiera ni recomendaciones de compra
> o venta.

## Arquitectura

```
docker compose
├─ db      Postgres 17 (puerto 127.0.0.1:5433)
├─ api     FastAPI + SQLAlchemy 2 + Alembic (127.0.0.1:8000, docs en /docs)
├─ worker  APScheduler: Gmail cada 30 min, tipo de cambio, alertas, resumen semanal
└─ web     React + Vite + TypeScript + Recharts (127.0.0.1:5173)
```

| Módulo | Dónde | Qué hace |
|---|---|---|
| Ingesta | `backend/src/moneytalk/ingestion/` | Parsers por banco (patrón estrategia), Gmail solo lectura, PDF con PyMuPDF, deduplicación |
| Categorización | `categorization/` | Reglas → memoria por comercio → Claude (solo sugerencia) |
| Finanzas | `finance/` | Tipo de cambio BCCR, presupuesto, metas, alertas, resumen semanal |
| Inversiones | `investments/` | Proveedores de mercado con caché, SEC EDGAR, screener, portafolio, comparador, backtesting, reportes |

## Puesta en marcha (Windows)

Requisitos: Docker Desktop, [uv](https://docs.astral.sh/uv/) y Node 22.

```bash
cp .env.example .env
```

Editá `.env` (como mínimo `POSTGRES_PASSWORD` y las URLs que la usan) y levantá todo:

```bash
docker compose up -d --build
```

Abrí http://localhost:5173. Las migraciones corren solas al arrancar la API.

Para desarrollo y pruebas en el host:

```bash
cd backend && uv sync && uv run pytest
```

> En Windows usá `127.0.0.1` y no `localhost` en `DATABASE_URL`: `localhost` resuelve
> primero a IPv6 (`::1`), Docker publica solo en IPv4 y la conexión se queda colgada.

## Integraciones (todas opcionales)

| Integración | Variables | Cómo obtenerla |
|---|---|---|
| Gmail (solo lectura) | `GMAIL_LABEL` | Google Cloud → habilitar Gmail API → OAuth client *Desktop* → `data/gmail_credentials.json`. Luego `cd backend && uv run moneytalk gmail-auth` (en el host, abre el navegador). Creá un filtro en Gmail que etiquete los correos de tus bancos. |
| Tipo de cambio BCCR | `BCCR_EMAIL`, `BCCR_TOKEN` | Suscripción gratuita al servicio web de indicadores económicos del BCCR. Sin token se puede cargar el tipo de cambio a mano (`PUT /api/fx/manual`). |
| Claude | `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | Solo se usa para categorías dudosas y resúmenes de reportes. Solo se envían el comercio, el monto y la moneda (nunca tarjetas ni cuentas). Usa `fallbacks="default"`: si el modelo declina, el servidor reintenta con otro. |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | @BotFather → token; escribile al bot y consultá `getUpdates` para obtener el chat_id. |
| Mercado | `MARKET_PROVIDER` (`yfinance`, `fmp`, `alphavantage`) + keys | yfinance no requiere key. Las respuestas se cachean `MARKET_CACHE_TTL_HOURS`. |
| SEC EDGAR | `SEC_USER_AGENT` | La SEC exige un User-Agent con nombre y **tu correo real**. |

## CLI

Desde `backend/` (o dentro del contenedor con `docker compose exec api moneytalk ...`):

| Comando | Qué hace |
|---|---|
| `uv run moneytalk gmail-auth` | Autoriza Gmail (una vez) |
| `uv run moneytalk ingest-gmail` | Lee correos nuevos de la etiqueta |
| `uv run moneytalk ingest-pdf estado.pdf --password` | Importa PDFs (pide la contraseña si está protegido; no se guarda) |
| `uv run moneytalk reprocess` | Reprocesa documentos fallidos o leídos con un parser viejo |
| `uv run moneytalk fx-sync` | Descarga el tipo de cambio del BCCR |
| `uv run moneytalk alerts` | Evalúa alertas y notifica |
| `uv run moneytalk weekly-summary` | Envía el resumen semanal |

## Agregar un banco nuevo

1. Creá `ingestion/parsers/<banco>.py` con una clase que herede de `EmailParser` o
   `StatementParser` (`can_parse` + `parse` → `list[ParsedTransaction]`).
2. Registrala en `ingestion/parsers/__init__.py`.
3. Agregá un ejemplo **anonimizado** en `tests/fixtures/` y su prueba.

Si cambiás un parser, subí su `version`: `moneytalk reprocess` vuelve a leer los documentos
viejos desde el texto crudo guardado.

## Decisiones técnicas

- **Una transacción canónica con varias fuentes.** El correo y el estado de cuenta describen
  el mismo gasto con textos y fechas distintos. La deduplicación exige la misma cuenta,
  moneda y monto, una fecha a ±3 días y un **tipo de fuente distinto** (dos correos idénticos
  pueden ser dos compras reales). El puntaje queda guardado en `match_confidence`.
- **Cuentas bimoneda.** La moneda no identifica la tarjeta; cada transacción guarda la suya.
- **Monto con signo** (negativo = salida) en `NUMERIC(14,2)`; nunca `float` para dinero.
- **Enums como VARCHAR + CHECK** en lugar de ENUM nativo de Postgres, que es más fácil de
  migrar. `scripts/clean_enum_checks.py` limpia los CHECK duplicados que genera el autogenerate.
- **Transferencias** (pago de tarjeta, entre cuentas) no cuentan como gasto ni ingreso;
  si contaran, el gasto aparecería dos veces.
- **Conversión USD→CRC con el tipo de venta** del día de cada transacción (vista
  conservadora para presupuesto).
- **Backtesting point-in-time:** usa solo los 10-K *presentados* antes de cada fecha de
  rebalanceo, para no usar información del futuro.
- **APScheduler en un proceso aparte** (`worker`): con `--reload` en la API los jobs se
  duplicarían. Celery no se justifica para un solo usuario.
- **Sin acceso a banca en línea**: solo correos y PDFs. No se guardan contraseñas bancarias
  ni números completos (CHECK `last4 ~ '^[0-9]{4}$'`); los logs enmascaran tarjetas,
  IBAN y correos.

## Calidad

`ruff`, `mypy --strict`, `pytest` contra Postgres real (cada prueba corre en una
transacción que se revierte) y ESLint + `tsc` en el frontend. La CI está en
`.github/workflows/ci.yml`.

## Datos de ejemplo

Todos los fixtures son sintéticos. Para empezar de cero con la base local:

```bash
docker compose down -v
```
