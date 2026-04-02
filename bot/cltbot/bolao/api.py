"""
Cliente HTTP assíncrono para os endpoints REST do bolão no backend Django.

Todas as funções comunicam com ``{API_BASE_URL}/bolao/...`` e devolvem dados ou mensagens de erro.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from cltbot import config

log = logging.getLogger(__name__)

BASE = f"{config.API_BASE_URL}/bolao"
"""Prefixo URL dos endpoints do bolão."""


async def fetch_active() -> dict[str, Any] | None:
    """GET ``/current/`` — devolve o dicionário ``active`` ou ``None`` se não existir bolão."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{BASE}/current/", params={"guild_id": config.GUILD_ID})
    if r.status_code != 200:
        log.warning("bolao/current HTTP %s", r.status_code)
        return None
    data = r.json()
    return data.get("active")


async def start_bolao(
    *,
    channel_id: int,
    team_home: str,
    team_away: str,
    match_at_display: str,
    prize: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """POST ``/start/`` — cria bolão; em sucesso devolve ``(payload, None)``, senão ``(None, erro)``."""
    payload = {
        "discord_guild_id": config.GUILD_ID,
        "channel_id": channel_id,
        "team_home": team_home,
        "team_away": team_away,
        "match_at_display": match_at_display,
        "prize": prize,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(f"{BASE}/start/", json=payload)
    if r.status_code != 201:
        try:
            err = r.json().get("error", r.text[:300])
        except Exception:
            err = r.text[:300]
        log.warning("bolao/start %s %s", r.status_code, err)
        return None, err
    return r.json(), None


async def patch_message_id(bolao_id: int, message_id: int) -> dict[str, Any] | None:
    """PATCH ``/{id}/message/`` — associa o ID da mensagem Discord ao bolão."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.patch(f"{BASE}/{bolao_id}/message/", json={"message_id": message_id})
    if r.status_code != 200:
        log.warning("bolao/message %s", r.status_code)
        return None
    return r.json()


async def add_bet(
    bolao_id: int,
    *,
    discord_user_id: int,
    username: str,
    prediction: str,
    team_pick: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """POST ``/{id}/bets/`` — regista uma aposta; devolve payload ou mensagem de erro."""
    payload = {
        "discord_user_id": discord_user_id,
        "username": username,
        "prediction": prediction,
        "team_pick": team_pick,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(f"{BASE}/{bolao_id}/bets/", json=payload)
    if r.status_code != 201:
        try:
            err = r.json().get("error", r.text[:200])
        except Exception:
            err = r.text[:200]
        return None, err
    return r.json(), None


async def close_bolao(
    bolao_id: int,
    *,
    gols_casa: int,
    gols_visitante: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """POST ``/{id}/close/`` — encerra com placar final e devolve vencedores ou erro."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{BASE}/{bolao_id}/close/",
            json={"gols_casa": gols_casa, "gols_visitante": gols_visitante},
        )
    if r.status_code != 200:
        try:
            err = r.json().get("error", r.text[:200])
        except Exception:
            err = r.text[:200]
        return None, err
    return r.json(), None
