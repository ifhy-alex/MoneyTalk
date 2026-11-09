# MoneyTalk

**Tus finanzas personales e inversiones en un solo lugar, en tu propia computadora.**

MoneyTalk lee tus movimientos bancarios a partir de los correos de notificación y de los
estados de cuenta en PDF, los ordena por categoría y te muestra en qué se va tu dinero,
cómo vas con tu presupuesto y tus metas, y qué está pasando en los mercados. Está pensado
para Costa Rica (colones y dólares, bancos locales, tipo de cambio del BCCR), pero sirve
para cualquiera.

**[⬇ Descargar MoneyTalk para Windows](https://github.com/ifhy-alex/MoneyTalk/releases/latest)**:
bajá `MoneyTalk-Setup.exe` y abrilo. No hace falta instalar nada más.

> ⚠️ **No es asesoría financiera.** Las secciones de inversiones muestran datos y señales
> calculadas con criterios que vos definís, siempre con su evidencia. Nunca son
> recomendaciones de compra o venta.

## Qué podés hacer

| Sección | Para qué sirve |
|---|---|
| **Inicio** | Lo primero que ves al abrir: tu mes dibujado, cuánto ahorraste y en qué gastaste más |
| **Resumen** | Ingresos, gastos y ahorro del mes o del año, gasto por categoría, evolución de 12 meses y ritmo de gasto |
| **Transacciones** | Todos tus movimientos, sin duplicados; los clasificás con un clic y la app aprende reglas |
| **Presupuesto y metas** | Topes mensuales por categoría y metas de ahorro (con el fondo de emergencia primero) |
| **Alertas** | Gastos inusuales, presupuestos al límite y suscripciones nuevas o duplicadas, también por Telegram |
| **Mercado** | Índices, ETFs, empresas grandes, sectores, oro, petróleo y bitcoin, con tendencias y gráficos de hasta 5 años |
| **Portafolio** | Tus inversiones, su rendimiento y la comparación contra el S&P 500 |
| **Screener, reportes, comparador y backtesting** | Herramientas para analizar empresas, entender sus reportes trimestrales y comparar con CDP y fondos locales |
| **Ingesta y reglas** | Importar estados de cuenta en PDF y correos de Gmail, y enseñarle a la app cómo clasificar cada comercio |

Cada sección tiene un botón **?** que explica qué es, cómo se calcula y qué significa cada dato.

### El arte de la app

Varias pantallas tienen arte generativo dibujado con tus propios datos, todo en la misma familia
visual: el grabado de un billete.

- **Inicio:** tu mes como un campo de flujo. Cada línea cruza el mes de izquierda a derecha,
  sube los días en que entró más de lo que salió y se agita con los gastos fuertes.
- **Resumen:** el mismo campo, en una franja, para el mes o año que estés viendo.
- **Metas:** cada meta tiene su roseta guilloché; se graba anillo por anillo con lo ahorrado y
  se vuelve dorada al cumplirse.
- **Presupuesto:** líneas que se tensan al acercarse al tope y se vuelven bermellón al pasarlo.
- **Mercado, Portafolio y Backtesting:** relieves de líneas con las series de precios.
- **Transacciones:** el mes como código de barras, un trazo por movimiento.
- **Alertas:** un sismógrafo del gasto diario con los días de alerta marcados.
- **Ingesta:** un sello grabado por cada documento recibido, del color de su estado.
- **Reglas:** un hilorama que une cada regla con su categoría.
- **Screener:** una tarjeta perforada con los criterios que cumple cada empresa.
- **Reportes:** una rosa de los vientos con cuánto creció o cayó cada métrica en el año.
- **Comparador:** un abanico con el crecimiento de cada opción desde el mismo monto.

El arte nunca reemplaza una cifra: los montos exactos siguen al lado. Con «reducir movimiento»
activado en el sistema, todo se dibuja quieto.

> `landing/index.html` es otra cosa: una página web de presentación, independiente de la app
> y con datos simulados, para mostrar MoneyTalk antes de descargarla.

## Privacidad

- **Todo corre en tu computadora.** Tu información queda en una base de datos local; no hay
  servidores de terceros.
- **Nunca entra a tu banca en línea** ni te pide claves del banco.
- Gmail se conecta con permiso de **solo lectura**: la app no puede enviar, borrar ni
  modificar correos.
- Antes de guardar cualquier documento se **enmascaran** los números de cuenta, tarjeta e
  IBAN (quedan solo los últimos 4 dígitos), los teléfonos de SINPE y tu nombre.
- Las contraseñas y llaves van únicamente en el archivo `.env`, que nunca se sube a git.

## App de escritorio (Windows)

La forma más fácil de usar MoneyTalk, y la que sirve para compartirla con familia y amigos:
no hace falta Docker, Python ni nada más.

**Para instalarla:** bajá `MoneyTalk-Setup.exe` de la
[página de descargas](https://github.com/ifhy-alex/MoneyTalk/releases/latest) y abrilo. Instala
sin pedir permisos de administrador y crea los accesos directos. Funciona en Windows 10 y 11 de
64 bits. Al abrirla arrancan solos la base de datos, la API y las tareas programadas; al cerrar
la ventana se apagan todos. La primera vez tarda unos segundos más, mientras prepara la base
de datos.

**Para actualizarla:** cerrá MoneyTalk, bajá el instalador nuevo y abrilo encima de la versión
que tenés. No hace falta desinstalar nada y tus datos se conservan.

- **Tus datos** quedan en `%LOCALAPPDATA%\MoneyTalk` (base de datos, PDFs, token de Gmail y
  registros). Actualizar o borrar la app no los toca; para empezar de cero, borrá esa carpeta.
- **Carpeta de entrada:** los PDF que dejés en `%LOCALAPPDATA%\MoneyTalk\data\inbox` se
  importan solos. En Ingesta hay un botón para abrirla.
- **Configuración opcional** (llave de Claude, BCCR, Telegram): editá
  `%LOCALAPPDATA%\MoneyTalk\.env` y volvé a abrir la app.
- La primera vez Windows SmartScreen puede avisar que la app no está firmada:
  «Más información» → «Ejecutar de todas formas».

**Para construirla** (en Windows, con [uv](https://docs.astral.sh/uv/) y Node 22):

```bash
powershell -ExecutionPolicy Bypass -File desktop\build.ps1
```

Deja la app en `dist\MoneyTalk\`, el zip en `dist\MoneyTalk-windows.zip` y, si tenés
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`), el
instalador en `dist\MoneyTalk-Setup.exe`. Para probar sin empaquetar: `uv run --group desktop python -m
moneytalk.desktop` dentro de `backend/` (después de `npm run build` en `frontend/`).

## Instalación con Docker (para desarrollo)

### 1. Requisitos

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Windows, macOS o
  Linux). Es lo único obligatorio.
- **Git**, para descargar el proyecto.

### 2. Descargar y configurar

```bash
git clone https://github.com/ifhy-alex/MoneyTalk.git
```

```bash
cd MoneyTalk
```

Copiá el archivo de configuración de ejemplo (en Windows, desde PowerShell, usá `copy` en
lugar de `cp`):

```bash
cp .env.example .env
```

Abrí `.env` con cualquier editor y cambiá `cambia-esto` por una contraseña propia en
`POSTGRES_PASSWORD` y en las dos líneas `DATABASE_URL` que la repiten. Todo lo demás es
opcional.

### 3. Arrancar

```bash
docker compose up -d --build
```

La primera vez tarda unos minutos. Cuando termine, abrí **http://localhost:5173**.

Para detenerla:

```bash
docker compose down
```

Tus datos se conservan entre reinicios. Para borrar todo y empezar de cero:
`docker compose down -v`.

## Cargar tus movimientos

En Costa Rica no hay una forma oficial y segura de conectarse directamente a la banca en
línea de una persona, así que MoneyTalk usa tres caminos seguros:

1. **Subir un PDF** (página **Ingesta**): el estado de cuenta o el reporte de movimientos que
   descargás de tu banco. Si está protegido, escribís la contraseña y no se guarda.
2. **Carpeta de entrada:** guardá los PDF ahí y se importan solos en un par de minutos. En la
   app de escritorio es `%LOCALAPPDATA%\MoneyTalk\data\inbox` (en **Ingesta** hay un botón
   «Abrir la carpeta»); con Docker, `data/inbox/` dentro del proyecto.
3. **Gmail, automático:** activá en tu banco los avisos por correo de cada compra y
   conectá Gmail desde **Ingesta → Gmail**. La app busca los correos de los bancos de Costa
   Rica cada 30 minutos.

Si un mismo gasto llega por correo y por PDF, aparece una sola vez.

### Conectar Gmail (una sola vez, ~5 minutos)

Google exige que cada persona cree su propio acceso. Esto garantiza que nadie más que vos
tenga permiso sobre tu correo.

1. Entrá a [Google Cloud Console](https://console.cloud.google.com/), creá un proyecto y
   habilitá la **Gmail API**.
2. En **Pantalla de consentimiento OAuth**, elegí *Externo*, dejala en modo de prueba y
   agregá tu correo como *usuario de prueba*.
3. En **Credenciales → Crear credenciales → ID de cliente OAuth**, elegí **App de escritorio**
   y descargá el JSON.
4. En MoneyTalk, **Ingesta → Gmail → Subir JSON del cliente** y después **Conectar Gmail**.
   En la app de escritorio la autorización se abre en tu navegador (Google no permite iniciar
   sesión dentro de la ventana de la app); cuando termines, la app lo detecta sola.

Mientras el proyecto de Google esté en modo de prueba, **Google vence la autorización cada 7
días**: cuando pase, volvé a tocar **Conectar Gmail**. El JSON del paso 3 sirve siempre; no hay
que repetir los pasos 1 a 3.

### Bancos soportados

| Banco | Qué lee | Estado |
|---|---|---|
| Banco Popular | Reporte de movimientos de cuenta (PDF) | Probado con reportes reales; valida el saldo fila por fila |
| BAC Credomatic | Correos de notificación y estado de tarjeta (PDF) | Basado en el formato típico; falta validar con ejemplos reales |
| Banco Nacional | Correos de notificación | Basado en el formato típico; falta validar con ejemplos reales |
| BCR, Davivienda, Promerica, LAFISE, BCT, Cathay, Improsa, cooperativas y mutuales | Correos de notificación | Se reciben y guardan; se procesan cuando exista su lector |

¿Tu banco no está o falla? Abrí un *issue* con un ejemplo **anonimizado** (sin números de
cuenta ni nombres) y se agrega su lector. Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Configuración opcional

Todo se configura en el archivo `.env`. En la app de escritorio está en
`%LOCALAPPDATA%\MoneyTalk\.env` (se crea solo, con cada opción explicada); con Docker, en la
raíz del proyecto. Nada de esto es obligatorio:

| Qué | Variables | Para qué |
|---|---|---|
| Tipo de cambio oficial | `BCCR_EMAIL`, `BCCR_TOKEN` | Suscripción gratuita al [servicio web del BCCR](https://www.bccr.fi.cr/indicadores-economicos/servicio-web). Sin esto se usa el tipo de cambio de mercado |
| Categorización con IA | `ANTHROPIC_API_KEY` | Claude sugiere categorías para comercios nuevos y explica reportes trimestrales. Solo recibe el comercio, el monto y la moneda |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Alertas y resumen semanal en tu celular. Creá el bot con @BotFather |
| Datos oficiales de la SEC | `SEC_USER_AGENT` | Poné tu nombre y correo real: la SEC lo exige para consultar estados financieros |
| PDFs con contraseña | `STATEMENT_PDF_PASSWORDS` | Para la carpeta de entrada y los adjuntos de Gmail |

Después de cambiar `.env`: en la app de escritorio, cerrala y volvé a abrirla; con Docker,
`docker compose up -d`.

## Preguntas frecuentes

**¿Los datos de la bolsa son reales?** Sí: vienen de Yahoo Finance, con unos 15 minutos de
retraso para EE. UU., y se actualizan cada 15 minutos.

**¿Cómo actualizo la app?** En la app de escritorio, cerrala y abrí el instalador de la
[última versión](https://github.com/ifhy-alex/MoneyTalk/releases/latest) encima de la que
tenés; tus datos se conservan. Con Docker, `git pull` y luego `docker compose up -d --build`.

**¿Puedo compartirla con mi familia?** Sí: pasales `MoneyTalk-Setup.exe` (o el enlace de
descarga). Cada persona tiene sus propios datos, guardados solo en su computadora. Lo más
simple para empezar es importar los PDF del banco; Gmail requiere los pasos de Google Cloud de
arriba.

**¿Windows dice que la app no es segura?** Pasa con apps nuevas que no están firmadas
digitalmente. Tocá «Más información» → «Ejecutar de todas formas». Algún antivirus podría
marcarla por el mismo motivo; se puede agregar como excepción.

**¿Puedo usarla sin Docker ni el instalador?** Sí, para desarrollo: mirá
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Tecnología

Python 3.12 · FastAPI · SQLAlchemy · PostgreSQL · React · TypeScript · Recharts.
La app de escritorio suma un PostgreSQL embebido (binarios de `pgserver`), una ventana nativa
con pywebview (WebView2) y se empaqueta con PyInstaller e Inno Setup. Docker se usa solo para
desarrollo. Detalles técnicos y decisiones de diseño en
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).
