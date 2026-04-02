"""
Construção de embeds Discord para o painel público do bolão e para a mensagem de encerramento.
"""

from __future__ import annotations

from typing import Any

import discord

from cltbot.bolao.constants import MAX_BETS_PER_USER
from cltbot.bolao.models import ActiveBolao


def _bets_lines(active: ActiveBolao) -> list[str]:
    """Gera linhas de texto descrevendo cada aposta (formato legado ou placar por time)."""
    out: list[str] = []
    th, ta = active.team_home.strip(), active.team_away.strip()
    for b in active.bets:
        legacy = (b.team_pick or "").strip()
        if legacy:
            out.append(f"**{b.username}** — time: **{legacy}** — `{b.prediction}`")
            continue
        parts = b.prediction.split("x", 1)
        if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            g1, g2 = parts[0].strip(), parts[1].strip()
            out.append(f"**{b.username}** — **{th}** {g1} × **{ta}** {g2}")
        else:
            out.append(f"**{b.username}** — `{b.prediction}`")
    return out


def build_bolao_embed(active: ActiveBolao) -> discord.Embed:
    """Monta o embed da mensagem fixa do bolão (jogo, hora, prémio opcional e lista de palpites)."""
    embed = discord.Embed(
        title="Bolão — jogo de futebol",
        color=0x57F287,
    )
    embed.add_field(
        name="Jogo",
        value=f"**{active.team_home}** × **{active.team_away}**",
        inline=False,
    )
    embed.add_field(
        name="Data e hora",
        value=active.match_at_display,
        inline=False,
    )
    if active.prize and active.prize.strip():
        embed.add_field(name="Premiação", value=active.prize.strip(), inline=False)

    total = len(active.bets)
    embed.add_field(
        name="Apostas registradas",
        value=str(total),
        inline=True,
    )
    lines = _bets_lines(active)
    if lines:
        body = "\n".join(lines)
        if len(body) > 3800:
            body = body[:3797] + "..."
        embed.add_field(name="Palpites", value=body, inline=False)
    else:
        embed.set_footer(
            text=f"Para apostar, fale com um administrador. Máx. {MAX_BETS_PER_USER} por pessoa."
        )
    return embed


def build_encerramento_embed_from_close(data: dict[str, Any]) -> discord.Embed:
    """
    Monta o embed publicado no canal após ``POST /bolao/{id}/close/``.

    Inclui resultado final, vencedores de placar exato, prémio e texto sobre levantamento.
    """
    th = str(data["team_home"])
    ta = str(data["team_away"])
    gc = int(data["gols_casa_final"])
    gv = int(data["gols_visitante_final"])
    winners: list[dict[str, Any]] = list(data.get("winners") or [])

    embed = discord.Embed(
        title="Bolão encerrado",
        description=f"Jogo: **{th}** × **{ta}**",
        color=0x5865F2,
    )
    embed.add_field(
        name="Resultado final",
        value=f"**{th}** {gc} × {gv} **{ta}**",
        inline=False,
    )

    if winners:
        lines: list[str] = []
        seen: set[int] = set()
        for w in winners:
            uid = int(w["discord_user_id"])
            if uid in seen:
                continue
            seen.add(uid)
            un = str(w.get("username", "?"))
            lines.append(f"<@{uid}> — **{un}**")
        body = "\n".join(lines)
        if len(body) > 1024:
            body = body[:1021] + "..."
        embed.add_field(name="Vencedores (placar exato)", value=body, inline=False)
    else:
        embed.add_field(
            name="Vencedores",
            value="Não houve apostas com **placar exato** a este resultado.",
            inline=False,
        )

    prize = data.get("prize")
    if prize and str(prize).strip():
        embed.add_field(
            name="Premiação (deste bolão)",
            value=str(prize).strip()[:1024],
            inline=False,
        )

    embed.add_field(
        name="Levantamento do prémio",
        value=(
            "Se foi vencedor ou tiver dúvidas sobre o resultado, **fale com um dos administradores** "
            "do servidor para combinar a **retirada do prémio**."
        ),
        inline=False,
    )
    return embed
