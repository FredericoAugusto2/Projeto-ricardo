"""
Views do Hotel Cesar.

Organização:
    1. Site institucional (público)
    2. Autenticação
    3. Dashboard
    4. Hóspedes
    5. Quartos
    6. Reservas
    7. Check-in / Check-out
    8. Relatórios
    9. Configurações
"""
import csv
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from .forms import (
    DisponibilidadeForm, HospedeForm, LoginForm, MensagemContatoForm, QuartoForm,
    QuartoStatusForm, RelatorioFiltroForm, ReservaForm, SolicitacaoReservaForm,
)
from .mixins import FuncionarioRequiredMixin, PermissaoMixin
from .models import Hospede, MensagemContato, Quarto, Reserva
from .validators import somente_digitos

ITENS_POR_PAGINA = 10

SERVICOS = [
    ("fa-wifi", "Wi-Fi de alta velocidade", "Conexão gratuita em todos os quartos e áreas comuns."),
    ("fa-square-parking", "Estacionamento", "Vagas cobertas e monitoradas para hóspedes."),
    ("fa-bell-concierge", "Recepção 24 horas", "Equipe pronta para atender a qualquer momento."),
    ("fa-utensils", "Serviço de quarto", "Refeições e bebidas entregues no seu quarto."),
    ("fa-mug-hot", "Café da manhã", "Buffet completo com opções regionais e saudáveis."),
    ("fa-snowflake", "Ar-condicionado", "Climatização individual em todas as acomodações."),
]


def _tipos_acomodacao():
    """Agrupa os quartos cadastrados por tipo para o site público."""
    tipos = []
    dados = (
        Quarto.objects.values("tipo")
        .annotate(total=Count("id"))
        .order_by("tipo")
    )
    ordem = [t.value for t in Quarto.Tipo]
    for item in sorted(dados, key=lambda d: ordem.index(d["tipo"])):
        quartos = Quarto.objects.filter(tipo=item["tipo"]).order_by("valor_diaria")
        exemplo = quartos.first()
        tipos.append({
            "tipo": item["tipo"],
            "nome": Quarto.Tipo(item["tipo"]).label,
            "total": item["total"],
            "capacidade": max(q.capacidade for q in quartos),
            "valor_minimo": exemplo.valor_diaria,
            "descricao": exemplo.descricao,
            "imagem_url": exemplo.imagem_url,
        })
    return tipos


# =====================================================================
# 1. SITE INSTITUCIONAL
# =====================================================================
class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["acomodacoes"] = _tipos_acomodacao()
        ctx["servicos"] = SERVICOS
        ctx.setdefault("form_reserva", SolicitacaoReservaForm(prefix="r"))
        ctx.setdefault("form_contato", MensagemContatoForm(prefix="c"))
        return ctx


class SobreView(TemplateView):
    template_name = "sobre.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["servicos"] = SERVICOS
        ctx["total_quartos"] = Quarto.objects.count()
        return ctx


class AcomodacoesView(TemplateView):
    template_name = "acomodacoes.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["acomodacoes"] = _tipos_acomodacao()
        return ctx


class ReservarView(View):
    """Recebe a solicitação de reserva do visitante (status Pendente)."""

    template_name = "reservar.html"

    def get(self, request):
        inicial = {k: v for k, v in request.GET.items() if k in ("data_checkin", "data_checkout", "tipo", "quantidade_hospedes")}
        form = SolicitacaoReservaForm(prefix="r", initial=inicial)
        return render(request, self.template_name, {"form_reserva": form})

    def post(self, request):
        form = SolicitacaoReservaForm(request.POST, prefix="r")
        if not form.is_valid():
            messages.error(request, "Não foi possível enviar a solicitação. Verifique os campos destacados.")
            return render(request, self.template_name, {"form_reserva": form})

        dados = form.cleaned_data
        try:
            with transaction.atomic():
                hospede, criado = Hospede.objects.get_or_create(
                    cpf=dados["cpf"],
                    defaults={
                        "nome_completo": dados["nome_completo"],
                        "telefone": dados["telefone"],
                        "email": dados.get("email", ""),
                    },
                )
                reserva = Reserva(
                    hospede=hospede,
                    quarto=form.quarto_sugerido,
                    data_checkin=dados["data_checkin"],
                    data_checkout=dados["data_checkout"],
                    quantidade_hospedes=dados["quantidade_hospedes"],
                    status=Reserva.Status.PENDENTE,
                    origem=Reserva.Origem.SITE,
                    observacoes=dados.get("observacoes", ""),
                )
                reserva.full_clean()
                reserva.save()
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
            return render(request, self.template_name, {"form_reserva": form})

        return render(request, "reserva_enviada.html", {"reserva": reserva})


