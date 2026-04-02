"""
Componentes Discord (modais e views) do bolão e rotinas de canal/mensagem pública.

Inclui limpeza do canal ao iniciar novo bolão e atualização do embed após novas apostas.
"""

from __future__ import annotations

import logging

import discord

from cltbot import config
from cltbot.bolao import api as bolao_api
from cltbot.bolao.constants import MAX_BETS_PER_USER
from cltbot.bolao.embeds import build_bolao_embed, build_encerramento_embed_from_close
from cltbot.bolao.models import ActiveBolao, fetch_active
from cltbot.bolao.parsing import parse_golos_field

log = logging.getLogger(__name__)


class ApostaGolsModal(discord.ui.Modal):
    """
    Modal com dois campos de texto (golos do mandante e do visitante).

    Os rótulos usam os nomes dos times do bolão ativo.
    """

    def __init__(self, active: ActiveBolao, alvo: discord.User, guild: discord.Guild | None) -> None:
        """Constrói campos dinâmicos e guarda IDs necessários para validar e registar a aposta."""
        super().__init__(title="Palpite (golos)")
        self._bolao_id = active.id
        self.alvo = alvo
        self.guild = guild
        self._team_home = active.team_home
        self._team_away = active.team_away

        lab_casa = (active.team_home.strip() or "Mandante")[:45]
        lab_fora = (active.team_away.strip() or "Visitante")[:45]

        self._gols_casa = discord.ui.TextInput(
            label=lab_casa,
            placeholder="Ex.: 2",
            min_length=1,
            max_length=2,
            required=True,
        )
        self._gols_fora = discord.ui.TextInput(
            label=lab_fora,
            placeholder="Ex.: 4",
            min_length=1,
            max_length=2,
            required=True,
        )
        self.add_item(self._gols_casa)
        self.add_item(self._gols_fora)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Dá defer imediato, valida estado, envia aposta à API e atualiza a mensagem pública."""
        await interaction.response.defer(ephemeral=True)

        cur = await fetch_active()
        if cur is None or cur.id != self._bolao_id:
            await interaction.followup.send(
                "O bolão foi encerrado ou atualizado. Tente de novo com `/bolao aposta`.",
                ephemeral=True,
            )
            return

        uid = self.alvo.id
        n = sum(1 for b in cur.bets if b.user_id == uid)
        if n >= MAX_BETS_PER_USER:
            await interaction.followup.send(
                f"{self.alvo.mention} já tem **{MAX_BETS_PER_USER}** apostas neste bolão.",
                ephemeral=True,
            )
            return

        try:
            g1 = parse_golos_field(str(self._gols_casa.value))
            g2 = parse_golos_field(str(self._gols_fora.value))
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        pred = f"{g1}x{g2}"
        uname = self.alvo.name
        g = self.guild
        if g is not None:
            mem = g.get_member(uid)
            if mem is None:
                try:
                    mem = await g.fetch_member(uid)
                except discord.NotFound:
                    mem = None
            if mem is not None:
                uname = mem.display_name or mem.name

        _updated, err = await bolao_api.add_bet(
            self._bolao_id,
            discord_user_id=uid,
            username=uname[:80],
            prediction=pred,
            team_pick="",
        )
        if err:
            await interaction.followup.send(f"Erro ao guardar: {err}", ephemeral=True)
            return

        fresh = await fetch_active()
        if fresh is not None:
            await refresh_bolao_public_message(interaction.client, fresh)
        await interaction.followup.send(
            content=(
                f"Aposta registada para {self.alvo.mention}: **{self._team_home}** {g1} × "
                f"**{self._team_away}** {g2} (`{pred}`) — {n + 1}/{MAX_BETS_PER_USER} neste bolão."
            ),
            ephemeral=True,
        )


class EncerrarBolaoModal(discord.ui.Modal):
    """Modal para introduzir o placar final com os mesmos rótulos dos nomes dos times."""

    def __init__(self, active: ActiveBolao) -> None:
        """Define campos de golos para casa e fora conforme o bolão dado."""
        super().__init__(title="Resultado final (golos)")
        self._bolao_id = active.id
        self._th = active.team_home.strip() or "Mandante"
        self._ta = active.team_away.strip() or "Visitante"

        self._gols_casa = discord.ui.TextInput(
            label=(self._th[:45]),
            placeholder="Golos",
            min_length=1,
            max_length=2,
            required=True,
        )
        self._gols_fora = discord.ui.TextInput(
            label=(self._ta[:45]),
            placeholder="Golos",
            min_length=1,
            max_length=2,
            required=True,
        )
        self.add_item(self._gols_casa)
        self.add_item(self._gols_fora)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Encerra na API, publica embed de resultado no canal do bolão e confirma ao staff."""
        await interaction.response.defer(ephemeral=True)

        try:
            g1 = parse_golos_field(str(self._gols_casa.value))
            g2 = parse_golos_field(str(self._gols_fora.value))
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        result, err = await bolao_api.close_bolao(self._bolao_id, gols_casa=g1, gols_visitante=g2)
        if err or not result:
            await interaction.followup.send(
                f"Não foi possível encerrar: {err or 'erro desconhecido'}",
                ephemeral=True,
            )
            return

        embed = build_encerramento_embed_from_close(result)

        ch = interaction.client.get_channel(config.BOLAO_CHANNEL_ID)
        if ch is None:
            try:
                ch = await interaction.client.fetch_channel(config.BOLAO_CHANNEL_ID)
            except discord.HTTPException:
                ch = None
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=embed)
            except discord.HTTPException as e:
                log.warning("Envio mensagem encerramento: %s", e)
                await interaction.followup.send(
                    "Bolão encerrado na base de dados, mas **falhou publicar** no canal.",
                    ephemeral=True,
                )
                return

        await interaction.followup.send(
            "Bolão **encerrado**. Mensagem de resultado enviada ao canal do bolão.",
            ephemeral=True,
        )


