"""Testes automatizados do Hotel Cesar: python manage.py test"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import HospedeForm
from .models import Hospede, Quarto, Reserva
from .validators import cpf_valido

CPF_1 = "52998224725"
CPF_2 = "11144477735"


class BaseTestCase(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.hospede = Hospede.objects.create(nome_completo="Hóspede Teste", cpf=CPF_1, telefone="11987654321")
        self.quarto = Quarto.objects.create(numero="101", tipo=Quarto.Tipo.STANDARD, capacidade=2, valor_diaria=Decimal("200.00"))
        self.usuario = User.objects.create_user("recepcao", password="senha-teste-123", is_staff=True)

    def criar_reserva(self, entrada=0, saida=3, status=Reserva.Status.CONFIRMADA, qtd=1, quarto=None):
        r = Reserva(hospede=self.hospede, quarto=quarto or self.quarto, quantidade_hospedes=qtd, status=status,
                    data_checkin=self.hoje + timedelta(days=entrada), data_checkout=self.hoje + timedelta(days=saida))
        r.full_clean()
        r.save()
        return r


class ValidadoresTests(TestCase):
    def test_cpf(self):
        self.assertTrue(cpf_valido(CPF_1))
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertFalse(cpf_valido("12345678900"))
        self.assertFalse(cpf_valido("11111111111"))


class HospedeTests(BaseTestCase):
    def test_cpf_unico(self):
        form = HospedeForm(data={"nome_completo": "Outro", "cpf": "529.982.247-25", "telefone": "(11) 91234-5678"})
        self.assertFalse(form.is_valid())
        self.assertIn("cpf", form.errors)

    def test_form_aceita_mascara_e_salva_digitos(self):
        form = HospedeForm(data={"nome_completo": "Novo Hóspede", "cpf": "111.444.777-35", "telefone": "(11) 91234-5678", "email": "a@b.com"})
        self.assertTrue(form.is_valid(), form.errors)
        h = form.save()
        self.assertEqual(h.cpf, CPF_2)
        self.assertEqual(h.telefone, "11912345678")

    def test_email_invalido(self):
        form = HospedeForm(data={"nome_completo": "X", "cpf": CPF_2, "telefone": "11912345678", "email": "invalido"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class ReservaRegrasTests(BaseTestCase):
    def test_calculo_diarias_e_total(self):
        r = self.criar_reserva(0, 3)
        self.assertEqual(r.diarias, 3)
        self.assertEqual(r.valor_diaria, Decimal("200.00"))
        self.assertEqual(r.valor_total, Decimal("600.00"))

    def test_checkout_posterior_ao_checkin(self):
        with self.assertRaises(ValidationError) as ctx:
            self.criar_reserva(3, 3)
        self.assertIn("data_checkout", ctx.exception.message_dict)

    def test_capacidade_do_quarto(self):
        with self.assertRaises(ValidationError) as ctx:
            self.criar_reserva(0, 2, qtd=3)
        self.assertIn("quantidade_hospedes", ctx.exception.message_dict)

    def test_bloqueia_conflito_de_datas(self):
        self.criar_reserva(0, 4)
        with self.assertRaises(ValidationError):
            self.criar_reserva(2, 6)
        # Datas encostadas (saída = entrada) não são conflito
        self.criar_reserva(4, 6)

    def test_cancelada_nao_bloqueia(self):
        r = self.criar_reserva(0, 4)
        r.cancelar()
        self.criar_reserva(1, 3)

    def test_preco_congelado_na_reserva(self):
        r = self.criar_reserva(0, 2)
        self.quarto.valor_diaria = Decimal("999.00")
        self.quarto.save()
        r.refresh_from_db()
        r.observacoes = "editada"
        r.save()
        self.assertEqual(r.valor_diaria, Decimal("200.00"))
        self.assertEqual(r.valor_total, Decimal("400.00"))

    def test_confirmar_pendente_com_conflito_falha(self):
        self.criar_reserva(0, 3)
        pendente = self.criar_reserva(5, 7, status=Reserva.Status.PENDENTE)
        Reserva.objects.filter(pk=pendente.pk).update(data_checkin=self.hoje + timedelta(days=1))
        pendente.refresh_from_db()
        with self.assertRaises(ValidationError):
            pendente.confirmar()


class CheckinCheckoutTests(BaseTestCase):
    def test_fluxo_completo(self):
        r = self.criar_reserva(0, 2)
        r.realizar_checkin()
        self.quarto.refresh_from_db()
        self.assertEqual(r.status, Reserva.Status.EM_ANDAMENTO)
        self.assertIsNotNone(r.checkin_realizado_em)
        self.assertEqual(self.quarto.status, Quarto.Status.OCUPADO)
        with self.assertRaises(ValidationError):
            r.realizar_checkin()  # não permite check-in duplicado
        r.realizar_checkout()
        self.quarto.refresh_from_db()
        self.assertEqual(r.status, Reserva.Status.FINALIZADA)
        self.assertIsNotNone(r.checkout_realizado_em)
        self.assertEqual(self.quarto.status, Quarto.Status.DISPONIVEL)

    def test_checkout_sem_checkin_bloqueado(self):
        r = self.criar_reserva(0, 2)
        with self.assertRaises(ValidationError):
            r.realizar_checkout()

    def test_checkin_pendente_bloqueado(self):
        r = self.criar_reserva(0, 2, status=Reserva.Status.PENDENTE)
        with self.assertRaises(ValidationError):
            r.realizar_checkin()

    def test_checkin_quarto_em_manutencao_bloqueado(self):
        r = self.criar_reserva(0, 2)
        Quarto.objects.filter(pk=self.quarto.pk).update(status=Quarto.Status.MANUTENCAO)
        with self.assertRaises(ValidationError):
            r.realizar_checkin()


class ViewsTests(BaseTestCase):
    def test_paginas_publicas(self):
        for nome in ["home", "sobre", "acomodacoes", "contato", "reservar", "login"]:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)

    def test_area_restrita_exige_login(self):
        resposta = self.client.get(reverse("dashboard"))
        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_usuario_sem_perfil_recebe_403(self):
        User.objects.create_user("visitante", password="senha-teste-123")
        self.client.login(username="visitante", password="senha-teste-123")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_paginas_administrativas(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        r = self.criar_reserva(0, 2)
        urls = [
            reverse("dashboard"), reverse("hospede_lista"), reverse("hospede_criar"),
            reverse("hospede_detalhes", args=[self.hospede.pk]), reverse("hospede_editar", args=[self.hospede.pk]),
            reverse("quarto_lista"), reverse("quarto_criar"), reverse("quarto_detalhes", args=[self.quarto.pk]),
            reverse("quarto_editar", args=[self.quarto.pk]), reverse("reserva_lista"), reverse("reserva_criar"),
            reverse("reserva_detalhes", args=[r.pk]), reverse("reserva_editar", args=[r.pk]),
            reverse("disponibilidade"), reverse("checkin_lista"), reverse("checkout_lista"),
            reverse("relatorios"), reverse("configuracoes"),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_solicitacao_publica_fica_pendente(self):
        dados = {
            "r-data_checkin": (self.hoje + timedelta(days=1)).isoformat(),
            "r-data_checkout": (self.hoje + timedelta(days=3)).isoformat(),
            "r-quantidade_hospedes": 2, "r-tipo": Quarto.Tipo.STANDARD,
            "r-nome_completo": "Visitante Site", "r-cpf": "111.444.777-35", "r-telefone": "(21) 99876-5432",
        }
        resposta = self.client.post(reverse("reservar"), dados)
        self.assertEqual(resposta.status_code, 200)
        reserva = Reserva.objects.get(hospede__cpf=CPF_2)
        self.assertEqual(reserva.status, Reserva.Status.PENDENTE)
        self.assertEqual(reserva.origem, Reserva.Origem.SITE)
        self.assertEqual(reserva.valor_total, Decimal("400.00"))

    def test_solicitacao_publica_sem_disponibilidade(self):
        self.criar_reserva(0, 5)
        dados = {
            "r-data_checkin": (self.hoje + timedelta(days=1)).isoformat(),
            "r-data_checkout": (self.hoje + timedelta(days=3)).isoformat(),
            "r-quantidade_hospedes": 1, "r-tipo": Quarto.Tipo.STANDARD,
            "r-nome_completo": "Visitante", "r-cpf": CPF_2, "r-telefone": "21998765432",
        }
        self.client.post(reverse("reservar"), dados)
        self.assertFalse(Reserva.objects.filter(hospede__cpf=CPF_2).exists())

    def test_criar_reserva_pela_recepcao_com_previa(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        dados = {"hospede": self.hospede.pk, "quarto": self.quarto.pk, "quantidade_hospedes": 2,
                 "data_checkin": self.hoje.isoformat(), "data_checkout": (self.hoje + timedelta(days=2)).isoformat()}
        previa = self.client.post(reverse("reserva_criar"), {**dados, "acao": "previsualizar"})
        self.assertContains(previa, "R$ 400,00")
        self.assertEqual(Reserva.objects.count(), 0)
        self.client.post(reverse("reserva_criar"), {**dados, "acao": "salvar"})
        self.assertEqual(Reserva.objects.get().status, Reserva.Status.PENDENTE)

    def test_fluxo_checkin_checkout_pelas_views(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        r = self.criar_reserva(0, 2)
        self.client.post(reverse("checkin_realizar", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, Reserva.Status.EM_ANDAMENTO)
        resposta = self.client.post(reverse("checkout_realizar", args=[r.pk]))
        self.assertRedirects(resposta, reverse("checkout_resumo", args=[r.pk]))

    def test_exclusao_protegida_por_vinculo(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        self.usuario.is_superuser = True
        self.usuario.save()
        self.criar_reserva(0, 2)
        self.client.post(reverse("hospede_excluir", args=[self.hospede.pk]))
        self.assertTrue(Hospede.objects.filter(pk=self.hospede.pk).exists())

    def test_exclusao_exige_permissao(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        resposta = self.client.post(reverse("quarto_excluir", args=[self.quarto.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Quarto.objects.filter(pk=self.quarto.pk).exists())

    def test_exportar_csv(self):
        self.client.login(username="recepcao", password="senha-teste-123")
        self.criar_reserva(0, 2)
        resposta = self.client.get(reverse("relatorios") + "?exportar=csv")
        self.assertEqual(resposta["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Hóspede Teste", resposta.content.decode("utf-8"))


class AdminTests(TestCase):
    def test_models_registrados(self):
        for model in (Hospede, Quarto, Reserva):
            self.assertTrue(site.is_registered(model))