class ContatoView(View):
    template_name = "contato.html"

    def get(self, request):
        return render(request, self.template_name, {"form_contato": MensagemContatoForm(prefix="c")})

    def post(self, request):
        form = MensagemContatoForm(request.POST, prefix="c")
        if form.is_valid():
            form.save()
            messages.success(request, "Mensagem enviada com sucesso! Nossa equipe retornará em breve.")
            return redirect("contato")
        messages.error(request, "Verifique os campos do formulário de contato.")
        return render(request, self.template_name, {"form_contato": form})


# =====================================================================
# 2. AUTENTICAÇÃO
# =====================================================================
class LoginView(auth_views.LoginView):
    template_name = "login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Bem-vindo(a), {form.get_user().get_short_name() or form.get_user().username}!")
        return super().form_valid(form)


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        messages.info(request, "Você saiu do sistema com segurança.")
        return super().post(request, *args, **kwargs)


# =====================================================================
# 3. DASHBOARD
# =====================================================================
class DashboardView(FuncionarioRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        quartos = Quarto.objects.aggregate(
            total=Count("id"),
            disponiveis=Count("id", filter=Q(status=Quarto.Status.DISPONIVEL)),
            ocupados=Count("id", filter=Q(status=Quarto.Status.OCUPADO)),
            manutencao=Count("id", filter=Q(status=Quarto.Status.MANUTENCAO)),
        )
        reservas = Reserva.objects.aggregate(
            confirmadas=Count("id", filter=Q(status=Reserva.Status.CONFIRMADA)),
            pendentes=Count("id", filter=Q(status=Reserva.Status.PENDENTE)),
            previsto=Sum("valor_total", filter=Q(status__in=Reserva.STATUS_PREVISTOS)),
            finalizado=Sum("valor_total", filter=Q(status=Reserva.Status.FINALIZADA)),
            cancelado=Sum("valor_total", filter=Q(status=Reserva.Status.CANCELADA)),
            em_andamento=Sum("valor_total", filter=Q(status=Reserva.Status.EM_ANDAMENTO)),
        )
        checkins_hoje = Reserva.objects.filter(
            Q(status=Reserva.Status.CONFIRMADA, data_checkin=hoje)
            | Q(checkin_realizado_em__date=hoje)
        ).count()
        checkouts_hoje = Reserva.objects.filter(
            Q(status=Reserva.Status.EM_ANDAMENTO, data_checkout=hoje)
            | Q(checkout_realizado_em__date=hoje)
        ).count()

        ctx.update({
            "hoje": hoje,
            "q": quartos,
            "r": reservas,
            "total_hospedes": Hospede.objects.count(),
            "checkins_hoje": checkins_hoje,
            "checkouts_hoje": checkouts_hoje,
            "recentes": Reserva.objects.select_related("hospede", "quarto")[:6],
            "proximas_chegadas": Reserva.objects.filter(
                status=Reserva.Status.CONFIRMADA, data_checkin__gte=hoje
            ).select_related("hospede", "quarto").order_by("data_checkin")[:5],
            "proximas_saidas": Reserva.objects.filter(
                status=Reserva.Status.EM_ANDAMENTO
            ).select_related("hospede", "quarto").order_by("data_checkout")[:5],
            "grafico_ocupacao": json.dumps({
                "labels": ["Disponíveis", "Ocupados", "Em manutenção"],
                "valores": [quartos["disponiveis"], quartos["ocupados"], quartos["manutencao"]],
            }),
        })
        return ctx


# =====================================================================
# 4. HÓSPEDES
# =====================================================================
class HospedeListView(FuncionarioRequiredMixin, ListView):
    model = Hospede
    template_name = "hospedes/lista.html"
    context_object_name = "hospedes"
    paginate_by = ITENS_POR_PAGINA

    def get_queryset(self):
        qs = Hospede.objects.annotate(total_reservas=Count("reservas"))
        busca = self.request.GET.get("q", "").strip()
        nome = self.request.GET.get("nome", "").strip()
        cpf = somente_digitos(self.request.GET.get("cpf", ""))
        if busca:
            filtro = Q(nome_completo__icontains=busca) | Q(email__icontains=busca)
            if somente_digitos(busca):
                filtro |= Q(cpf__contains=somente_digitos(busca)) | Q(telefone__contains=somente_digitos(busca))
            qs = qs.filter(filtro)
        if nome:
            qs = qs.filter(nome_completo__icontains=nome)
        if cpf:
            qs = qs.filter(cpf__contains=cpf)
        return qs.order_by("nome_completo")


class HospedeDetailView(FuncionarioRequiredMixin, DetailView):
    model = Hospede
    template_name = "hospedes/detalhes.html"
    context_object_name = "hospede"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reservas"] = self.object.reservas.select_related("quarto").order_by("-data_checkin")
        return ctx


class HospedeCreateView(FuncionarioRequiredMixin, SuccessMessageMixin, CreateView):
    model = Hospede
    form_class = HospedeForm
    template_name = "hospedes/criar.html"
    success_message = "Hóspede %(nome_completo)s cadastrado com sucesso."


class HospedeUpdateView(FuncionarioRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Hospede
    form_class = HospedeForm
    template_name = "hospedes/editar.html"
    context_object_name = "hospede"
    success_message = "Cadastro de %(nome_completo)s atualizado com sucesso."


class ExclusaoProtegidaMixin:
    """Trata ProtectedError ao excluir registros vinculados a reservas."""

    mensagem_protegida = "Este registro possui reservas vinculadas e não pode ser excluído."
    mensagem_sucesso = "Registro excluído com sucesso."

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(self.request, self.mensagem_protegida)
            return HttpResponseRedirect(self.object.get_absolute_url())
        messages.success(self.request, self.mensagem_sucesso)
        return HttpResponseRedirect(self.get_success_url())


class HospedeDeleteView(PermissaoMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Hospede
    permissao = "reservas.delete_hospede"
    template_name = "partials/confirmar_exclusao.html"
    success_url = reverse_lazy("hospede_lista")
    mensagem_protegida = (
        "Não é possível excluir este hóspede porque ele possui reservas registradas. "
        "O histórico de hospedagens precisa ser preservado."
    )
    mensagem_sucesso = "Hóspede excluído com sucesso."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "titulo": "Excluir hóspede",
            "descricao": f"o hóspede {self.object.nome_completo}",
            "voltar": self.object.get_absolute_url(),
            "bloqueado": self.object.reservas.exists(),
        })
        return ctx


# =====================================================================
# 5. QUARTOS
# =====================================================================
class QuartoListView(FuncionarioRequiredMixin, ListView):
    model = Quarto
    template_name = "quartos/lista.html"
    context_object_name = "quartos"
    paginate_by = 12

    def get_queryset(self):
        qs = Quarto.objects.all()
        status = self.request.GET.get("status", "")
        tipo = self.request.GET.get("tipo", "")
        busca = self.request.GET.get("q", "").strip()
        if status in Quarto.Status.values:
            qs = qs.filter(status=status)
        if tipo in Quarto.Tipo.values:
            qs = qs.filter(tipo=tipo)
        if busca:
            qs = qs.filter(Q(numero__icontains=busca) | Q(descricao__icontains=busca))
        return qs.order_by("numero")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_atual"] = self.request.GET.get("status", "")
        ctx["contagem"] = {
            "": Quarto.objects.count(),
            **{s: Quarto.objects.filter(status=s).count() for s in Quarto.Status.values},
        }
        ctx["filtros_status"] = [("", "Todos")] + list(Quarto.Status.choices)
        ctx["tipos"] = Quarto.Tipo.choices
        return ctx


class QuartoDetailView(FuncionarioRequiredMixin, DetailView):
    model = Quarto
    template_name = "quartos/detalhes.html"
    context_object_name = "quarto"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        ctx["proximas"] = self.object.reservas.filter(
            status__in=Reserva.STATUS_PREVISTOS, data_checkout__gte=hoje
        ).select_related("hospede").order_by("data_checkin")
        ctx["historico"] = self.object.reservas.exclude(
            pk__in=ctx["proximas"].values("pk")
        ).select_related("hospede").order_by("-data_checkin")[:10]
        ctx["status_opcoes"] = [
            c for c in Quarto.Status.choices if c[0] != Quarto.Status.OCUPADO
        ]
        return ctx


class QuartoCreateView(FuncionarioRequiredMixin, SuccessMessageMixin, CreateView):
    model = Quarto
    form_class = QuartoForm
    template_name = "quartos/criar.html"
    success_message = "Quarto %(numero)s cadastrado com sucesso."


class QuartoUpdateView(FuncionarioRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Quarto
    form_class = QuartoForm
    template_name = "quartos/editar.html"
    context_object_name = "quarto"
    success_message = "Quarto %(numero)s atualizado com sucesso."


class QuartoStatusView(FuncionarioRequiredMixin, View):
    """Alteração rápida de status (Disponível / Em manutenção)."""

    def post(self, request, pk):
        quarto = get_object_or_404(Quarto, pk=pk)
        form = QuartoStatusForm(request.POST)
        if form.is_valid():
            quarto.status = form.cleaned_data["status"]
            try:
                quarto.full_clean()
                quarto.save(update_fields=["status"])
                messages.success(request, f"Status do quarto {quarto.numero} alterado para {quarto.get_status_display()}.")
            except ValidationError as erro:
                messages.error(request, " ".join(erro.messages))
        else:
            messages.error(request, "Status inválido.")
        destino = request.POST.get("next") or quarto.get_absolute_url()
        if not destino.startswith("/"):
            destino = quarto.get_absolute_url()
        return redirect(destino)


class QuartoDeleteView(PermissaoMixin, ExclusaoProtegidaMixin, DeleteView):
    model = Quarto
    permissao = "reservas.delete_quarto"
    template_name = "partials/confirmar_exclusao.html"
    success_url = reverse_lazy("quarto_lista")
    mensagem_protegida = (
        "Não é possível excluir este quarto porque existem reservas vinculadas a ele. "
        "Considere colocá-lo em manutenção."
    )
    mensagem_sucesso = "Quarto excluído com sucesso."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "titulo": "Excluir quarto",
            "descricao": f"o quarto {self.object.numero} ({self.object.get_tipo_display()})",
            "voltar": self.object.get_absolute_url(),
            "bloqueado": self.object.reservas.exists(),
        })
        return ctx


