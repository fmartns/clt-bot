"""
Comandos slash do bolão (grupo ``/bolao``) e comando global ``/help`` do servidor.

Regista handlers na árvore de comandos via ``setup_app_commands``.

``GUILD_OBJ`` limita o ``/help`` ao servidor configurado. ``HELP_TEXT`` é o Markdown enviado
por esse comando.
"""

from __future__ import annotations

import discord
from discord import app_commands

from cltbot import config
from cltbot.bolao import api as bolao_api
from cltbot.bolao.constants import MAX_BETS_PER_USER
from cltbot.bolao.embeds import build_bolao_embed
from cltbot.bolao.models import active_from_api, fetch_active
from cltbot.bolao.parsing import format_match_display, parse_match_datetime
from cltbot.bolao.permissions import interaction_may_manage_bolao
from cltbot.bolao.ui import AbrirEncerrarView, AbrirPalpiteView, clear_bolao_channel

GUILD_OBJ = discord.Object(id=config.GUILD_ID)

HELP_TEXT = (
    "**Comandos (slash)**\n\n"
    "`/help` — Mostra esta ajuda.\n\n"
    "**Verificação Habbo** — use o painel com o botão **Verificar** no canal de verificação.\n\n"
    "**Bolão (futebol)** — dados guardados na **base de dados** (persistem após reinício do bot).\n"
    "• `/bolao iniciar` — *(staff)* Times, data/hora, premiação opcional; **no canal do bolão**. "
    "Limpa o canal e abre novo bolão.\n"
    "• `/bolao aposta` — *(staff)* Escolhe o utilizador e preenche golos por time.\n"
    "• `/bolao encerrar` — *(staff)* Abre formulário com **placar final** (obrigatório); publica vencedores.\n\n"
    "_Comandos por `/` — sem Message Content Intent._"
)


async def _execute_bolao_iniciar(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    th: str,
    ta: str,
    data_hora_str: str,
    prize: str | None,
) -> None:
    """
    Limpa o canal do bolão, cria registo na API, publica embed e guarda o ID da mensagem.

    Espera que ainda não exista bolão ativo e que o utilizador tenha permissão de gestão.
    """
    if await fetch_active() is not None:
        await interaction.response.send_message(
            "Já existe um bolão em andamento. Encerre-o antes de iniciar outro.",
            ephemeral=True,
        )
        return

    if not await interaction_may_manage_bolao(interaction):
        await interaction.response.send_message(
            "Sem permissão para iniciar bolão.",
            ephemeral=True,
        )
        return

    try:
        dt = parse_match_datetime(data_hora_str)
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return

    display = format_match_display(dt)
    th = th.strip()
    ta = ta.strip()
    prize_n = prize.strip() if prize and prize.strip() else None

    await interaction.response.defer(ephemeral=True)

    cleared = await clear_bolao_channel(channel)
    if not cleared:
        await interaction.followup.send(
            "Não consegui limpar o canal do bolão. Verifique permissões do bot (**Gerenciar mensagens**).",
            ephemeral=True,
        )
        return

    created, err = await bolao_api.start_bolao(
        channel_id=channel.id,
        team_home=th,
        team_away=ta,
        match_at_display=display,
        prize=prize_n,
    )
    if err or not created:
        await interaction.followup.send(
            f"Não foi possível criar o bolão na API: {err or 'erro'}",
            ephemeral=True,
        )
        return

    active = active_from_api(created)
    embed = build_bolao_embed(active)
    msg = await channel.send(embed=embed)
    patched = await bolao_api.patch_message_id(active.id, msg.id)
    if not patched:
        await interaction.followup.send(
            f"Bolão criado (id `{active.id}`), mas **não consegui guardar** o ID da mensagem. "
            "Verifique o backend.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        content=f"Bolão publicado em {channel.mention}.",
        ephemeral=True,
    )


