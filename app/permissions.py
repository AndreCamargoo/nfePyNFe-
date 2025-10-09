from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions

from empresa.models import Funcionario, RotasPermitidas
from sistema.models import RotaSistema, GrupoRotaSistema


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


class PodeAcessarRotasFuncionario(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user

        # Superusuário sempre tem acesso completo
        if user.is_superuser:
            return True

        # Verifica se o usuário é funcionário ativo de alguma empresa
        funcionarios = Funcionario.objects.filter(user=user, status='1')

        if not funcionarios.exists():
            return False

        # Se é ADMIN em alguma empresa → PERMITE TUDO
        if funcionarios.filter(role=Funcionario.ADMIN).exists():
            return True

        # Para funcionários não-ADMIN, verificar acesso específico à rota
        return self._verificar_acesso_rota_funcionario(request, user)

    def _verificar_acesso_rota_funcionario(self, request, user):
        """
        Verifica se o funcionário tem acesso à rota específica
        """
        try:
            # Obter informações da rota atual
            path = request.path
            metodo = request.method.upper()

            print(f"Verificando acesso para {user.username}: {metodo} {path}")

            # Buscar a rota no sistema que corresponde ao path
            rota_sistema = self._encontrar_rota_correspondente(path, metodo)

            if not rota_sistema:
                print(f"Rota do sistema não encontrada: {metodo} {path}")
                return False

            # Verificar acesso direto através de RotasPermitidas
            acesso_direto = RotasPermitidas.objects.filter(
                funcionario__user=user,
                funcionario__status='1',
                rota__rotas=rota_sistema,  # Grupo que contém esta rota
                status='1'
            ).exists()

            if acesso_direto:
                print(f"Acesso direto concedido via RotasPermitidas")
                return True

            # Verificar acesso através de grupos de rotas
            acesso_grupo = GrupoRotaSistema.objects.filter(
                usuario=user,
                rotas=rota_sistema
            ).exists()

            if acesso_grupo:
                print(f"Acesso concedido via GrupoRotaSistema")
                return True

            print(f"Nenhum acesso encontrado para a rota")
            return False

        except Exception as e:
            print(f"Erro ao verificar acesso: {str(e)}")
            return False

    def _encontrar_rota_correspondente(self, path, metodo):
        """
        Encontra a rota do sistema que melhor corresponde ao path solicitado
        """
        # Normalizar o path (remover trailing slash para consistência)
        normalized_path = path.rstrip('/')

        # Buscar TODAS as rotas do sistema com este método
        rotas_possiveis = RotaSistema.objects.filter(metodo=metodo)

        print(f"Buscando entre {rotas_possiveis.count()} rotas possíveis")

        for rota in rotas_possiveis:
            rota_path = rota.path.rstrip('/')

            # Se a rota não tem parâmetros, fazer match exato
            if '<' not in rota_path and '>' not in rota_path:
                if normalized_path == rota_path:
                    print(f"Match exato encontrado: {rota_path}")
                    return rota
                continue

            # Se a rota tem parâmetros, fazer match por padrão
            # Exemplo: rota_path = "/api/v1/nfes/<int:pk>/"
            #          normalized_path = "/api/v1/nfes/123"

            # Criar regex a partir do path da rota
            pattern = self._convert_route_to_regex(rota_path)

            import re
            if re.match(pattern, normalized_path):
                print(f"Match com parâmetros encontrado: {rota_path} -> {normalized_path}")
                return rota

        print(f"Nenhuma rota corresponde a: {normalized_path}")
        return None

    def _convert_route_to_regex(self, route_path):
        """
        Converte uma rota Django com parâmetros para regex
        Exemplo: "/api/v1/nfes/<int:pk>/" → "^/api/v1/nfes/[^/]+/$"
        """
        # Normalizar o path
        path = route_path.rstrip('/')

        # Substituir parâmetros por padrões regex
        path = path.replace('<int:pk>', r'[0-9]+')
        path = path.replace('<int:id>', r'[0-9]+')
        path = path.replace('<str:pk>', r'[^/]+')
        path = path.replace('<str:slug>', r'[^/]+')
        path = path.replace('<uuid:pk>', r'[a-f0-9-]+')
        path = path.replace('<int:documento>', r'[0-9]+')

        # Substituir qualquer outro parâmetro genérico
        import re
        path = re.sub(r'<[^>]+>', r'[^/]+', path)

        # Adicionar âncoras de início e fim
        return f'^{path}/?$'

    def has_object_permission(self, request, view, obj):
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