# =====================================================================
# 6. RESERVAS
# =====================================================================
class ReservaListView(FuncionarioRequiredMixin, ListView):
    model = Reserva
    template_name = "reservas/lista.html"
    context_object_name = "reservas"
    paginate_by = ITENS_POR_PAGINA

    def get_queryset(self):
        qs = Reserva.objects.select_related("hospede", "quarto")
        status = self.request.GET.get("status", "")
        busca = self.request.GET.get("q", "").strip()
        if status in Reserva.Status.values:
            qs = qs.filter(status=status)
        if busca:
            filtro = Q(hospede__nome_completo__icontains=busca) | Q(quarto__numero__iexact=busca)
            codigo = busca.upper().replace("RC", "")
            if codigo.isdigit():
                filtro |= Q(pk=int(codigo))
            if len(somente_digitos(busca)) >= 3:
                filtro |= Q(hospede__cpf__contains=somente_digitos(busca))
            qs = qs.filter(filtro)
        return qs.order_by("-data_checkin", "-pk")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_atual"] = self.request.GET.get("status", "")
        contagem = dict(Reserva.objects.values_list("status").annotate(n=Count("id")))
        ctx["filtros_status"] = [("", "Todas", Reserva.objects.count())] + [
            (valor, rotulo, contagem.get(valor, 0)) for valor, rotulo in Reserva.Status.choices
        ]
        return ctx


