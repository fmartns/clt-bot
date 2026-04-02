"""
Subpacote do **bolão de futebol**: modelos, API HTTP, UI e comandos slash.

O estado persistente vive no backend Django/PostgreSQL; o Discord apenas apresenta e recolhe interações.
"""

from cltbot.bolao.commands import setup_app_commands

__all__ = ["setup_app_commands"]
