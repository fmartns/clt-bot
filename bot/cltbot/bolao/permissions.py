"""
Regras de autorização para comandos e ações de staff relacionadas com o bolão.
"""

from __future__ import annotations

import discord

from cltbot import config
from cltbot.members import resolve_guild_member


async def interaction_may_manage_bolao(interaction: discord.Interaction) -> bool:
    """
    Indica se o utilizador da interação pode gerir o bolão (iniciar, apostar por outros, encerrar).

    Permite dono do servidor, administradores e membros com cargos listados em
    ``config.BOLAO_ADMIN_ROLE_IDS``.
    """
    g = interaction.guild
    if g is None:
        return False
    uid = interaction.user.id
    if uid == g.owner_id:
        return True
    perms = getattr(interaction, "permissions", None)
    if perms is not None and getattr(perms, "administrator", False):
        return True
    member = await resolve_guild_member(interaction)
    if member is None:
        return False
    if member.guild_permissions.administrator:
        return True
    if config.BOLAO_ADMIN_ROLE_IDS:
        role_ids = {r.id for r in member.roles}
        if role_ids.intersection(set(config.BOLAO_ADMIN_ROLE_IDS)):
            return True
    return False