class AbrirPalpiteView(discord.ui.View):
    """
    View com botão que abre o modal de palpite numa interação nova.

    Evita executar HTTP antes do primeiro ``defer`` no comando slash (limite de 3 s do Discord).
    """

    def __init__(
        self,
        admin_id: int,
        active: ActiveBolao,
        alvo: discord.User,
        guild: discord.Guild | None,
    ) -> None:
        """Associa o bolão, o alvo da aposta e restringe o botão ao staff que correu ``/bolao aposta``."""
        super().__init__(timeout=600)
        self._admin_id = admin_id
        self._active = active
        self._alvo = alvo
        self._guild = guild

    @discord.ui.button(label="Abrir formulário de palpite", style=discord.ButtonStyle.primary)
    async def abrir(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Abre o modal de palpite se quem clicou for o mesmo utilizador que usou o comando."""
        if interaction.user.id != self._admin_id:
            await interaction.response.send_message(
                "Só quem usou o comando pode abrir este formulário.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            ApostaGolsModal(self._active, self._alvo, self._guild)
        )


class AbrirEncerrarView(discord.ui.View):
    """View com botão que abre o modal de encerramento numa interação nova."""

    def __init__(self, admin_id: int, active: ActiveBolao) -> None:
        """Restringe o botão ao staff que invocou ``/bolao encerrar``."""
        super().__init__(timeout=600)
        self._admin_id = admin_id
        self._active = active

    @discord.ui.button(label="Abrir placar final", style=discord.ButtonStyle.danger)
    async def abrir(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Abre o modal de placar final para o mesmo utilizador que usou o comando."""
        if interaction.user.id != self._admin_id:
            await interaction.response.send_message(
                "Só quem usou o comando pode abrir este formulário.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(EncerrarBolaoModal(self._active))


async def refresh_bolao_public_message(client: discord.Client, active: ActiveBolao) -> None:
    """Atualiza o embed da mensagem fixa do bolão com a lista atual de apostas."""
    ch = client.get_channel(active.channel_id)
    if ch is None:
        try:
            ch = await client.fetch_channel(active.channel_id)
        except discord.HTTPException:
            return
    if not isinstance(ch, discord.TextChannel):
        return
    try:
        msg = await ch.fetch_message(active.message_id)
        await msg.edit(embed=build_bolao_embed(active), view=None)
    except discord.HTTPException as e:
        log.warning("Não foi possível atualizar mensagem do bolão: %s", e)


async def clear_bolao_channel(channel: discord.TextChannel) -> bool:
    """
    Remove pins, faz purge em lote e apaga mensagens antigas restantes no canal do bolão.

    Devolve ``False`` se o bot não tiver permissão para gerir mensagens.
    """
    try:
        for m in await channel.pins():
            try:
                await m.unpin()
            except discord.HTTPException:
                pass
    except discord.HTTPException as e:
        log.warning("Pins bolão: %s", e)

    try:
        while True:
            deleted = await channel.purge(limit=100)
            if len(deleted) < 100:
                break
    except discord.Forbidden:
        log.error("Sem permissão para limpar canal do bolão.")
        return False
    except discord.HTTPException as e:
        log.warning("Purge bolão parcial: %s", e)

    try:
        async for message in channel.history(limit=500):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
    except discord.Forbidden:
        pass

    return True
