from rest_framework import permissions

from empresa.models import Funcionario


class GlobalDefaultPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True  # superusuário sempre tem acesso

        model_permission_codename = self.__get_model_permission_codename(
            method=request.method,
            view=view
        )

        if not model_permission_codename:
            return False
        return request.user.has_perm(model_permission_codename)

    def __get_model_permission_codename(self, method, view):
        try:
            model_name = view.queryset.model._meta.model_name
            app_label = view.queryset.model._meta.app_label
            action = self.__get_action_sufix(method=method)
            return f'{app_label}.{action}_{model_name}'
        except AttributeError:
            return None

    def __get_action_sufix(self, method):
        method_actions = {
            'GET': 'view',
            'POST': 'add',
            'PUT': 'change',
            'PATCH': 'change',
            'DELETE': 'delete',
            'OPTIONS': 'view',
            'HEAD': 'view',
        }
        return method_actions.get(method, '')


class UsuarioIndependenteOuAdmin(permissions.BasePermission):
    """
    Permite TODOS os métodos (POST, PUT, GET, DELETE, PATCH) para:
    1. Usuários que NÃO são funcionários de nenhuma empresa (independentes)
    2. Administradores de empresas

    Bloqueia tudo para funcionários não-administradores
    """
    message = "Acesso permitido apenas para usuários independentes ou administradores."

    def has_permission(self, request, view):
        # Superusuário sempre tem acesso completo
        if request.user.is_superuser:
            return True

        # Verifica se o usuário é funcionário de alguma empresa
        funcionarios = Funcionario.objects.filter(user=request.user)

        # Se NÃO é funcionário de nenhuma empresa → PERMITE TUDO
        if not funcionarios.exists():
            return True

        # Se é funcionário, verifica se é ADMIN em alguma empresa → PERMITE TUDO
        if funcionarios.filter(role=Funcionario.ADMIN).exists():
            return True

        # Se é apenas funcionário (não-admin) em qualquer empresa → BLOQUEIA TUDO
        return False

    def has_object_permission(self, request, view, obj):
        # A mesma lógica se aplica para permissões em objetos específicos
        return self.has_permission(request, view)


class PodeGerenciarRotasFuncionarios(permissions.BasePermission):
    """
    Permite gerenciar rotas de funcionários apenas para:
    - Superusuários
    - Usuários independentes (dono da empresa)
    - Administradores de empresas matriz
    """
    message = "Apenas administradores de empresas matriz podem gerenciar rotas de funcionários."

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        # Verifica se é funcionário
        funcionarios = Funcionario.objects.filter(user=request.user)

        # Se não é funcionário → PERMITE (dono independente)
        if not funcionarios.exists():
            return True

        # Se é funcionário, verifica se é ADMIN em alguma empresa matriz
        if funcionarios.filter(
            role=Funcionario.ADMIN,
            empresa__matriz_filial__isnull=True  # Apenas empresas matriz
        ).exists():
            return True

        return False

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
