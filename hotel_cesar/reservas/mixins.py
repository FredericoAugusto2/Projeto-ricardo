"""Controle de acesso da área administrativa."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

GRUPO_FUNCIONARIOS = "Funcionários"
GRUPO_ADMINISTRADORES = "Administradores"


def eh_funcionario(user):
    """Funcionários, administradores e equipe (is_staff) acessam o sistema."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=[GRUPO_FUNCIONARIOS, GRUPO_ADMINISTRADORES]).exists()


class FuncionarioRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Exige login; usuários sem perfil de funcionário recebem erro 403."""

    raise_exception = False

    def test_func(self):
        return eh_funcionario(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Seu usuário não possui acesso ao sistema administrativo.")
        return super().handle_no_permission()


class PermissaoMixin(FuncionarioRequiredMixin):
    """Exige uma permissão específica do Django (ex.: excluir registros)."""

    permissao = None

    def test_func(self):
        if not super().test_func():
            return False
        return self.permissao is None or self.request.user.has_perm(self.permissao)
