"""
Pacote da **verificação Habbo**: views persistentes, painel do canal e função de arranque.

Reexporta os símbolos necessários para registar o cliente e republicar o painel ao ligar.
"""

from cltbot.verification.service import MottoConfirmView, VerificationView, ensure_verification_panel

__all__ = [
    "MottoConfirmView",
    "VerificationView",
    "ensure_verification_panel",
]
