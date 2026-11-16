"""
Models do Hotel Cesar.

Relacionamentos:
    Hospede 1 ──< N Reserva  (um hóspede pode ter várias reservas)
    Quarto  1 ──< N Reserva  (um quarto pode ter várias reservas em datas diferentes)
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from .validators import somente_digitos, validar_cpf, validar_telefone

ESTADOS_BR = [
    ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
    ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"),
    ("ES", "Espírito Santo"), ("GO", "Goiás"), ("MA", "Maranhão"),
    ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
    ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"),
    ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
    ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"),
    ("SC", "Santa Catarina"), ("SP", "São Paulo"), ("SE", "Sergipe"),
    ("TO", "Tocantins"),
]


class Hospede(models.Model):
    nome_completo = models.CharField("nome completo", max_length=150)
    cpf = models.CharField(
        "CPF", max_length=11, unique=True, validators=[validar_cpf],
        help_text="Somente números (a máscara é aplicada automaticamente).",
    )
    telefone = models.CharField("telefone", max_length=20, validators=[validar_telefone])
    email = models.EmailField("e-mail", blank=True)
    endereco = models.CharField("endereço", max_length=200, blank=True)
    cidade = models.CharField("cidade", max_length=100, blank=True)
    estado = models.CharField("estado", max_length=2, choices=ESTADOS_BR, blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    data_cadastro = models.DateTimeField("data de cadastro", auto_now_add=True)

    class Meta:
        verbose_name = "hóspede"
        verbose_name_plural = "hóspedes"
        ordering = ["nome_completo"]

    def __str__(self):
        return self.nome_completo

    def get_absolute_url(self):
        return reverse("hospede_detalhes", args=[self.pk])

    def clean(self):
        self.cpf = somente_digitos(self.cpf)
        self.telefone = somente_digitos(self.telefone)
        if self.nome_completo:
            self.nome_completo = " ".join(self.nome_completo.split())
        if self.data_nascimento and self.data_nascimento > timezone.localdate():
            raise ValidationError({"data_nascimento": "A data de nascimento não pode estar no futuro."})


class Quarto(models.Model):
    class Tipo(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        EXECUTIVO = "EXECUTIVO", "Executivo"
        LUXO = "LUXO", "Luxo"
        SUITE_MASTER = "SUITE_MASTER", "Suíte Master"

    class Status(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        OCUPADO = "OCUPADO", "Ocupado"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"

    IMAGENS_PADRAO = {
        Tipo.STANDARD: "images/quarto_standard.jpg",
        Tipo.EXECUTIVO: "images/quarto_executivo.jpg",
        Tipo.LUXO: "images/quarto_luxo.jpg",
        Tipo.SUITE_MASTER: "images/quarto_suite_master.jpg",
    }

    numero = models.CharField("número", max_length=10, unique=True)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, default=Tipo.STANDARD)
    descricao = models.TextField("descrição", blank=True)
    capacidade = models.PositiveSmallIntegerField(
        "capacidade (pessoas)", validators=[MinValueValidator(1)], default=2
    )
    valor_diaria = models.DecimalField(
        "valor da diária (R$)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.DISPONIVEL)
    imagem = models.ImageField("imagem", upload_to="quartos/", blank=True)

    class Meta:
        verbose_name = "quarto"
        verbose_name_plural = "quartos"
        ordering = ["numero"]

    def __str__(self):
        return f"Quarto {self.numero} – {self.get_tipo_display()}"

    def get_absolute_url(self):
        return reverse("quarto_detalhes", args=[self.pk])

    @property
    def imagem_url(self):
        if self.imagem:
            return self.imagem.url
        return static(self.IMAGENS_PADRAO.get(self.tipo, "images/quarto_standard.jpg"))

    @property
    def hospedagem_atual(self):
        return self.reservas.filter(status=Reserva.Status.EM_ANDAMENTO).select_related("hospede").first()

    def clean(self):
        if self.pk and self.hospedagem_atual and self.status != self.Status.OCUPADO:
            raise ValidationError({
                "status": "Este quarto possui um hóspede em andamento. "
                          "Realize o check-out antes de alterar o status."
            })
        if self.status == self.Status.OCUPADO and not (self.pk and self.hospedagem_atual):
            raise ValidationError({
                "status": "O status 'Ocupado' é definido automaticamente pelo check-in."
            })

    def esta_livre(self, entrada, saida, ignorar_reserva=None):
        """Verifica se não há reservas ativas no período informado."""
        conflitos = Reserva.conflitos(self, entrada, saida, ignorar_reserva)
        return not conflitos.exists()


class Reserva(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

    class Origem(models.TextChoices):
        RECEPCAO = "RECEPCAO", "Recepção"
        SITE = "SITE", "Site"

    # Status que bloqueiam o quarto no período (geram conflito de datas).
    STATUS_BLOQUEANTES = [Status.CONFIRMADA, Status.EM_ANDAMENTO]
    # Status em que a reserva ainda pode ser editada ou cancelada.
    STATUS_EDITAVEIS = [Status.PENDENTE, Status.CONFIRMADA]
    # Status considerados no faturamento previsto (ainda não recebido).
    STATUS_PREVISTOS = [Status.PENDENTE, Status.CONFIRMADA, Status.EM_ANDAMENTO]

    hospede = models.ForeignKey(
        Hospede, on_delete=models.PROTECT, related_name="reservas", verbose_name="hóspede"
    )
    quarto = models.ForeignKey(
        Quarto, on_delete=models.PROTECT, related_name="reservas", verbose_name="quarto"
    )
    data_reserva = models.DateTimeField("data da reserva", auto_now_add=True)
    data_checkin = models.DateField("data de entrada")
    data_checkout = models.DateField("data de saída")
    quantidade_hospedes = models.PositiveSmallIntegerField(
        "quantidade de hóspedes", validators=[MinValueValidator(1)], default=1
    )
    valor_diaria = models.DecimalField(
        "valor da diária (R$)", max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Preço registrado no momento da reserva.",
    )
    valor_total = models.DecimalField("valor total (R$)", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.PENDENTE)
    origem = models.CharField("origem", max_length=10, choices=Origem.choices, default=Origem.RECEPCAO)
    observacoes = models.TextField("observações", blank=True)
    checkin_realizado_em = models.DateTimeField("check-in realizado em", null=True, blank=True)
    checkout_realizado_em = models.DateTimeField("check-out realizado em", null=True, blank=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-data_reserva"]

    def __str__(self):
        return f"Reserva {self.codigo} – {self.hospede}"

    def get_absolute_url(self):
        return reverse("reserva_detalhes", args=[self.pk])

    # ---------- Propriedades auxiliares ----------
    @property
    def codigo(self):
        return f"RC{self.pk:05d}" if self.pk else "—"

    @property
    def diarias(self):
        if self.data_checkin and self.data_checkout and self.data_checkout > self.data_checkin:
            return (self.data_checkout - self.data_checkin).days
        return 0

    @property
    def pode_editar(self):
        return self.status in self.STATUS_EDITAVEIS

    @property
    def pode_confirmar(self):
        return self.status == self.Status.PENDENTE

    @property
    def pode_cancelar(self):
        return self.status in self.STATUS_EDITAVEIS

    @property
    def pode_checkin(self):
        return self.status == self.Status.CONFIRMADA and not self.checkin_realizado_em

    @property
    def pode_checkout(self):
        return self.status == self.Status.EM_ANDAMENTO and self.checkin_realizado_em is not None

    # ---------- Regras de negócio ----------
    @classmethod
    def conflitos(cls, quarto, entrada, saida, ignorar_reserva=None):
        """Reservas ativas do quarto que se sobrepõem ao período [entrada, saida)."""
        qs = cls.objects.filter(
            quarto=quarto,
            status__in=cls.STATUS_BLOQUEANTES,
            data_checkin__lt=saida,
            data_checkout__gt=entrada,
        )
        if ignorar_reserva is not None and ignorar_reserva.pk:
            qs = qs.exclude(pk=ignorar_reserva.pk)
        return qs

    @staticmethod
    def calcular_valores(valor_diaria, entrada, saida):
        diarias = (saida - entrada).days if entrada and saida else 0
        diarias = max(diarias, 0)
        return diarias, (Decimal(valor_diaria or 0) * diarias).quantize(Decimal("0.01"))

    def _quarto_alterado(self):
        if not self.pk:
            return True
        anterior = Reserva.objects.filter(pk=self.pk).values_list("quarto_id", flat=True).first()
        return anterior != self.quarto_id

    def atualizar_valores(self):
        """Registra a diária do quarto apenas na criação ou quando o quarto muda."""
        if self.quarto_id and (self._quarto_alterado() or not self.valor_diaria):
            self.valor_diaria = self.quarto.valor_diaria
        _, self.valor_total = self.calcular_valores(self.valor_diaria, self.data_checkin, self.data_checkout)

    def clean(self):
        erros = {}
        if self.data_checkin and self.data_checkout and self.data_checkout <= self.data_checkin:
            erros["data_checkout"] = "A data de saída deve ser posterior à data de entrada."

        if self.quarto_id and self.quantidade_hospedes:
            if self.quantidade_hospedes > self.quarto.capacidade:
                erros["quantidade_hospedes"] = (
                    f"O quarto {self.quarto.numero} comporta no máximo "
                    f"{self.quarto.capacidade} hóspede(s)."
                )

        if (
            not erros
            and self.quarto_id
            and self.data_checkin
            and self.data_checkout
            and self.status in [self.Status.PENDENTE, *self.STATUS_BLOQUEANTES]
        ):
            conflito = self.conflitos(self.quarto, self.data_checkin, self.data_checkout, self).first()
            if conflito:
                erros["quarto"] = (
                    f"O quarto {self.quarto.numero} já possui a reserva {conflito.codigo} "
                    f"de {conflito.data_checkin:%d/%m/%Y} a {conflito.data_checkout:%d/%m/%Y}."
                )
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.atualizar_valores()
        super().save(*args, **kwargs)

    # ---------- Transições de status ----------
    @transaction.atomic
    def confirmar(self):
        if not self.pode_confirmar:
            raise ValidationError("Somente reservas pendentes podem ser confirmadas.")
        self.status = self.Status.CONFIRMADA
        self.full_clean()
        self.save()

    @transaction.atomic
    def cancelar(self):
        if not self.pode_cancelar:
            raise ValidationError("Esta reserva não pode mais ser cancelada.")
        self.status = self.Status.CANCELADA
        self.save(update_fields=["status"])

    @transaction.atomic
    def realizar_checkin(self):
        reserva = Reserva.objects.select_for_update().select_related("quarto").get(pk=self.pk)
        if reserva.checkin_realizado_em or reserva.status == self.Status.EM_ANDAMENTO:
            raise ValidationError("O check-in desta reserva já foi realizado.")
        if reserva.status != self.Status.CONFIRMADA:
            raise ValidationError("Somente reservas confirmadas podem receber check-in.")
        hoje = timezone.localdate()
        if not (reserva.data_checkin <= hoje < reserva.data_checkout):
            raise ValidationError(
                f"O check-in só pode ser feito a partir de {reserva.data_checkin:%d/%m/%Y} "
                f"e antes da data de saída."
            )
        quarto = reserva.quarto
        if quarto.status != Quarto.Status.DISPONIVEL:
            raise ValidationError(
                f"O quarto {quarto.numero} está '{quarto.get_status_display()}' e não pode receber hóspedes."
            )
        reserva.status = self.Status.EM_ANDAMENTO
        reserva.checkin_realizado_em = timezone.now()
        reserva.save(update_fields=["status", "checkin_realizado_em"])
        Quarto.objects.filter(pk=quarto.pk).update(status=Quarto.Status.OCUPADO)
        self.refresh_from_db()

    @transaction.atomic
    def realizar_checkout(self):
        reserva = Reserva.objects.select_for_update().get(pk=self.pk)
        if not reserva.checkin_realizado_em or reserva.status != self.Status.EM_ANDAMENTO:
            raise ValidationError("Não é possível fazer check-out de uma reserva sem check-in realizado.")
        reserva.status = self.Status.FINALIZADA
        reserva.checkout_realizado_em = timezone.now()
        reserva.save(update_fields=["status", "checkout_realizado_em"])
        Quarto.objects.filter(pk=reserva.quarto_id).update(status=Quarto.Status.DISPONIVEL)
        self.refresh_from_db()


class MensagemContato(models.Model):
    nome = models.CharField("nome", max_length=120)
    email = models.EmailField("e-mail")
    telefone = models.CharField("telefone", max_length=20, blank=True)
    assunto = models.CharField("assunto", max_length=150)
    mensagem = models.TextField("mensagem")
    lida = models.BooleanField("lida", default=False)
    enviada_em = models.DateTimeField("enviada em", auto_now_add=True)

    class Meta:
        verbose_name = "mensagem de contato"
        verbose_name_plural = "mensagens de contato"
        ordering = ["-enviada_em"]

    def __str__(self):
        return f"{self.assunto} – {self.nome}"
