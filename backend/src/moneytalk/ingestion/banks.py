"""Remitentes de correo de las entidades financieras de Costa Rica.

Se usan para filtrar Gmail sin que tengas que crear etiquetas: la búsqueda es
`from:(dominio1 OR dominio2 ...)`. Gmail compara por coincidencia parcial del remitente,
así que basta el dominio. Si tu banco usa otro dominio, agregalo en GMAIL_EXTRA_SENDERS.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bank:
    name: str
    domains: tuple[str, ...]
    parser: bool  # ¿ya hay un lector para sus notificaciones?


CR_BANKS: list[Bank] = [
    Bank(
        "BAC Credomatic", ("baccredomatic.com", "notificacionesbaccr.com", "baccredomatic.cr"), True
    ),
    Bank("Banco Nacional", ("bncr.fi.cr",), True),
    Bank("Banco de Costa Rica", ("bancobcr.com", "bcr.fi.cr"), False),
    Bank("Banco Popular", ("bp.fi.cr", "bancopopular.fi.cr"), False),
    Bank("Davivienda", ("davivienda.cr", "davivienda.com"), False),
    Bank("Promerica", ("promerica.fi.cr",), False),
    Bank("Banco LAFISE", ("lafise.fi.cr", "lafise.com"), False),
    Bank("Banco BCT", ("bct.fi.cr",), False),
    Bank("Banco Cathay", ("bancocathay.fi.cr", "cathay.fi.cr"), False),
    Bank("Banco Improsa", ("improsa.com", "improsa.fi.cr"), False),
    Bank("Coopenae", ("coopenae.fi.cr",), False),
    Bank("Coopeservidores", ("coopeservidores.fi.cr",), False),
    Bank("Grupo Mutual", ("grupomutual.fi.cr",), False),
    Bank("MUCAP", ("mucap.fi.cr",), False),
]


def sender_query(extra: list[str] | None = None) -> str:
    domains = [d for b in CR_BANKS for d in b.domains] + [e for e in (extra or []) if e]
    return "from:(" + " OR ".join(domains) + ")"
