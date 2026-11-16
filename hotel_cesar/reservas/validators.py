"""Validadores reutilizáveis (CPF e telefone)."""
import re

from django.core.exceptions import ValidationError


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf):
    """Retorna True se o CPF (somente dígitos) possuir dígitos verificadores válidos."""
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def validar_cpf(valor):
    if not cpf_valido(valor):
        raise ValidationError("Informe um CPF válido.", code="cpf_invalido")


def validar_telefone(valor):
    digitos = somente_digitos(valor)
    if len(digitos) not in (10, 11):
        raise ValidationError(
            "Informe um telefone válido com DDD, por exemplo (11) 91234-5678.",
            code="telefone_invalido",
        )
