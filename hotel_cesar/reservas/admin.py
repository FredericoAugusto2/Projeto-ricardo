"""Configuração do Django Admin – Hotel Cesar Administração."""
from django.contrib import admin
from django.utils.html import format_html

from .models import Hospede, MensagemContato, Quarto, Reserva
from .templatetags.hotel_extras import brl, cpf as formatar_cpf, telefone as formatar_telefone


class ReservaInline(admin.TabularInline):
    model = Reserva
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("data_checkin", "data_checkout", "quarto", "status", "valor_total")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Hospede)
class HospedeAdmin(admin.ModelAdmin):
    list_display = ("id", "nome_completo", "cpf_formatado", "telefone_formatado", "email", "cidade", "estado", "data_cadastro")
    list_display_links = ("id", "nome_completo")
    list_filter = ("estado", "data_cadastro")
    search_fields = ("nome_completo", "cpf", "email", "telefone")
    ordering = ("nome_completo",)
    readonly_fields = ("data_cadastro",)
    date_hierarchy = "data_cadastro"
    inlines = [ReservaInline]
    fieldsets = (
        ("Dados pessoais", {"fields": ("nome_completo", "cpf", "data_nascimento")}),
        ("Contato", {"fields": ("telefone", "email")}),
        ("Endereço", {"fields": ("endereco", "cidade", "estado")}),
        ("Sistema", {"fields": ("data_cadastro",)}),
    )

    @admin.display(description="CPF", ordering="cpf")
    def cpf_formatado(self, obj):
        return formatar_cpf(obj.cpf)

    @admin.display(description="Telefone")
    def telefone_formatado(self, obj):
        return formatar_telefone(obj.telefone)


@admin.register(Quarto)
class QuartoAdmin(admin.ModelAdmin):
    list_display = ("numero", "tipo", "capacidade", "diaria", "status_colorido")
    list_filter = ("tipo", "status", "capacidade")
    search_fields = ("numero", "descricao")
    ordering = ("numero",)
    inlines = [ReservaInline]

    @admin.display(description="Diária", ordering="valor_diaria")
    def diaria(self, obj):
        return brl(obj.valor_diaria)

    @admin.display(description="Status", ordering="status")
    def status_colorido(self, obj):
        cores = {"DISPONIVEL": "#1e7e4a", "OCUPADO": "#b42318", "MANUTENCAO": "#b26b00"}
        return format_html('<strong style="color:{}">{}</strong>', cores.get(obj.status, "#333"), obj.get_status_display())


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "hospede", "quarto", "data_checkin", "data_checkout", "diarias", "total", "status", "origem")
    list_filter = ("status", "origem", "quarto__tipo", "data_checkin")
    search_fields = ("id", "hospede__nome_completo", "hospede__cpf", "quarto__numero")
    ordering = ("-data_checkin",)
    date_hierarchy = "data_checkin"
    autocomplete_fields = ("hospede",)
    list_select_related = ("hospede", "quarto")
    readonly_fields = ("data_reserva", "valor_diaria", "valor_total", "checkin_realizado_em", "checkout_realizado_em")
    fieldsets = (
        ("Reserva", {"fields": ("hospede", "quarto", "status", "origem")}),
        ("Período", {"fields": ("data_checkin", "data_checkout", "quantidade_hospedes")}),
        ("Valores (calculados automaticamente)", {"fields": ("valor_diaria", "valor_total")}),
        ("Registro de hospedagem", {"fields": ("data_reserva", "checkin_realizado_em", "checkout_realizado_em")}),
        ("Observações", {"fields": ("observacoes",)}),
    )

    @admin.display(description="Código", ordering="id")
    def codigo(self, obj):
        return obj.codigo

    @admin.display(description="Diárias")
    def diarias(self, obj):
        return obj.diarias

    @admin.display(description="Valor total", ordering="valor_total")
    def total(self, obj):
        return brl(obj.valor_total)


@admin.register(MensagemContato)
class MensagemContatoAdmin(admin.ModelAdmin):
    list_display = ("assunto", "nome", "email", "enviada_em", "lida")
    list_filter = ("lida", "enviada_em")
    search_fields = ("nome", "email", "assunto", "mensagem")
    ordering = ("-enviada_em",)
    readonly_fields = ("enviada_em",)
    list_editable = ("lida",)