class ReservaDetailView(FuncionarioRequiredMixin, DetailView):
    model = Reserva
    template_name = "reservas/detalhes.html"
    context_object_name = "reserva"

    def get_queryset(self):
        return Reserva.objects.select_related("hospede", "quarto")


class ReservaFormMixin:
    """Adiciona o resumo (diárias, diária, total) antes de salvar."""

    def _resumo(self, form):
        dados = form.cleaned_data
        quarto = dados.get("quarto")
        if not quarto:
            return None
        if self.object and self.object.pk and self.object.quarto_id == quarto.pk:
            diaria = self.object.valor_diaria
        else:
            diaria = quarto.valor_diaria
        diarias, total = Reserva.calcular_valores(diaria, dados["data_checkin"], dados["data_checkout"])
        return {"quarto": quarto, "hospede": dados.get("hospede"), "diarias": diarias,
                "valor_diaria": diaria, "valor_total": total,
                "entrada": dados["data_checkin"], "saida": dados["data_checkout"],
                "quantidade": dados["quantidade_hospedes"]}

    def form_valid(self, form):
        if self.request.POST.get("acao") == "previsualizar":
            messages.info(self.request, "Confira o resumo da reserva e clique em Salvar para concluir.")
            return self.render_to_response(self.get_context_data(form=form, resumo=self._resumo(form)))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["precos_json"] = json.dumps(ctx["form"].precos_quartos)
        return ctx


