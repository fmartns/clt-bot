"""
Ponto de entrada ao executar ``python -m cltbot``.

Configura logging em stdout e arranca o cliente Discord de forma assíncrona.
"""

import asyncio
import logging
import sys

from cltbot.app import main as amain


def run() -> None:
    """Inicia o event loop e corre a função ``main`` do cliente Discord."""
    asyncio.run(amain())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    run()
