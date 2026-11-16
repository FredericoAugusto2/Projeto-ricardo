"""
Insere dados DEMONSTRATIVOS no banco: 10 quartos, 5 hóspedes e reservas
sem conflitos de datas. Todos os dados são fictícios.

Uso:
    python manage.py popular_demo
    python manage.py popular_demo --limpar
    python manage.py popular_demo --funcionario recepcao --senha "SuaSenhaForte"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from reservas.mixins import GRUPO_ADMINISTRADORES, GRUPO_FUNCIONARIOS
from reservas.models import Hospede, MensagemContato, Quarto, Reserva

QUARTOS = [
    ("101", Quarto.Tipo.STANDARD, 2, "180.00", "Quarto aconchegante com cama de casal, TV e frigobar."),
    ("102", Quarto.Tipo.STANDARD, 2, "180.00", "Quarto aconchegante com duas camas de solteiro."),
    ("103", Quarto.Tipo.STANDARD, 3, "210.00", "Standard ampliado com cama de casal e uma de solteiro."),
    ("201", Quarto.Tipo.EXECUTIVO, 2, "290.00", "Ideal para viagens de negócios: mesa de trabalho e cama king."),
    ("202", Quarto.Tipo.EXECUTIVO, 2, "290.00", "Executivo com vista para a cidade e estação de trabalho."),
    ("203", Quarto.Tipo.EXECUTIVO, 3, "320.00", "Executivo amplo com sofá-cama e mesa de reuniões."),
    ("301", Quarto.Tipo.LUXO, 3, "450.00", "Acabamento premium, banheira, enxoval especial e varanda."),
    ("302", Quarto.Tipo.LUXO, 3, "450.00", "Luxo com sala de estar integrada e vista panorâmica."),
    ("401", Quarto.Tipo.SUITE_MASTER, 4, "780.00", "Suíte com sala, quarto separado, banheira e serviço exclusivo."),
    ("402", Quarto.Tipo.SUITE_MASTER, 5, "850.00", "A acomodação mais completa do hotel, ideal para famílias."),
]


def gerar_cpf(base):
    """Gera um CPF fictício com dígitos verificadores válidos a partir de 9 dígitos."""
    digitos = [int(d) for d in base]
    for tamanho in (9, 10):
        soma = sum(digitos[i] * (tamanho + 1 - i) for i in range(tamanho))
        digitos.append((soma * 10) % 11 % 10)
    return "".join(map(str, digitos))


HOSPEDES = [
    ("Ana Beatriz Souza (Demo)", "123456789", "11987650001", "ana.demo@exemplo.com", "São Paulo", "SP"),
    ("Carlos Eduardo Lima (Demo)", "234567891", "21987650002", "carlos.demo@exemplo.com", "Rio de Janeiro", "RJ"),
    ("Fernanda Oliveira (Demo)", "345678912", "31987650003", "fernanda.demo@exemplo.com", "Belo Horizonte", "MG"),
    ("Rafael Martins (Demo)", "456789123", "41987650004", "rafael.demo@exemplo.com", "Curitiba", "PR"),
    ("Juliana Costa (Demo)", "567891234", "51987650005", "juliana.demo@exemplo.com", "Porto Alegre", "RS"),
]


class Command(BaseCommand):
    help = "Popula o banco com dados demonstrativos do Hotel Cesar."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true", help="Remove reservas, hóspedes e quartos antes de inserir.")
        parser.add_argument("--funcionario", help="Cria um usuário do grupo Funcionários com este nome.")
        parser.add_argument("--senha", help="Senha do usuário funcionário (obrigatória com --funcionario).")

    @transaction.atomic
    def handle(self, *args, **opts):
        self.criar_grupos()

        if opts["limpar"]:
            Reserva.objects.all().delete()
            Hospede.objects.all().delete()
            Quarto.objects.all().delete()
            MensagemContato.objects.all().delete()
            self.stdout.write(self.style.WARNING("Dados anteriores removidos."))

        if Reserva.objects.exists() or Quarto.objects.exists():
            raise CommandError("O banco já possui dados. Use --limpar para recriar os dados demonstrativos.")

        quartos = {}
        for numero, tipo, capacidade, valor, descricao in QUARTOS:
            quartos[numero] = Quarto.objects.create(
                numero=numero, tipo=tipo, capacidade=capacidade,
                valor_diaria=Decimal(valor), descricao=descricao,
            )

        hospedes = []
        for nome, base_cpf, telefone, email, cidade, uf in HOSPEDES:
            hospedes.append(Hospede.objects.create(
                nome_completo=nome, cpf=gerar_cpf(base_cpf), telefone=telefone, email=email,
                endereco="Rua Demonstrativa, 100", cidade=cidade, estado=uf,
            ))

        hoje = timezone.localdate()
        d = lambda dias: hoje + timedelta(days=dias)  # noqa: E731
        obs = "[DEMONSTRAÇÃO] Reserva fictícia para apresentação."

        def reservar(hospede, quarto, entrada, saida, qtd, status, origem=Reserva.Origem.RECEPCAO):
            r = Reserva(hospede=hospede, quarto=quartos[quarto], data_checkin=entrada, data_checkout=saida,
                        quantidade_hospedes=qtd, status=status, origem=origem, observacoes=obs)
            r.full_clean()
            r.save()
            return r

        # Hospedagem finalizada no passado
        fin = reservar(hospedes[0], "201", d(-12), d(-9), 1, Reserva.Status.CONFIRMADA)
        Reserva.objects.filter(pk=fin.pk).update(
            status=Reserva.Status.FINALIZADA,
            checkin_realizado_em=timezone.now() - timedelta(days=12),
            checkout_realizado_em=timezone.now() - timedelta(days=9),
        )
        fin2 = reservar(hospedes[3], "301", d(-6), d(-3), 2, Reserva.Status.CONFIRMADA)
        Reserva.objects.filter(pk=fin2.pk).update(
            status=Reserva.Status.FINALIZADA,
            checkin_realizado_em=timezone.now() - timedelta(days=6),
            checkout_realizado_em=timezone.now() - timedelta(days=3),
        )

        # Hóspedes atualmente hospedados (check-in realizado)
        for hospede, quarto, entrada, saida, qtd in [
            (hospedes[1], "302", d(-2), d(2), 2),
            (hospedes[2], "102", d(-1), d(1), 2),
        ]:
            r = reservar(hospede, quarto, entrada, saida, qtd, Reserva.Status.CONFIRMADA)
            r.realizar_checkin()
            # Registra a entrada no dia previsto (simula hospedagem já iniciada)
            Reserva.objects.filter(pk=r.pk).update(
                checkin_realizado_em=timezone.now() - timedelta(days=(hoje - entrada).days)
            )

        # Chegadas de hoje e futuras
        reservar(hospedes[3], "202", d(0), d(3), 1, Reserva.Status.CONFIRMADA)
        reservar(hospedes[4], "401", d(0), d(4), 3, Reserva.Status.CONFIRMADA)
        reservar(hospedes[0], "101", d(5), d(8), 2, Reserva.Status.CONFIRMADA)
        reservar(hospedes[2], "203", d(10), d(14), 3, Reserva.Status.CONFIRMADA)

        # Pendentes (uma vinda do site) e cancelada
        reservar(hospedes[1], "103", d(7), d(9), 2, Reserva.Status.PENDENTE, Reserva.Origem.SITE)
        reservar(hospedes[4], "301", d(15), d(18), 2, Reserva.Status.PENDENTE)
        canc = reservar(hospedes[3], "402", d(3), d(6), 4, Reserva.Status.CONFIRMADA)
        canc.cancelar()

        # Quarto em manutenção
        Quarto.objects.filter(numero="103").update(status=Quarto.Status.MANUTENCAO)

        MensagemContato.objects.create(
            nome="Visitante Demonstração", email="visitante.demo@exemplo.com",
            assunto="Informações sobre eventos",
            mensagem="Mensagem fictícia de demonstração: o hotel possui salas para eventos?",
        )

        if opts.get("funcionario"):
            self.criar_funcionario(opts["funcionario"], opts.get("senha"))

        self.stdout.write(self.style.SUCCESS(
            f"Dados demonstrativos criados: {Quarto.objects.count()} quartos, "
            f"{Hospede.objects.count()} hóspedes e {Reserva.objects.count()} reservas."
        ))

    def criar_grupos(self):
        modelos = ["hospede", "quarto", "reserva", "mensagemcontato"]
        funcionarios, _ = Group.objects.get_or_create(name=GRUPO_FUNCIONARIOS)
        administradores, _ = Group.objects.get_or_create(name=GRUPO_ADMINISTRADORES)
        perms_func = Permission.objects.filter(
            content_type__app_label="reservas",
            codename__in=[f"{acao}_{m}" for m in modelos for acao in ("view", "add", "change")],
        )
        perms_admin = Permission.objects.filter(content_type__app_label="reservas")
        funcionarios.permissions.set(perms_func)
        administradores.permissions.set(perms_admin)

    def criar_funcionario(self, usuario, senha):
        if not senha:
            raise CommandError("Informe --senha junto com --funcionario.")
        user, criado = User.objects.get_or_create(username=usuario, defaults={"first_name": "Funcionário"})
        user.set_password(senha)
        user.is_staff = False
        user.save()
        user.groups.add(Group.objects.get(name=GRUPO_FUNCIONARIOS))
        self.stdout.write(self.style.SUCCESS(f"Usuário funcionário '{usuario}' {'criado' if criado else 'atualizado'}."))