class ReservaCreateView(FuncionarioRequiredMixin, ReservaFormMixin, CreateView):
    model = Reserva
    form_class = ReservaForm
    template_name = "reservas/criar.html"

    def get_initial(self):
        inicial = super().get_initial()
        for campo in ("hospede", "quarto", "data_checkin", "data_checkout", "quantidade_hospedes"):
            if self.request.GET.get(campo):
                inicial[campo] = self.request.GET[campo]
        return inicial

    def form_valid(self, form):
        form.instance.status = Reserva.Status.PENDENTE
        form.instance.origem = Reserva.Origem.RECEPCAO
        resposta = super().form_valid(form)
        if self.request.POST.get("acao") != "previsualizar":
            messages.success(self.request, f"Reserva {self.object.codigo} criada com status Pendente.")
        return resposta


class ReservaUpdateView(FuncionarioRequiredMixin, ReservaFormMixin, UpdateView):
    model = Reserva
    form_class = ReservaForm
    template_name = "reservas/editar.html"
    context_object_name = "reserva"

    def dispatch(self, request, *args, **kwargs):
        reserva = get_object_or_404(Reserva, pk=kwargs["pk"])
        if not reserva.pode_editar:
            messages.error(request, f"Reservas com status '{reserva.get_status_display()}' não podem ser editadas.")
            return redirect(reserva)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if self.request.POST.get("acao") != "previsualizar":
            messages.success(self.request, f"Reserva {self.object.codigo} atualizada com sucesso.")
        return resposta


class ReservaAcaoView(FuncionarioRequiredMixin, View):
    """Executa uma transição de status (POST com proteção CSRF)."""

    acao = None
    sucesso = ""

    def post(self, request, pk):
        reserva = get_object_or_404(Reserva, pk=pk)
        try:
            getattr(reserva, self.acao)()
            messages.success(request, self.sucesso.format(codigo=reserva.codigo, quarto=reserva.quarto.numero))
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        return self.redirecionar(request, reserva)

    def redirecionar(self, request, reserva):
        destino = request.POST.get("next", "")
        return redirect(destino if destino.startswith("/") else reserva.get_absolute_url())


class ReservaConfirmarView(ReservaAcaoView):
    acao = "confirmar"
    sucesso = "Reserva {codigo} confirmada com sucesso."


class ReservaCancelarView(ReservaAcaoView):
    acao = "cancelar"
    sucesso = "Reserva {codigo} cancelada."


class DisponibilidadeView(FuncionarioRequiredMixin, View):
    template_name = "reservas/disponibilidade.html"

    def get(self, request):
        form = DisponibilidadeForm(request.GET or None)
        quartos = None
        if form.is_bound and form.is_valid():
            quartos = form.quartos_disponiveis()
        return render(request, self.template_name, {"form": form, "quartos": quartos})


# =====================================================================
# 7. CHECK-IN / CHECK-OUT
# =====================================================================
class CheckinListView(FuncionarioRequiredMixin, TemplateView):
    template_name = "checkin/lista.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        busca = self.request.GET.get("q", "").strip()
        base = Reserva.objects.filter(status=Reserva.Status.CONFIRMADA).select_related("hospede", "quarto")
        ctx["hoje"] = hoje
        ctx["chegadas_hoje"] = base.filter(data_checkin=hoje).order_by("quarto__numero")
        ctx["atrasadas"] = base.filter(data_checkin__lt=hoje, data_checkout__gt=hoje).order_by("data_checkin")
        ctx["proximas"] = base.filter(data_checkin__gt=hoje).order_by("data_checkin")[:10]
        ctx["realizados_hoje"] = Reserva.objects.filter(checkin_realizado_em__date=hoje).select_related("hospede", "quarto")
        ctx["busca"] = busca
        if busca:
            filtro = Q(hospede__nome_completo__icontains=busca)
            codigo = busca.upper().replace("RC", "")
            if codigo.isdigit():
                filtro |= Q(pk=int(codigo))
            if len(somente_digitos(busca)) >= 3:
                filtro |= Q(hospede__cpf__contains=somente_digitos(busca))
            ctx["resultados"] = Reserva.objects.filter(filtro).select_related("hospede", "quarto").order_by("-data_checkin")[:20]
        return ctx


