"""
Modelos de dados do bolão (espelho dos JSON devolvidos pela API Django).

Inclui conversão de respostas HTTP para objetos tipados e pedido do bolão ativo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cltbot.bolao import api as bolao_api


@dataclass
class Bet:
    """Uma aposta: utilizador Discord, texto do palpite e legado opcional de escolha de time."""

    user_id: int
    username: str
    prediction: str
    team_pick: str = ""


@dataclass
class ActiveBolao:
    """Estado do bolão em curso: jogo, mensagem no Discord e lista de apostas."""

    id: int
    message_id: int
    channel_id: int
    team_home: str
    team_away: str
    match_at_display: str
    prize: str | None
    bets: list[Bet]


def active_from_api(d: dict[str, Any]) -> ActiveBolao:
    """Constrói um ``ActiveBolao`` a partir do dicionário ``active`` da API."""
    bets = [
        Bet(
            user_id=int(b["user_id"]),
            username=str(b["username"]),
            prediction=str(b["prediction"]),
            team_pick=str(b.get("team_pick") or ""),
        )
        for b in d.get("bets", [])
    ]
    return ActiveBolao(
        id=int(d["id"]),
        message_id=int(d["message_id"]),
        channel_id=int(d["channel_id"]),
        team_home=str(d["team_home"]),
        team_away=str(d["team_away"]),
        match_at_display=str(d["match_at_display"]),
        prize=d.get("prize"),
        bets=bets,
    )


async def fetch_active() -> ActiveBolao | None:
    """Obtém o bolão ativo do servidor via API ou ``None`` se não houver."""
    raw = await bolao_api.fetch_active()
    if not raw:
        return None
    return active_from_api(raw)
