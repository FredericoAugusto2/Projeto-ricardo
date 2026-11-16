"""Filtros de template para formatação brasileira."""
from decimal import Decimal, InvalidOperation

from django import template

from ..validators import somente_digitos

register = template.Library()


@register.filter
def brl(valor):
    """Formata um número como moeda brasileira: R$ 1.234,56"""
    try:
        valor = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return "R$ 0,00"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


@register.filter
def cpf(valor):
    d = somente_digitos(valor)
    if len(d) != 11:
        return valor
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


@register.filter
def telefone(valor):
    d = somente_digitos(valor)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return valor


STATUS_CORES = {
    "DISPONIVEL": "success", "OCUPADO": "danger", "MANUTENCAO": "warning",
    "PENDENTE": "warning", "CONFIRMADA": "primary", "EM_ANDAMENTO": "info",
    "FINALIZADA": "success", "CANCELADA": "secondary",
}


@register.filter
def status_cor(valor):
    return STATUS_CORES.get(valor, "secondary")


@register.simple_tag(takes_context=True)
def url_com_parametros(context, **kwargs):
    """Preserva filtros da URL atual ao trocar de página."""
    query = context["request"].GET.copy()
    for chave, valor in kwargs.items():
        query[chave] = valor
    return "?" + query.urlencode()