class CheckinRealizarView(ReservaAcaoView):
    acao = "realizar_checkin"
    sucesso = "Check-in da reserva {codigo} realizado! Quarto {quarto} agora está ocupado."

    def redirecionar(self, request, reserva):
        return redirect("checkin_lista")


class CheckoutListView(FuncionarioRequiredMixin, TemplateView):
    template_name = "checkout/lista.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        ctx["hoje"] = hoje
        ctx["hospedados"] = Reserva.objects.filter(
            status=Reserva.Status.EM_ANDAMENTO
        ).select_related("hospede", "quarto").order_by("data_checkout")
        ctx["realizados_hoje"] = Reserva.objects.filter(
            checkout_realizado_em__date=hoje
        ).select_related("hospede", "quarto")
        return ctx


class CheckoutRealizarView(FuncionarioRequiredMixin, View):
    def post(self, request, pk):
        reserva = get_object_or_404(Reserva, pk=pk)
        try:
            reserva.realizar_checkout()
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
            return redirect("checkout_lista")
        messages.success(request, f"Check-out da reserva {reserva.codigo} realizado. Quarto {reserva.quarto.numero} liberado.")
        return redirect("checkout_resumo", pk=reserva.pk)


class CheckoutResumoView(FuncionarioRequiredMixin, DetailView):
    model = Reserva
    template_name = "checkout/resumo.html"
    context_object_name = "reserva"

    def get_queryset(self):
        return Reserva.objects.filter(status=Reserva.Status.FINALIZADA).select_related("hospede", "quarto")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        r = self.object
        ctx["permanencia"] = r.checkout_realizado_em - r.checkin_realizado_em
        return ctx


