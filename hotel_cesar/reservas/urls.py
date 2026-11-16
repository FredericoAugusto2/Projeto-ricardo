from django.urls import path

from . import views

urlpatterns = [
    # Site institucional
    path("", views.HomeView.as_view(), name="home"),
    path("sobre/", views.SobreView.as_view(), name="sobre"),
    path("acomodacoes/", views.AcomodacoesView.as_view(), name="acomodacoes"),
    path("reservar/", views.ReservarView.as_view(), name="reservar"),
    path("contato/", views.ContatoView.as_view(), name="contato"),

    # Autenticação
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    # Sistema administrativo
    path("painel/", views.DashboardView.as_view(), name="dashboard"),

    path("painel/hospedes/", views.HospedeListView.as_view(), name="hospede_lista"),
    path("painel/hospedes/novo/", views.HospedeCreateView.as_view(), name="hospede_criar"),
    path("painel/hospedes/<int:pk>/", views.HospedeDetailView.as_view(), name="hospede_detalhes"),
    path("painel/hospedes/<int:pk>/editar/", views.HospedeUpdateView.as_view(), name="hospede_editar"),
    path("painel/hospedes/<int:pk>/excluir/", views.HospedeDeleteView.as_view(), name="hospede_excluir"),

    path("painel/quartos/", views.QuartoListView.as_view(), name="quarto_lista"),
    path("painel/quartos/novo/", views.QuartoCreateView.as_view(), name="quarto_criar"),
    path("painel/quartos/<int:pk>/", views.QuartoDetailView.as_view(), name="quarto_detalhes"),
    path("painel/quartos/<int:pk>/editar/", views.QuartoUpdateView.as_view(), name="quarto_editar"),
    path("painel/quartos/<int:pk>/status/", views.QuartoStatusView.as_view(), name="quarto_status"),
    path("painel/quartos/<int:pk>/excluir/", views.QuartoDeleteView.as_view(), name="quarto_excluir"),

    path("painel/reservas/", views.ReservaListView.as_view(), name="reserva_lista"),
    path("painel/reservas/nova/", views.ReservaCreateView.as_view(), name="reserva_criar"),
    path("painel/reservas/disponibilidade/", views.DisponibilidadeView.as_view(), name="disponibilidade"),
    path("painel/reservas/<int:pk>/", views.ReservaDetailView.as_view(), name="reserva_detalhes"),
    path("painel/reservas/<int:pk>/editar/", views.ReservaUpdateView.as_view(), name="reserva_editar"),
    path("painel/reservas/<int:pk>/confirmar/", views.ReservaConfirmarView.as_view(), name="reserva_confirmar"),
    path("painel/reservas/<int:pk>/cancelar/", views.ReservaCancelarView.as_view(), name="reserva_cancelar"),

    path("painel/check-in/", views.CheckinListView.as_view(), name="checkin_lista"),
    path("painel/check-in/<int:pk>/", views.CheckinRealizarView.as_view(), name="checkin_realizar"),
    path("painel/check-out/", views.CheckoutListView.as_view(), name="checkout_lista"),
    path("painel/check-out/<int:pk>/", views.CheckoutRealizarView.as_view(), name="checkout_realizar"),
    path("painel/check-out/<int:pk>/resumo/", views.CheckoutResumoView.as_view(), name="checkout_resumo"),

    path("painel/relatorios/", views.RelatoriosView.as_view(), name="relatorios"),
    path("painel/configuracoes/", views.ConfiguracoesView.as_view(), name="configuracoes"),
]
