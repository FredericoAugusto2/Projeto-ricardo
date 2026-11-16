"""Formulários do Hotel Cesar (validação no servidor)."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from .models import Hospede, MensagemContato, Quarto, Reserva
from .validators import somente_digitos, validar_cpf, validar_telefone


class BootstrapMixin:
    """Aplica classes do Bootstrap 5 a todos os campos."""

    def _aplicar_bootstrap(self):
        for nome, campo in self.fields.items():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
            if campo.required:
                widget.attrs.setdefault("required", "required")


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class LoginForm(BootstrapMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["password"].label = "Senha"
        self.fields["username"].widget.attrs["placeholder"] = "Seu usuário"
        self.fields["password"].widget.attrs["placeholder"] = "Sua senha"
        self._aplicar_bootstrap()


class HospedeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Hospede
        fields = [
            "nome_completo", "cpf", "telefone", "email", "data_nascimento",
            "endereco", "cidade", "estado",
        ]
        widgets = {
            "cpf": forms.TextInput(attrs={"data-mask": "cpf", "placeholder": "000.000.000-00", "maxlength": 14}),
            "telefone": forms.TextInput(attrs={"data-mask": "telefone", "placeholder": "(00) 00000-0000", "maxlength": 15}),
            "email": forms.EmailInput(attrs={"placeholder": "nome@exemplo.com"}),
            "data_nascimento": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove o limite de 11 caracteres para aceitar a máscara digitada
        self.fields["cpf"].max_length = 14
        self.fields["cpf"].validators = []
        self.fields["cpf"].widget.attrs["maxlength"] = 14
        self._aplicar_bootstrap()

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data.get("cpf"))
        validar_cpf(cpf)
        existe = Hospede.objects.filter(cpf=cpf).exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Já existe um hóspede cadastrado com este CPF.")
        return cpf

    def clean_telefone(self):
        telefone = somente_digitos(self.cleaned_data.get("telefone"))
        validar_telefone(telefone)
        return telefone


class QuartoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Quarto
        fields = ["numero", "tipo", "capacidade", "valor_diaria", "status", "descricao", "imagem"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "valor_diaria": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "imagem": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()
        # Ocupado é definido somente pelo check-in
        if not (self.instance.pk and self.instance.status == Quarto.Status.OCUPADO):
            self.fields["status"].choices = [
                c for c in self.fields["status"].choices if c[0] != Quarto.Status.OCUPADO
            ]


class QuartoStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Quarto.Status.choices)


class ReservaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ["hospede", "quarto", "data_checkin", "data_checkout", "quantidade_hospedes", "observacoes"]
        widgets = {
            "data_checkin": DateInput(),
            "data_checkout": DateInput(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "quantidade_hospedes": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hospede"].queryset = Hospede.objects.order_by("nome_completo")
        quartos = Quarto.objects.exclude(status=Quarto.Status.MANUTENCAO)
        if self.instance.pk:
            quartos = Quarto.objects.filter(pk=self.instance.quarto_id) | quartos
        self.fields["quarto"].queryset = quartos.order_by("numero").distinct()
        self.fields["hospede"].empty_label = "Selecione o hóspede"
        self.fields["quarto"].empty_label = "Selecione o quarto"
        self._aplicar_bootstrap()
        self.fields["quarto"].widget.attrs["data-resumo"] = "quarto"
        # Dados de preço/capacidade para o resumo dinâmico em JavaScript
        self.precos_quartos = {
            str(q.pk): {"diaria": str(q.valor_diaria), "capacidade": q.capacidade}
            for q in self.fields["quarto"].queryset
        }
        if self.instance.pk and str(self.instance.quarto_id) in self.precos_quartos:
            # Na edição, mantém a diária registrada no momento da reserva
            self.precos_quartos[str(self.instance.quarto_id)]["diaria"] = str(self.instance.valor_diaria)

    def clean_data_checkin(self):
        data = self.cleaned_data.get("data_checkin")
        if data and not self.instance.pk and data < timezone.localdate():
            raise forms.ValidationError("A data de entrada não pode estar no passado.")
        return data


class DisponibilidadeForm(BootstrapMixin, forms.Form):
    data_checkin = forms.DateField(label="Data de entrada", widget=DateInput())
    data_checkout = forms.DateField(label="Data de saída", widget=DateInput())
    quantidade_hospedes = forms.IntegerField(label="Hóspedes", min_value=1, max_value=10, initial=1)
    tipo = forms.ChoiceField(
        label="Tipo de acomodação",
        choices=[("", "Qualquer tipo")] + list(Quarto.Tipo.choices),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean(self):
        dados = super().clean()
        entrada, saida = dados.get("data_checkin"), dados.get("data_checkout")
        if entrada and entrada < timezone.localdate():
            self.add_error("data_checkin", "A data de entrada não pode estar no passado.")
        if entrada and saida and saida <= entrada:
            self.add_error("data_checkout", "A data de saída deve ser posterior à data de entrada.")
        return dados

    def quartos_disponiveis(self):
        dados = self.cleaned_data
        quartos = Quarto.objects.exclude(status=Quarto.Status.MANUTENCAO).filter(
            capacidade__gte=dados["quantidade_hospedes"]
        )
        if dados.get("tipo"):
            quartos = quartos.filter(tipo=dados["tipo"])
        ocupados = Reserva.objects.filter(
            status__in=Reserva.STATUS_BLOQUEANTES,
            data_checkin__lt=dados["data_checkout"],
            data_checkout__gt=dados["data_checkin"],
        ).values_list("quarto_id", flat=True)
        return quartos.exclude(pk__in=ocupados).order_by("valor_diaria", "numero")


class SolicitacaoReservaForm(DisponibilidadeForm):
    """Formulário público: o visitante solicita uma reserva (fica pendente)."""

    tipo = forms.ChoiceField(label="Tipo de acomodação", choices=Quarto.Tipo.choices)
    nome_completo = forms.CharField(label="Nome completo", max_length=150)
    cpf = forms.CharField(
        label="CPF", max_length=14,
        widget=forms.TextInput(attrs={"data-mask": "cpf", "placeholder": "000.000.000-00"}),
    )
    telefone = forms.CharField(
        label="Telefone", max_length=15,
        widget=forms.TextInput(attrs={"data-mask": "telefone", "placeholder": "(00) 00000-0000"}),
    )
    email = forms.EmailField(label="E-mail", required=False)
    observacoes = forms.CharField(
        label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data.get("cpf"))
        validar_cpf(cpf)
        return cpf

    def clean_telefone(self):
        telefone = somente_digitos(self.cleaned_data.get("telefone"))
        validar_telefone(telefone)
        return telefone

    def clean(self):
        dados = super().clean()
        if not self.errors:
            quarto = self.quartos_disponiveis().first()
            if quarto is None:
                raise forms.ValidationError(
                    "Não há acomodações deste tipo disponíveis para o período e a quantidade "
                    "de hóspedes informados. Tente outras datas ou outro tipo de quarto."
                )
            self.quarto_sugerido = quarto
        return dados


class MensagemContatoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = MensagemContato
        fields = ["nome", "email", "telefone", "assunto", "mensagem"]
        widgets = {
            "mensagem": forms.Textarea(attrs={"rows": 4}),
            "telefone": forms.TextInput(attrs={"data-mask": "telefone", "placeholder": "(00) 00000-0000"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()


class RelatorioFiltroForm(BootstrapMixin, forms.Form):
    inicio = forms.DateField(label="De", widget=DateInput(), required=False)
    fim = forms.DateField(label="Até", widget=DateInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["fim"] < dados["inicio"]:
            self.add_error("fim", "A data final deve ser igual ou posterior à inicial.")
        return dados
