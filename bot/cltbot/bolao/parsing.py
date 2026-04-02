"""
Parsing de datas de jogo e de campos numéricos de golos introduzidos nos modais.
"""

from __future__ import annotations

from datetime import datetime

from cltbot.bolao.constants import BR_TZ


def parse_match_datetime(text: str) -> datetime:
    """
    Interpreta texto no formato ``dd/mm/aaaa HH:MM`` (opcionalmente com segundos) em ``datetime`` com ``BR_TZ``.

    Levanta ``ValueError`` com mensagem amigável se o formato for inválido.
    """
    s = text.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=BR_TZ)
        except ValueError:
            continue
    raise ValueError(
        "Data/hora inválida. Use **dd/mm/aaaa HH:MM** (ex.: `05/04/2026 16:00`)."
    )


def format_match_display(dt: datetime) -> str:
    """Formata data/hora para o texto guardado na API e mostrado no embed (rótulo com horário de Brasília)."""
    dt_br = dt.astimezone(BR_TZ)
    return dt_br.strftime("%d/%m/%Y %H:%M") + " (horário de Brasília)"


def parse_golos_field(text: str) -> int:
    """Converte o texto do campo de golos num inteiro entre 0 e 20; caso contrário levanta ``ValueError``."""
    s = text.strip()
    if not s.isdigit():
        raise ValueError("Indique apenas **números** nos golos (ex.: `2`).")
    v = int(s)
    if v < 0 or v > 20:
        raise ValueError("Golos devem estar entre **0** e **20**.")
    return v
