"""
Configuração carregada do ambiente (``.env`` / variáveis do sistema).

Variáveis obrigatórias: token Discord, IDs do servidor, canal de verificação, canal do bolão,
cargo de verificado e URL base da API. Listas opcionais definem cargos de staff do bolão.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    """Lê uma variável de ambiente obrigatória ou levanta ``RuntimeError`` se estiver ausente."""
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return v


DISCORD_TOKEN = _req("DISCORD_TOKEN")
GUILD_ID = int(_req("GUILD_ID"))
VERIFIED_ROLE_ID = int(_req("VERIFIED_ROLE_ID"))
API_BASE_URL = _req("API_BASE_URL").rstrip("/")

# Canal onde o bot mantém a mensagem fixa com o botão Verificar.
VERIFICATION_CHANNEL_ID = int(_req("VERIFICATION_CHANNEL_ID"))

# Canal exclusivo do bolão (mensagem única atualizada; limpo ao iniciar novo bolão).
BOLAO_CHANNEL_ID = int(_req("BOLAO_CHANNEL_ID"))


def _optional_id_list(name: str) -> list[int]:
    """Interpreta uma lista de IDs inteiros separados por vírgula (string vazia → lista vazia)."""
    raw = os.environ.get(name, "")
    if not raw.strip():
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out


def _optional_int(name: str) -> int | None:
    """Lê um inteiro opcional; string vazia ou ausente devolve ``None``."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return int(raw)


def _bolao_admin_role_ids() -> list[int]:
    """
    Combina ``BOLAO_ADMIN_ROLE_IDS`` com ``ADMIN_ROLE_ID`` (legado), sem duplicados.

    Estes cargos podem usar comandos de bolão além de quem tem permissão de administrador no servidor.
    """
    ids = _optional_id_list("BOLAO_ADMIN_ROLE_IDS")
    aid = _optional_int("ADMIN_ROLE_ID")
    if aid is not None and aid not in ids:
        ids.append(aid)
    return ids


BOLAO_ADMIN_ROLE_IDS = _bolao_admin_role_ids()

# Marcador visual das linhas do painel (ex.: emoji ou <:nome:id> do seu servidor)
VERIFICATION_BULLET = os.environ.get("VERIFICATION_BULLET", "🔹")
