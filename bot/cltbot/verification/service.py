"""
Fluxo completo de **verificação Habbo** no Discord.

Inclui botões persistentes, modal de nick, pedidos HTTP à API, aplicação de cargo e apelido,
limpeza do canal de verificação ao arrancar e ficheiros JSON locais para estado do painel e
mensagens efémeras a apagar no purge.

``pending_habbo_by_user`` guarda o nick Habbo por ID Discord enquanto a palavra secreta está
pendente na missão do jogo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import discord
import httpx

from cltbot import config
from cltbot.members import resolve_guild_member

log = logging.getLogger(__name__)

_PKG = Path(__file__).resolve().parent
VERIFY_PATH = "/users/verify/"
REFRESH_WORD_PATH = "/users/verify/refresh-word/"
STATE_FILE = _PKG / "verification_message.json"
EPHEMERAL_IDS_FILE = _PKG / "verification_ephemeral_ids.json"
BUTTON_VERIFY_ID = "cltbot:habbo_verify"
BUTTON_MOTTO_CONFIRM_ID = "cltbot:motto_confirm"
BUTTON_REFRESH_WORD_ID = "cltbot:refresh_word"

pending_habbo_by_user: dict[int, str] = {}


def _append_tracked_ephemeral_id(message_id: int) -> None:
    """Acrescenta o ID de uma mensagem efémera à lista persistida em disco (para apagar no purge)."""
    ids: list[int] = []
    if EPHEMERAL_IDS_FILE.exists():
        try:
            data = json.loads(EPHEMERAL_IDS_FILE.read_text(encoding="utf-8"))
            ids = [int(x) for x in data.get("ids", [])]
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            ids = []
    if message_id not in ids:
        ids.append(message_id)
    EPHEMERAL_IDS_FILE.write_text(
        json.dumps({"ids": ids}, indent=2),
        encoding="utf-8",
    )


async def _track_response_send(interaction: discord.Interaction, **kwargs: object) -> None:
    """Resposta inicial ephemeral + registro do ID (purge não apaga ephemeral do histórico)."""
    await interaction.response.send_message(**kwargs)  # type: ignore[arg-type]
    try:
        m = await interaction.original_response()
        _append_tracked_ephemeral_id(m.id)
    except discord.HTTPException:
        pass


async def _track_followup_send(interaction: discord.Interaction, **kwargs: object) -> None:
    """Envia follow-up efémera e regista o ID da mensagem para limpeza posterior do canal."""
    kwargs = dict(kwargs)
    kwargs.setdefault("ephemeral", True)
    kwargs.setdefault("wait", True)
    msg = await interaction.followup.send(**kwargs)  # type: ignore[arg-type]
    if msg is not None:
        _append_tracked_ephemeral_id(msg.id)


async def _delete_tracked_ephemeral_messages(channel: discord.TextChannel) -> None:
    """Apaga mensagens efémeras rastreadas e remove o ficheiro de IDs."""
    if not EPHEMERAL_IDS_FILE.exists():
        return
    try:
        data = json.loads(EPHEMERAL_IDS_FILE.read_text(encoding="utf-8"))
        ids = [int(x) for x in data.get("ids", [])]
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        ids = []
    removed = 0
    for mid in ids:
        try:
            await channel.get_partial_message(mid).delete()
            removed += 1
        except discord.HTTPException:
            pass
    try:
        EPHEMERAL_IDS_FILE.unlink()
    except OSError:
        pass
    if ids:
        log.info("Apagadas %s/%s respostas ephemeral rastreadas do fluxo de verificação.", removed, len(ids))


def _api_url() -> str:
    """URL completa do endpoint de verificação (POST nick / conclusão)."""
    return f"{config.API_BASE_URL}{VERIFY_PATH}"


def _refresh_word_url() -> str:
    """URL completa do endpoint que gera nova palavra secreta para a missão."""
    return f"{config.API_BASE_URL}{REFRESH_WORD_PATH}"


def _secret_word_message_content(code: str) -> str:
    """Texto da mensagem com a palavra a colocar na missão do Habbo (Markdown)."""
    return (
        "**Palavra secreta — coloque na missão do Habbo**\n\n"
        f"Coloque **somente** isto no seu **missão** no Habbo:\n"
        f"# **`{code}`**\n\n"
        "Você tem **5 minutos** para concluir. Se o Habbo **não aceitar** esta palavra, "
        "use **Trocar palavra** abaixo para gerar outra (o prazo é renovado).\n\n"
        "Salve o perfil e clique em **Verificar agora** abaixo.\n"
        "_A verificação ignora maiúsculas e acentos._"
    )


def _save_message_id(message_id: int) -> None:
    """Guarda o ID da mensagem do painel fixo em ``verification_message.json``."""
    STATE_FILE.write_text(
        json.dumps({"message_id": message_id}, indent=2),
        encoding="utf-8",
    )


def _verification_embed() -> discord.Embed:
    """Embed de boas-vindas do painel com o botão *Verificar*."""
    b = config.VERIFICATION_BULLET
    return discord.Embed(
        title="Bem-vindo(a)!",
        description=(
            "Para ter **acesso completo** ao servidor, vincule sua conta **Habbo** "
            "completando a verificação.\n\n"
            f"{b} Clique em **Verificar** abaixo para começar\n"
            f"{b} Depois de alterar a missão, use **Verificar agora** na mensagem do bot\n"
            f"{b} Você tem **5 minutos** por tentativa; se o jogo não aceitar a palavra, use **Trocar palavra**\n\n"
            "_As mensagens do bot neste fluxo são só para você._"
        ),
        color=0x5865F2,
    )


def _already_verified_embed(habbo_name: str) -> discord.Embed:
    """Resposta destacada quando a API indica que o utilizador já concluiu a verificação."""
    return discord.Embed(
        title="Conta já verificada",
        description=(
            f"Sua conta Habbo **{habbo_name}** já estava vinculada e confirmada.\n\n"
            "Não é preciso repetir a missão no jogo. O cargo de verificado e o apelido "
            "neste servidor foram conferidos ou atualizados."
        ),
        color=0x57F287,
    )


class MottoConfirmView(discord.ui.View):
    """Botões na mensagem da palavra secreta: verificar ou pedir nova palavra."""

    def __init__(self) -> None:
        """View persistente (sem timeout) com ``custom_id`` fixos para o bot reconhecer após reinício."""
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verificar agora",
        style=discord.ButtonStyle.success,
        custom_id=BUTTON_MOTTO_CONFIRM_ID,
        row=0,
    )
    async def verify_without_retyping(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Reenvia o pedido de verificação à API com o nick Habbo em memória."""
        if interaction.channel_id != config.VERIFICATION_CHANNEL_ID:
            await interaction.response.send_message(
                "Use este botão no fluxo do canal de verificação.",
                ephemeral=True,
            )
            return
        habbo = pending_habbo_by_user.get(interaction.user.id)
        if not habbo:
            await interaction.response.send_message(
                "Não há verificação em andamento. Clique em **Verificar** no canal e informe seu usuário Habbo.",
                ephemeral=True,
            )
            return
        await handle_verification_request(interaction, habbo)

    @discord.ui.button(
        label="Trocar palavra",
        style=discord.ButtonStyle.secondary,
        custom_id=BUTTON_REFRESH_WORD_ID,
        row=0,
    )
    async def refresh_word(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Pedido à API de nova palavra; atualiza a mensagem ou envia follow-up com o novo código."""
        if interaction.channel_id != config.VERIFICATION_CHANNEL_ID:
            await interaction.response.send_message(
                "Use este botão no fluxo do canal de verificação.",
                ephemeral=True,
            )
            return
        habbo = pending_habbo_by_user.get(interaction.user.id)
        if not habbo:
            await interaction.response.send_message(
                "Não há verificação em andamento. Clique em **Verificar** no canal e informe seu usuário Habbo.",
                ephemeral=True,
            )
            return

        payload = {
            "discord_id": str(interaction.user.id),
            "habbo_name": habbo,
        }

        await interaction.response.defer(ephemeral=True)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(_refresh_word_url(), json=payload)
        except httpx.RequestError as e:
            log.exception("API indisponível (refresh word)")
            await interaction.followup.send(
                content=f"Não foi possível falar com a API: `{e!s}`",
                ephemeral=True,
            )
            return

        try:
            data = r.json()
        except ValueError:
            data = {}

        if r.status_code == 200 and data.get("verification_code"):
            code = str(data["verification_code"])
            if interaction.message is not None:
                try:
                    await interaction.message.edit(
                        content=_secret_word_message_content(code),
                        view=MottoConfirmView(),
                    )
                except discord.HTTPException as e:
                    log.warning("Não foi possível editar mensagem com nova palavra: %s", e)
                    await interaction.followup.send(
                        content=_secret_word_message_content(code),
                        ephemeral=True,
                        view=MottoConfirmView(),
                    )
            else:
                await interaction.followup.send(
                    content=_secret_word_message_content(code),
                    ephemeral=True,
                    view=MottoConfirmView(),
                )
            return

        err = str(data.get("error", "Não foi possível trocar a palavra."))
        if r.status_code == 400 and "expired" in err.lower():
            pending_habbo_by_user.pop(interaction.user.id, None)
            await interaction.followup.send(
                content=(
                    "**Prazo de 5 minutos expirou.** Clique em **Verificar** no painel do canal "
                    "e informe seu nick Habbo de novo."
                ),
                ephemeral=True,
            )
            return

        err_pt = {
            "User already verified": "Esta conta Discord já está verificada.",
            "No pending verification": (
                "Não há verificação pendente. Clique em **Verificar** no painel e informe seu nick Habbo."
            ),
            "Habbo name does not match pending verification": (
                "O nick Habbo não confere com a verificação em andamento. "
                "Use **Verificar** de novo se mudou de conta."
            ),
        }.get(err, err)
        await interaction.followup.send(content=err_pt, ephemeral=True)


class VerificationView(discord.ui.View):
    """Painel público: um botão *Verificar* que abre o modal do nick Habbo."""

    def __init__(self) -> None:
        """Constrói o botão com ``custom_id`` fixo para persistência entre reinícios."""
        super().__init__(timeout=None)

        verify = discord.ui.Button(
            label="Verificar",
            style=discord.ButtonStyle.success,
            custom_id=BUTTON_VERIFY_ID,
        )
        verify.callback = self._on_verify
        self.add_item(verify)

    async def _on_verify(self, interaction: discord.Interaction) -> None:
        """Garante o canal certo e abre o modal do nick Habbo."""
        if interaction.channel_id != config.VERIFICATION_CHANNEL_ID:
            await _track_response_send(
                interaction,
                content="Use o botão apenas no canal de verificação.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(HabboModal())


class HabboModal(discord.ui.Modal, title="Nick no Habbo"):
    """Modal simples com um campo de texto para o utilizador indicar o nick no Habbo (hotel BR)."""

    habbo_name = discord.ui.TextInput(
        label="Nick no Habbo",
        placeholder="Nick exatamente como no jogo (hotel BR)",
        min_length=1,
        max_length=100,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Delega em ``handle_verification_request`` com o texto do campo."""
        await handle_verification_request(interaction, str(self.habbo_name.value))


async def handle_verification_request(interaction: discord.Interaction, habbo_name: str) -> None:
    """
    Envia o nick à API: conclui verificação, devolve palavra secreta ou mensagens de erro.

    Atualiza ``pending_habbo_by_user`` quando a API devolve código para a missão.
    """
    habbo_name = habbo_name.strip()
    if not habbo_name:
        await _track_response_send(
            interaction,
            content="Informe seu usuário Habbo.",
            ephemeral=True,
        )
        return

    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": interaction.user.name,
        "habbo_name": habbo_name,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(_api_url(), json=payload)
    except httpx.RequestError as e:
        log.exception("API indisponível")
        await _track_response_send(
            interaction,
            content=f"Não foi possível falar com a API: `{e!s}`",
            ephemeral=True,
        )
        return

    try:
        data = r.json()
    except ValueError:
        data = {}

    if r.status_code == 200:
        if data.get("success"):
            pending_habbo_by_user.pop(interaction.user.id, None)
            await _apply_verified(
                interaction,
                habbo_name,
                already=bool(data.get("already_verified")),
            )
            return
        if "verification_code" in data:
            code = data["verification_code"]
            pending_habbo_by_user[interaction.user.id] = habbo_name
            await _track_response_send(
                interaction,
                content=_secret_word_message_content(code),
                ephemeral=True,
                view=MottoConfirmView(),
            )
            return

    if r.status_code == 404:
        await _track_response_send(
            interaction,
            content="Usuário Habbo não encontrado. Confira o nome e o hotel (BR).",
            ephemeral=True,
        )
        return

    if r.status_code == 400:
        err = data.get("error", "Requisição inválida.")
        if "already verified" in err.lower():
            pending_habbo_by_user.pop(interaction.user.id, None)
            await _apply_verified(interaction, habbo_name, already=True)
            return
        if "incorrect" in err.lower() and data.get("verification_code"):
            code = str(data["verification_code"])
            pending_habbo_by_user[interaction.user.id] = habbo_name
            await _track_response_send(
                interaction,
                content=_secret_word_message_content(code),
                ephemeral=True,
                view=MottoConfirmView(),
            )
            return
        await _track_response_send(interaction, content=f"{err}", ephemeral=True)
        return

    await _track_response_send(
        interaction,
        content=f"Erro da API ({r.status_code}): `{data or r.text[:200]}`",
        ephemeral=True,
    )


def _explain_nick_forbidden(
    guild: discord.Guild,
    member: discord.Member,
    nick: str,
) -> str:
    """Motivos comuns de 403 ao alterar apelido (Discord)."""
    if member.id == guild.owner_id:
        return (
            "Cargo aplicado. O Discord **não permite** que bots alterem o apelido do **dono do servidor**. "
            f"Altere você mesmo o apelido para: **{nick}** (Configurações do servidor → seu perfil no servidor)."
        )

    me = guild.me
    if me is not None and not me.guild_permissions.manage_nicknames:
        return (
            "Cargo aplicado, mas o bot **não tem** a permissão *Gerenciar apelidos*. "
            "Ative essa permissão no **cargo do bot**. "
            f"Apelido sugerido: **{nick}**"
        )

    if me is not None and member.top_role.position >= me.top_role.position:
        return (
            "Cargo aplicado, mas o bot **não pode mudar apelido** de quem tem um cargo **acima ou igual** ao do bot. "
            "Em *Configurações do servidor → Cargos*, arraste o **cargo do bot para cima** do seu maior cargo. "
            f"Ou defina o apelido manualmente: **{nick}**"
        )

    return (
        "Cargo aplicado, mas não consegui **alterar o apelido** (limite do Discord ou nome inválido). "
        f"Defina manualmente: **{nick}**"
    )


async def _apply_verified(
    interaction: discord.Interaction,
    habbo_name: str,
    *,
    already: bool = False,
) -> None:
    """
    Atribui o cargo de verificado, define apelido no servidor e responde com sucesso ou aviso.

    Usa ``defer`` porque pode demorar; mensagens finais são follow-ups efémeras rastreadas.
    """
    if not interaction.guild:
        await _track_response_send(
            interaction,
            content="Este comando só funciona dentro do servidor.",
            ephemeral=True,
        )
        return

    role = interaction.guild.get_role(config.VERIFIED_ROLE_ID)
    if role is None:
        await _track_response_send(
            interaction,
            content="Cargo de verificado não encontrado (VERIFIED_ROLE_ID).",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    member = await resolve_guild_member(interaction)
    if member is None:
        await _track_followup_send(
            interaction,
            content="Não foi possível obter seu usuário no servidor. Tente de novo.",
        )
        return

    nick = habbo_name[:32]

    try:
        await member.add_roles(role, reason="Verificação Habbo concluída")
    except discord.Forbidden:
        await _track_followup_send(
            interaction,
            content=(
                "Não tenho permissão para **gerenciar cargos**. "
                "Coloque o cargo do bot **acima** do cargo verificado e conceda *Gerenciar cargos*."
            ),
        )
        return
    except discord.HTTPException as e:
        await _track_followup_send(interaction, content=f"Erro ao dar o cargo: `{e}`")
        return

    try:
        await member.edit(nick=nick, reason="Nome Habbo após verificação")
    except discord.Forbidden:
        await _track_followup_send(
            interaction,
            content=_explain_nick_forbidden(interaction.guild, member, nick),
        )
        return
    except discord.HTTPException:
        await _track_followup_send(
            interaction,
            content=(
                f"Cargo aplicado, mas o apelido **{nick}** foi recusado pelo Discord "
                "(caracteres ou tamanho). Ajuste manualmente se quiser."
            ),
        )
        return

    if already:
        await _track_followup_send(interaction, embed=_already_verified_embed(habbo_name))
    else:
        await _track_followup_send(
            interaction,
            content="Conta verificada! Cargo de verificado aplicado e apelido atualizado.",
        )


async def _clear_verification_channel(channel: discord.TextChannel) -> bool:
    """Apaga mensagens e desfixa pins. Retorna False se não tiver permissão para limpar."""
    await _delete_tracked_ephemeral_messages(channel)

    try:
        for m in await channel.pins():
            try:
                await m.unpin()
            except discord.HTTPException:
                pass
    except discord.HTTPException as e:
        log.warning("Não foi possível listar/despinar mensagens fixadas: %s", e)

    total = 0
    try:
        while True:
            deleted = await channel.purge(limit=100)
            total += len(deleted)
            if len(deleted) < 100:
                break
    except discord.Forbidden:
        log.error(
            "Sem permissão para **Gerenciar mensagens** no canal de verificação — "
            "não dá para limpar ao iniciar."
        )
        return False
    except discord.HTTPException as e:
        log.warning("Purge em lote parcial: %s", e)

    try:
        async for message in channel.history(limit=500):
            try:
                await message.delete()
            except discord.HTTPException:
                pass
    except discord.Forbidden:
        pass

    log.info("Canal de verificação limpo (purge ~%s mensagens em lote + restantes).", total)
    return True


async def ensure_verification_panel(client: discord.Client) -> None:
    """
    Limpa o canal de verificação, publica embed + view do painel e grava o ID da mensagem.

    Chamado no ``on_ready`` para garantir um único painel atualizado após cada arranque do bot.
    """
    channel = client.get_channel(config.VERIFICATION_CHANNEL_ID)
    if channel is None:
        channel = await client.fetch_channel(config.VERIFICATION_CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        log.error("VERIFICATION_CHANNEL_ID não é um canal de texto.")
        return

    cleared = await _clear_verification_channel(channel)
    if not cleared:
        log.error(
            "Painel **não** foi republicado: conceda ao bot **Gerenciar mensagens** "
            "no canal de verificação e reinicie."
        )
        return

    view = VerificationView()
    embed = _verification_embed()
    msg = await channel.send(embed=embed, view=view)
    _save_message_id(msg.id)
    log.info("Painel de verificação enviado (message_id=%s).", msg.id)

    try:
        await msg.pin(reason="Verificação Habbo — painel fixo")
    except discord.HTTPException:
        log.info("Não foi possível fixar a mensagem (permissão Gerenciar mensagens).")
