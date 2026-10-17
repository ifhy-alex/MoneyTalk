// Textos de ayuda de cada sección. Cada entrada responde: qué es, cómo funciona y cómo leerlo.

export interface HelpEntry {
  title: string;
  what: string;
  how?: string[];
  terms?: [string, string][];
  tip?: string;
}

export const HELP: Record<string, HelpEntry> = {
  // ── Finanzas ──
  resumen: {
    title: "Resumen",
    what: "Tu foto financiera del periodo elegido: cuánto entró, cuánto salió y en qué se fue. Podés ver un mes o un año completo.",
    how: [
      "Suma todas tus transacciones del periodo (correos, PDFs y lo que subiste a mano).",
      "Los movimientos en dólares se pasan a colones con el tipo de cambio del día de cada movimiento.",
      "Las transferencias (por ejemplo, pagar la tarjeta o mover plata entre tus cuentas) no cuentan como gasto ni como ingreso; si contaran, el gasto aparecería dos veces.",
    ],
    terms: [
      ["Neto", "Ingresos menos gastos. Si es negativo, gastaste más de lo que entró."],
      ["Tasa de ahorro", "Neto dividido entre ingresos: qué parte de lo que ganaste te quedó."],
      ["Sin categoría", "Gastos que todavía no clasificaste. Confirmalos en Transacciones para que los gráficos sean fieles."],
    ],
    tip: "Usá las flechas ‹ › para moverte entre periodos y el botón Mes/Año para cambiar la escala.",
  },
  "resumen.categorias": {
    title: "Gasto por categoría",
    what: "En qué se fue tu dinero, ordenado de mayor a menor.",
    how: ["Cada barra suma los gastos confirmados o sugeridos de esa categoría en el periodo, en colones."],
    tip: "Si 'Sin categoría' es grande, el gráfico todavía no refleja tu realidad: categorizá primero.",
  },
  "resumen.evolucion": {
    title: "Evolución de 12 meses",
    what: "Ingresos (verde) contra gastos (rojo) mes a mes, con la línea de neto.",
    how: ["En vista mensual muestra los 12 meses que terminan en el mes elegido; en vista anual, enero a diciembre."],
    tip: "Buscá meses donde la barra roja supera a la verde: ahí el neto fue negativo.",
  },
  "resumen.ritmo": {
    title: "Ritmo de gasto",
    what: "Cómo se fue acumulando el gasto a lo largo del periodo.",
    how: [
      "Las barras son el gasto de cada día (o de cada mes, en la vista anual).",
      "La curva es el gasto acumulado: si sube muy rápido al inicio del mes, vas gastando adelantado.",
    ],
  },
  "resumen.mas": {
    title: "Análisis adicional",
    what: "Detalles que ayudan a entender patrones: comercios donde más gastás, qué días de la semana gastás más y la mezcla de monedas.",
  },
  transacciones: {
    title: "Transacciones",
    what: "La lista de todos tus movimientos, ya deduplicados (si el mismo gasto llegó por correo y por PDF, aparece una sola vez).",
    how: [
      "Cada movimiento tiene una categoría con un estado: Confirmada (la elegiste vos o una regla), Sugerida (la propuso la IA o un movimiento anterior del mismo comercio) o Sin categoría.",
      "Al elegir una categoría, la app te ofrece crear una regla para que ese comercio se clasifique solo en el futuro.",
    ],
    terms: [
      ["Visto en 2 fuentes", "El movimiento llegó por correo y por estado de cuenta; se fusionaron."],
      ["SINPE Móvil", "Transferencia a otra persona usando su número de teléfono. Categorizalo según el motivo (comida, alquiler, préstamo…)."],
    ],
  },
  presupuesto: {
    title: "Presupuesto",
    what: "Topes mensuales de gasto por categoría, en colones o en dólares.",
    how: [
      "El gasto en la otra moneda se convierte con el tipo de cambio del día.",
      "Un presupuesto 'para todos los meses' se puede sobrescribir solo para un mes específico.",
      "Cuando una categoría llega al 80 % (configurable) o se pasa, se genera una alerta.",
    ],
  },
  metas: {
    title: "Metas de ahorro",
    what: "Objetivos de ahorro con su avance. El fondo de emergencia es la meta prioritaria.",
    how: [
      "Registrás aportes (o retiros con monto negativo) y la app calcula el avance.",
      "Si indicás un aporte mensual, estima en cuántos meses llegás; si indicás una fecha, cuánto necesitás por mes.",
      "La sugerencia del fondo de emergencia es tu gasto promedio de los últimos 3 meses multiplicado por los meses que elijas (6 por defecto).",
    ],
    terms: [["Fondo de emergencia", "Dinero líquido para imprevistos (pérdida de trabajo, salud). Hasta completarlo, la app no muestra dinero 'disponible para invertir'."]],
  },
  alertas: {
    title: "Alertas y ajustes",
    what: "Avisos automáticos con la evidencia numérica que los disparó, y los ajustes que controlan su sensibilidad.",
    terms: [
      ["Gasto inusual", "Un gasto mayor que la media de su categoría más N desviaciones estándar (N = sensibilidad z). Con menos historia, se compara contra la mediana del comercio."],
      ["Presupuesto cerca del límite", "La categoría llegó al umbral configurado (80 % por defecto)."],
      ["Suscripción nueva", "Un cargo de suscripción de un comercio que no aparecía, o un monto similar que se repite en 3 meses distintos."],
      ["Suscripción duplicada", "El mismo servicio cobró dos veces en menos de 25 días."],
    ],
    tip: "Si recibís demasiadas alertas de gasto inusual, subí la sensibilidad z (por ejemplo, de 3 a 4).",
  },
  // ── Inversiones ──
  mercado: {
    title: "Mercado",
    what: "Panorama de los principales mercados con datos reales de Yahoo Finance (unos 15 minutos de retraso para EE. UU.).",
    how: [
      "Rendimientos por periodo: cuánto cambió el precio en 1 día, 1 semana, 1 mes, 3 meses, en lo que va del año y en 12 meses.",
      "Hacé clic en 'Ver gráfico' en cualquier tarjeta para ver su historia de hasta 5 años.",
    ],
    terms: [
      ["S&P 500", "Las 500 empresas más grandes de EE. UU. Es la referencia más usada del mercado."],
      ["Nasdaq", "Índice con mucho peso en tecnología."],
      ["VIX", "'Índice del miedo': volatilidad esperada del S&P 500. Arriba de 25–30 suele indicar nerviosismo."],
      ["Bono a 10 años", "Rendimiento de la deuda del gobierno de EE. UU.; si sube, encarece el crédito y suele presionar a las acciones."],
      ["MM50 / MM200", "Promedio del precio de las últimas 50 o 200 sesiones. Estar ▲ encima indica tendencia alcista de corto o largo plazo; ▼ debajo, bajista."],
      ["vs máx.", "Qué tan lejos está el precio de su máximo de las últimas 52 semanas."],
      ["ETF", "Fondo que cotiza en bolsa y replica un índice o una canasta; con una sola compra te diversificás en cientos de empresas."],
    ],
    tip: "Las tendencias describen lo que pasó, no predicen lo que va a pasar.",
  },
  "mercado.etfs": {
    title: "ETFs amplios de bajo costo",
    what: "Fondos indexados muy usados por inversionistas de largo plazo por su diversificación y sus comisiones bajas. Aparecen como referencia educativa, no como recomendación.",
    terms: [
      ["VOO / IVV", "Replican el S&P 500."],
      ["VTI", "Todo el mercado accionario de EE. UU. (~3 500 empresas)."],
      ["QQQ", "Las 100 mayores empresas no financieras del Nasdaq; más concentrado en tecnología."],
      ["VXUS", "Acciones fuera de EE. UU.; diversifica geográficamente."],
      ["BND", "Bonos de EE. UU. con grado de inversión: menos volatilidad que las acciones."],
      ["SCHD", "Empresas de EE. UU. con historial de dividendos."],
    ],
    tip: "Desde Costa Rica, los dividendos de EE. UU. tienen una retención del 30 %. Antes de invertir, consultá con un asesor autorizado por SUGEVAL.",
  },
  "mercado.sectores": {
    title: "Rotación sectorial",
    what: "Rendimiento de los 11 sectores del S&P 500 (con sus ETF SPDR) en el periodo elegido. Muestra hacia dónde se movió el dinero.",
  },
  portafolio: {
    title: "Portafolio",
    what: "Tus inversiones registradas a mano, su valor actual y cómo te fue frente al S&P 500.",
    how: [
      "Las posiciones se calculan a partir de tus compras y ventas, con costo promedio ponderado.",
      "La comparación replica cada compra o venta con el mismo monto en el índice el mismo día: así sabés si le ganaste al mercado considerando cuándo invertiste.",
      "'Disponible para invertir' = ingreso − gasto promedio − aportes a metas − colchón; queda en 0 hasta completar el fondo de emergencia.",
    ],
    terms: [
      ["Ganancia no realizada", "Lo que ganarías o perderías si vendieras hoy."],
      ["Realizada", "Ganancia o pérdida de lo que ya vendiste."],
      ["Peso", "Qué porcentaje del portafolio representa cada posición."],
    ],
  },
  screener: {
    title: "Screener fundamental",
    what: "Filtra empresas según criterios que vos definís (P/E, ROE, deuda…) y muestra la evidencia de cada criterio: valor real, umbral y de dónde salió el dato.",
    terms: [
      ["P/E", "Precio dividido entre la utilidad por acción: cuántos años de utilidades estás pagando. Más bajo es más barato, pero ojo con las empresas en problemas."],
      ["ROE", "Utilidad neta sobre patrimonio: qué tan rentable es el dinero de los accionistas. Arriba de 15 % se considera bueno."],
      ["Deuda / patrimonio", "Cuánto debe la empresa por cada colón de patrimonio. 1 = 100 %."],
      ["Flujo de caja libre", "Efectivo que queda después de invertir en la operación. Positivo es sano."],
      ["Margen neto", "Qué parte de cada venta queda como utilidad."],
      ["Payout", "Qué parte de la utilidad se reparte como dividendo."],
      ["Sin dato", "No hay información para ese criterio; no cuenta como cumplido."],
    ],
    tip: "Con los datos oficiales de la SEC activados, se usan los estados financieros del último 10-K cuando existen.",
  },
  reportes: {
    title: "Reportes trimestrales",
    what: "Qué cambió en el último reporte trimestral (10-Q) de una empresa de EE. UU., contra el trimestre anterior y el mismo trimestre del año pasado.",
    how: [
      "Las cifras salen directamente de la SEC.",
      "La IA solo redacta una explicación a partir de la tabla: no inventa datos ni recomienda.",
    ],
    terms: [
      ["Var. trimestral", "Cambio contra el trimestre inmediatamente anterior (puede tener efecto estacional)."],
      ["Var. anual", "Cambio contra el mismo trimestre del año anterior: elimina la estacionalidad."],
      ["UPA", "Utilidad por acción."],
    ],
  },
  comparador: {
    title: "Comparador local",
    what: "Compara alternativas de Costa Rica (CDP, bonos, fondos) con las tasas que ingresés o la tasa básica pasiva del BCCR.",
    how: [
      "Descuenta el impuesto sobre rendimientos (15 % por defecto).",
      "Para comparar colones con dólares asume una variación anual del tipo de cambio que vos elegís, y calcula el punto de equilibrio.",
      "Rendimiento real = rendimiento neto descontada la inflación.",
    ],
    terms: [
      ["CDP", "Certificado de depósito a plazo: prestás dinero al banco por un plazo fijo a una tasa conocida."],
      ["TBP", "Tasa básica pasiva: promedio de las tasas que pagan las entidades; referencia del BCCR."],
      ["Punto de equilibrio", "La devaluación anual a partir de la cual ahorrar en dólares rinde más que en colones."],
    ],
  },
  backtesting: {
    title: "Backtesting",
    what: "Prueba cómo habrían funcionado tus criterios en el pasado, comprando cada año las empresas que los cumplían.",
    how: [
      "Usa solo los estados financieros que ya se habían publicado en cada fecha (sin mirar el futuro).",
      "Compara la estrategia contra el universo completo y contra el S&P 500.",
    ],
    terms: [
      ["CAGR", "Crecimiento anual compuesto."],
      ["Sesgo de supervivencia", "Solo se prueban empresas que existen hoy; las que quebraron no aparecen, y eso infla los resultados."],
      ["Sobreajuste", "Ajustar los criterios hasta que el pasado se vea bien; rara vez se repite en el futuro."],
    ],
  },
  // ── Datos ──
  reglas: {
    title: "Reglas de categorización",
    what: "Reglas 'comercio → categoría' que clasifican tus movimientos automáticamente.",
    terms: [
      ["Contiene la palabra", "Coincide si el nombre del comercio contiene esa palabra completa (AYA no atrapa PLAYA)."],
      ["Igual a", "El comercio normalizado debe ser exactamente ese."],
      ["Regex", "Patrón avanzado de texto."],
      ["Prioridad", "Si dos reglas coinciden, gana la de mayor prioridad."],
    ],
  },
  ingesta: {
    title: "Ingesta",
    what: "Cómo entran tus movimientos al sistema, de forma segura y sin entrar a tu banca en línea.",
    how: [
      "Gmail: conectás tu cuenta con permiso de solo lectura y la app busca los correos de notificación de los bancos de Costa Rica cada 30 minutos.",
      "PDF: subí aquí el estado de cuenta o el reporte de movimientos, o guardalo en la carpeta data/inbox (se importa solo).",
      "Todo documento se guarda enmascarado: sin números completos de cuenta, sin IBAN, sin teléfonos ni tu nombre.",
    ],
    terms: [
      ["Ignorado", "Llegó un correo o PDF de un banco para el que todavía no hay lector; se guarda para procesarlo cuando lo haya."],
      ["Reprocesar", "Vuelve a leer el documento guardado (útil cuando se mejora un lector)."],
    ],
  },
};
