from django.conf import settings


def hotel(request):
    """Disponibiliza as informações institucionais e contadores do menu."""
    contexto = {"HOTEL": settings.HOTEL_INFO}
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        from .models import MensagemContato, Reserva

        contexto["menu_pendentes"] = Reserva.objects.filter(status=Reserva.Status.PENDENTE).count()
        contexto["menu_mensagens"] = MensagemContato.objects.filter(lida=False).count()
    return contexto
