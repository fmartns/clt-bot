"""
Utilitários para obter :class:`discord.Member` a partir de interações.

Útil quando ``interaction.member`` não vem preenchido (ex.: certos modais).
"""

from __future__ import annotations

import discord


async def resolve_guild_member(interaction: discord.Interaction) -> discord.Member | None:
    """
    Devolve o membro do servidor associado ao utilizador da interação.

    Tenta ``interaction.member``, cache do servidor e ``fetch_member`` como último recurso.
    """
    guild = interaction.guild
    if guild is None:
        return None
    member = getattr(interaction, "member", None)
    if isinstance(member, discord.Member):
        return member
    member = guild.get_member(interaction.user.id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(interaction.user.id)
    except discord.NotFound:
        return None