# =====================================================================
# 8. RELATÓRIOS
# =====================================================================
class RelatoriosView(FuncionarioRequiredMixin, View):
    template_name = "relatorios/index.html"

    def _periodo(self, form):
        hoje = timezone.localdate()
        inicio = hoje.replace(day=1)
        fim = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        if form.is_valid():
            inicio = form.cleaned_data.get("inicio") or inicio
            fim = form.cleaned_data.get("fim") or fim
        return inicio, fim

    def get(self, request):
        form = RelatorioFiltroForm(request.GET or None)
        inicio, fim = self._periodo(form)
        fim_exclusivo = fim + timedelta(days=1)
        reservas = Reserva.objects.filter(
            data_checkin__lt=fim_exclusivo, data_checkout__gt=inicio
        ).select_related("hospede", "quarto")

        if request.GET.get("exportar") == "csv":
            return self.exportar_csv(reservas.order_by("data_checkin"), inicio, fim)

        por_status = {s: reservas.filter(status=s).count() for s in Reserva.Status.values}
        ocupacao_qs = reservas.filter(
            status__in=[Reserva.Status.CONFIRMADA, Reserva.Status.EM_ANDAMENTO, Reserva.Status.FINALIZADA]
        )
        dias_periodo = (fim_exclusivo - inicio).days
        total_quartos = Quarto.objects.count()
        noites_ocupadas = 0
        uso_quartos = {}
        for r in ocupacao_qs:
            noites = (min(r.data_checkout, fim_exclusivo) - max(r.data_checkin, inicio)).days
            noites_ocupadas += max(noites, 0)
            item = uso_quartos.setdefault(r.quarto_id, {"quarto": r.quarto, "reservas": 0, "noites": 0, "valor": Decimal("0")})
            item["reservas"] += 1
            item["noites"] += max(noites, 0)
            item["valor"] += r.valor_total
        capacidade = total_quartos * dias_periodo
        taxa = round(noites_ocupadas / capacidade * 100, 1) if capacidade else 0

        # Reservas por mês (data de entrada)
        por_mes = {}
        for r in reservas.order_by("data_checkin"):
            chave = r.data_checkin.strftime("%m/%Y")
            item = por_mes.setdefault(chave, {"mes": chave, "total": 0, "valor": Decimal("0")})
            item["total"] += 1
            item["valor"] += r.valor_total

        contexto = {
            "form": form,
            "inicio": inicio,
            "fim": fim,
            "dias_periodo": dias_periodo,
            "total_reservas": reservas.count(),
            "por_status": [(Reserva.Status(s).label, s, n) for s, n in por_status.items()],
            "taxa_ocupacao": taxa,
            "noites_ocupadas": noites_ocupadas,
            "capacidade_noites": capacidade,
            "quartos_mais_usados": sorted(uso_quartos.values(), key=lambda i: (-i["noites"], -i["reservas"]))[:5],
            "hospedes_periodo": reservas.exclude(status=Reserva.Status.CANCELADA).values("hospede").distinct().count(),
            "pessoas_periodo": reservas.exclude(status=Reserva.Status.CANCELADA).aggregate(t=Sum("quantidade_hospedes"))["t"] or 0,
            "total_hospedes": Hospede.objects.count(),
            "faturamento_previsto": reservas.filter(status__in=Reserva.STATUS_PREVISTOS).aggregate(t=Sum("valor_total"))["t"] or 0,
            "faturamento_finalizado": reservas.filter(status=Reserva.Status.FINALIZADA).aggregate(t=Sum("valor_total"))["t"] or 0,
            "por_mes": list(por_mes.values()),
            "reservas": reservas.order_by("data_checkin")[:50],
            "grafico_status": json.dumps({
                "labels": [Reserva.Status(s).label for s in por_status],
                "valores": list(por_status.values()),
            }),
        }
        return render(request, self.template_name, contexto)

    def exportar_csv(self, reservas, inicio, fim):
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        nome = f"relatorio_reservas_{inicio:%Y%m%d}_{fim:%Y%m%d}.csv"
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        resposta.write("\ufeff")  # BOM para o Excel reconhecer acentos
        escritor = csv.writer(resposta, delimiter=";")
        escritor.writerow([
            "Código", "Hóspede", "CPF", "Quarto", "Tipo", "Entrada", "Saída", "Diárias",
            "Hóspedes", "Valor diária (R$)", "Valor total (R$)", "Status", "Origem",
        ])
        for r in reservas:
            escritor.writerow([
                r.codigo, r.hospede.nome_completo, r.hospede.cpf, r.quarto.numero,
                r.quarto.get_tipo_display(), r.data_checkin.strftime("%d/%m/%Y"),
                r.data_checkout.strftime("%d/%m/%Y"), r.diarias, r.quantidade_hospedes,
                f"{r.valor_diaria:.2f}".replace(".", ","), f"{r.valor_total:.2f}".replace(".", ","),
                r.get_status_display(), r.get_origem_display(),
            ])
        return resposta


# =====================================================================
# 9. CONFIGURAÇÕES
# =====================================================================
class ConfiguracoesView(FuncionarioRequiredMixin, View):
    template_name = "configuracoes.html"

    def contexto(self, form_senha):
        return {
            "form_senha": form_senha,
            "mensagens": MensagemContato.objects.all()[:20],
            "grupos": self.request.user.groups.values_list("name", flat=True),
            "estatisticas": {
                "quartos": Quarto.objects.count(),
                "hospedes": Hospede.objects.count(),
                "reservas": Reserva.objects.count(),
            },
        }

    def _form_senha(self, data=None):
        form = PasswordChangeForm(self.request.user, data)
        for campo in form.fields.values():
            campo.widget.attrs["class"] = "form-control"
        return form

    def get(self, request):
        return render(request, self.template_name, self.contexto(self._form_senha()))

    def post(self, request):
        if "marcar_lida" in request.POST:
            MensagemContato.objects.filter(pk=request.POST.get("marcar_lida")).update(lida=True)
            messages.success(request, "Mensagem marcada como lida.")
            return redirect(reverse("configuracoes") + "#mensagens")
        form = self._form_senha(request.POST)
        if form.is_valid():
            from django.contrib.auth import update_session_auth_hash
            usuario = form.save()
            update_session_auth_hash(request, usuario)
            messages.success(request, "Senha alterada com sucesso.")
            return redirect("configuracoes")
        messages.error(request, "Não foi possível alterar a senha. Verifique os campos.")
        return render(request, self.template_name, self.contexto(form))