def setup_app_commands(tree: app_commands.CommandTree) -> None:
    """
    Regista ``/help`` e o grupo ``/bolao`` (iniciar, aposta, encerrar) na árvore dada.

    Deve ser chamado uma vez durante o ``setup_hook`` do cliente.
    """

    @tree.command(name="help", description="Mostra comandos do bot (verificação Habbo e bolão)")
    @app_commands.guilds(GUILD_OBJ)
    async def cmd_help(interaction: discord.Interaction) -> None:
        """Mostra o texto de ajuda em mensagem visível só para quem executou o comando."""
        await interaction.response.send_message(HELP_TEXT, ephemeral=True)

    bolao = app_commands.Group(
        name="bolao",
        description="Bolão de futebol",
        guild_ids=[config.GUILD_ID],
    )

    @bolao.command(name="iniciar", description="Inicia um bolão (só admin, só no canal do bolão)")
    @app_commands.describe(
        time_casa="Time da casa (mandante)",
        time_visitante="Time visitante",
        data_hora="dd/mm/aaaa HH:MM (horário de Brasília)",
        premiacao="Premiação (opcional — deixe em branco se não houver)",
    )
    async def bolao_iniciar(
        interaction: discord.Interaction,
        time_casa: str,
        time_visitante: str,
        data_hora: str,
        premiacao: str | None = None,
    ) -> None:
        """Valida canal e servidor e delega o fluxo completo de abertura de bolão."""
        if not interaction.guild or interaction.guild.id != config.GUILD_ID:
            await interaction.response.send_message("Use este comando no servidor.", ephemeral=True)
            return
        ch = interaction.channel
        if not isinstance(ch, discord.TextChannel) or ch.id != config.BOLAO_CHANNEL_ID:
            await interaction.response.send_message(
                f"Use `/bolao iniciar` **no canal do bolão**: <#{config.BOLAO_CHANNEL_ID}>.",
                ephemeral=True,
            )
            return
        await _execute_bolao_iniciar(
            interaction,
            ch,
            time_casa,
            time_visitante,
            data_hora,
            premiacao,
        )

    @bolao.command(
        name="aposta",
        description="Regista palpite (golos por time); só administradores; máx. 2 por pessoa",
    )
    @app_commands.describe(usuario="Utilizador que está a apostar")
    async def bolao_aposta(
        interaction: discord.Interaction,
        usuario: discord.User,
    ) -> None:
        """Adia a resposta, verifica bolão e limite de apostas e envia botão para abrir o modal de golos."""
        if not interaction.guild or interaction.guild.id != config.GUILD_ID:
            await interaction.response.send_message("Use este comando no servidor.", ephemeral=True)
            return
        if not await interaction_may_manage_bolao(interaction):
            await interaction.response.send_message(
                "Só **administradores** (ou cargo configurado) podem registar apostas.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        active = await fetch_active()
        if active is None:
            await interaction.followup.send("Não há bolão ativo.", ephemeral=True)
            return

        uid = usuario.id
        n = sum(1 for b in active.bets if b.user_id == uid)
        if n >= MAX_BETS_PER_USER:
            await interaction.followup.send(
                f"{usuario.mention} já tem **{MAX_BETS_PER_USER}** apostas neste bolão.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            content=f"Palpite para {usuario.mention}. Clique no botão para preencher os golos.",
            view=AbrirPalpiteView(interaction.user.id, active, usuario, interaction.guild),
            ephemeral=True,
        )

    @bolao.command(
        name="encerrar",
        description="Encerra o bolão (formulário com placar final obrigatório)",
    )
    async def bolao_encerrar(interaction: discord.Interaction) -> None:
        """Adia a resposta e envia botão para abrir o modal de placar final (evita expirar o slash)."""
        if not interaction.guild:
            await interaction.response.send_message("Use no servidor.", ephemeral=True)
            return
        if not await interaction_may_manage_bolao(interaction):
            await interaction.response.send_message(
                "Apenas **administradores** (ou cargos configurados) podem encerrar o bolão.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        active = await fetch_active()
        if active is None:
            await interaction.followup.send("Não há bolão ativo para encerrar.", ephemeral=True)
            return

        await interaction.followup.send(
            content="Clique no botão para indicar o **resultado final** (golos).",
            view=AbrirEncerrarView(interaction.user.id, active),
            ephemeral=True,
        )

    tree.add_command(bolao)
