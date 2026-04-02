"""
Cliente Discord da aplicação: registo de comandos slash, views persistentes e ciclo de vida.

Define ``CltBot``, a instância global ``bot`` e a corrotina ``main`` que liga o token.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from cltbot import config
from cltbot.bolao import setup_app_commands
from cltbot.verification import (
    MottoConfirmView,
    VerificationView,
    ensure_verification_panel,
)

log = logging.getLogger(__name__)


class CltBot(discord.Client):
    """
    Cliente com árvore de comandos slash e suporte a componentes (botões, modais).

    Não usa *Message Content Intent*; toda a interação é por comandos ``/`` ou componentes.
    """

    def __init__(self) -> None:
        """Inicializa intents predefinidos e a árvore de comandos slash do discord.py."""
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """Regista views persistentes, monta comandos do bolão e sincroniza slash no servidor."""
        self.add_view(VerificationView())
        self.add_view(MottoConfirmView())
        setup_app_commands(self.tree)
        guild = discord.Object(id=config.GUILD_ID)
        synced = await self.tree.sync(guild=guild)
        n = len(synced) if synced is not None else 0
        log.info("Comandos slash sincronizados no servidor %s: %s", config.GUILD_ID, n)


bot = CltBot()


@bot.event
async def on_ready() -> None:
    """Regista o arranque e republica o painel de verificação Habbo no canal configurado."""
    log.info("Bot ligado como %s (%s)", bot.user, bot.user.id if bot.user else "?")
    await ensure_verification_panel(bot)


async def main() -> None:
    """Liga o bot ao Discord usando :data:`cltbot.config.DISCORD_TOKEN`."""
    await bot.start(config.DISCORD_TOKEN)
