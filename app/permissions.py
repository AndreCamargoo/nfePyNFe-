import re
from rest_framework import permissions
from django.core.cache import cache

from empresa.models import Funcionario, RotasPermitidas, Empresa
from sistema.models import RotaSistema, GrupoRotaSistema, EmpresaSistema


class HasSystemAccess(permissions.BasePermission):
    """
    Permissão para verificar se o usuário tem acesso ao sistema específico.

    Verifica se:
    - O usuário é dono de uma empresa que contratou o sistema
    - O usuário é funcionário de uma empresa que contratou o sistema
    - O sistema está ativo para a empresa
    """

    def has_permission(self, request, view):
        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return True

        # Obter o sistema da view ou do request
        system_id = getattr(view, 'system_id', None)
        system_name = getattr(view, 'system_name', None)

        # Se não especificado, tentar obter do request (middleware)
        if not system_id:
            system_id = getattr(request, 'sistema_id', None)
            system_name = getattr(request, 'sistema_nome', None)

        if not system_id:
            # Se não tem sistema definido, é um endpoint público ou genérico
            return True

        # Tentar obter do cache
        cache_key = f"user_system_access_{request.user.id}_{system_id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            if cached_result.get('has_access'):
                request.current_empresa_id = cached_result.get('empresa_id')
                request.current_funcionario_id = cached_result.get('funcionario_id')
            return cached_result.get('has_access', False)

        # Verificar se usuário tem empresa com este sistema
        # 1. Como dono da empresa
        empresas_dono = Empresa.objects.filter(
            usuario=request.user,
            status='1',
            sistema_id=system_id
        )

        for empresa in empresas_dono:
            if EmpresaSistema.objects.filter(
                empresa=empresa,
                sistema_id=system_id,
                ativo=True
            ).exists():
                # Armazenar empresa atual no request para uso nas views
                request.current_empresa = empresa

                # Salvar no cache
                cache.set(cache_key, {
                    'has_access': True,
                    'empresa_id': empresa.id,
                    'funcionario_id': None
                }, 3600)  # Cache por 1 hora

                return True

        # 2. Como funcionário
        funcionarios = Funcionario.objects.filter(
            user=request.user,
            status='1',
            empresa__status='1',
            empresa__sistema_id=system_id
        ).select_related('empresa')

        for funcionario in funcionarios:
            if EmpresaSistema.objects.filter(
                empresa=funcionario.empresa,
                sistema_id=system_id,
                ativo=True
            ).exists():
                # Armazenar empresa e funcionário atual no request
                request.current_empresa = funcionario.empresa
                request.current_funcionario = funcionario

                # Salvar no cache
                cache.set(cache_key, {
                    'has_access': True,
                    'empresa_id': funcionario.empresa.id,
                    'funcionario_id': funcionario.id
                }, 3600)

                return True

        # Salvar resultado negativo no cache
        cache.set(cache_key, {'has_access': False}, 600)  # Cache negativo por 10 minutos

        return False

    def has_object_permission(self, request, view, obj):
        # Para permissões em objetos específicos
        return self.has_permission(request, view)


class HasEmpresaPermission(permissions.BasePermission):
    """
    Permissão para verificar se o usuário tem acesso a uma empresa específica.

    Verifica se:
    - O usuário é dono da empresa
    - O usuário é funcionário da empresa
    """

    def has_permission(self, request, view):
        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return True

        # Obter empresa_id da URL ou query params
        empresa_id = view.kwargs.get('empresa_id') or request.query_params.get('empresa_id')

        if not empresa_id:
            return True

        try:
            empresa_id = int(empresa_id)
        except (ValueError, TypeError):
            return False

        # Tentar obter do cache
        cache_key = f"user_empresa_access_{request.user.id}_{empresa_id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Verificar se usuário é dono da empresa
        if Empresa.objects.filter(id=empresa_id, usuario=request.user, status='1').exists():
            cache.set(cache_key, True, 3600)
            return True

        # Verificar se usuário é funcionário da empresa
        if Funcionario.objects.filter(
            user=request.user,
            empresa_id=empresa_id,
            status='1'
        ).exists():
            cache.set(cache_key, True, 3600)
            return True

        cache.set(cache_key, False, 600)
        return False


class HasFuncionarioPermission(permissions.BasePermission):
    """
    Permissão para verificar se o usuário pode gerenciar um funcionário.

    Verifica se:
    - Usuário é dono da empresa do funcionário
    - Usuário é o próprio funcionário
    """

    def has_permission(self, request, view):
        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return True

        funcionario_id = view.kwargs.get('pk') or view.kwargs.get('funcionario_id')

        if not funcionario_id:
            return True

        # Tentar obter do cache
        cache_key = f"user_funcionario_access_{request.user.id}_{funcionario_id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        try:
            funcionario = Funcionario.objects.select_related('empresa').get(id=funcionario_id, status='1')
        except Funcionario.DoesNotExist:
            cache.set(cache_key, False, 600)
            return False

        # Usuário é dono da empresa do funcionário
        if funcionario.empresa.usuario == request.user:
            cache.set(cache_key, True, 3600)
            return True

        # Usuário é o próprio funcionário
        if funcionario.user == request.user:
            cache.set(cache_key, True, 3600)
            return True

        cache.set(cache_key, False, 600)
        return False


class GlobalDefaultPermission(permissions.BasePermission):
    """
    Permissão para Django Admin - NÃO USAR EM API REST!
    Usar apenas em views do Django Admin.
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

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

        # Tentar obter do cache
        cache_key = f"user_independent_or_admin_{request.user.id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Verifica se o usuário é funcionário de alguma empresa
        funcionarios = Funcionario.objects.filter(user=request.user)

        # Se NÃO é funcionário de nenhuma empresa → PERMITE TUDO
        if not funcionarios.exists():
            cache.set(cache_key, True, 3600)
            return True

        # Se é funcionário, verifica se é ADMIN em alguma empresa → PERMITE TUDO
        if funcionarios.filter(role=Funcionario.ADMIN).exists():
            cache.set(cache_key, True, 3600)
            return True

        # Se é apenas funcionário (não-admin) em qualquer empresa → BLOQUEIA TUDO
        cache.set(cache_key, False, 600)
        return False

    def has_object_permission(self, request, view, obj):
        # A mesma lógica se aplica para permissões em objetos específicos
        return self.has_permission(request, view)


class PodeAcessarRotasFuncionario(permissions.BasePermission):
    """
    Permissão para verificar se um funcionário tem acesso a uma rota específica.

    Verifica:
    - Acesso direto via RotasPermitidas
    - Acesso via GrupoRotaSistema
    - Suporte a rotas com parâmetros (regex)
    - Cache para otimização
    """

    # Cache TTL em segundos
    CACHE_TTL_ACCESS = 3600  # 1 hora para acesso positivo
    CACHE_TTL_NEGATIVE = 600  # 10 minutos para acesso negativo

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

            # Tentar obter do cache
            cache_key = f"rota_access_{user.id}_{metodo}_{path}"
            cached_result = cache.get(cache_key)

            if cached_result is not None:
                return cached_result

            # Buscar a rota no sistema que corresponde ao path
            rota_sistema = self._encontrar_rota_correspondente(path, metodo)

            if not rota_sistema:
                # Salvar resultado negativo no cache
                cache.set(cache_key, False, self.CACHE_TTL_NEGATIVE)
                return False

            # Verificar acesso direto através de RotasPermitidas
            acesso_direto = RotasPermitidas.objects.filter(
                funcionario__user=user,
                funcionario__status='1',
                rota__rotas=rota_sistema,  # Grupo que contém esta rota
                status='1'
            ).exists()

            if acesso_direto:
                # Salvar acesso positivo no cache
                cache.set(cache_key, True, self.CACHE_TTL_ACCESS)
                return True

            # Verificar acesso através de grupos de rotas
            acesso_grupo = GrupoRotaSistema.objects.filter(
                usuario=user,
                rotas=rota_sistema
            ).exists()

            if acesso_grupo:
                # Salvar acesso positivo no cache
                cache.set(cache_key, True, self.CACHE_TTL_ACCESS)
                return True

            # Salvar resultado negativo no cache
            cache.set(cache_key, False, self.CACHE_TTL_NEGATIVE)
            return False

        except Exception as e:
            print(f"Erro ao verificar acesso: {str(e)}")
            return False

    def _encontrar_rota_correspondente(self, path, metodo):
        """
        Encontra a rota do sistema que melhor corresponde ao path solicitado
        Com suporte a cache e regex para parâmetros
        """
        # Normalizar o path (remover trailing slash para consistência)
        normalized_path = path.rstrip('/')

        # Tentar obter do cache de rotas
        cache_key = f"rota_match_{metodo}_{normalized_path}"
        cached_rota_id = cache.get(cache_key)

        if cached_rota_id:
            try:
                return RotaSistema.objects.get(id=cached_rota_id)
            except RotaSistema.DoesNotExist:
                pass

        # Buscar TODAS as rotas do sistema com este método
        rotas_possiveis = RotaSistema.objects.filter(metodo=metodo)

        for rota in rotas_possiveis:
            rota_path = rota.path.rstrip('/')

            # Se a rota não tem parâmetros, fazer match exato
            if '<' not in rota_path and '>' not in rota_path:
                if normalized_path == rota_path:
                    # Salvar no cache
                    cache.set(cache_key, rota.id, self.CACHE_TTL_ACCESS)
                    return rota
                continue

            # Se a rota tem parâmetros, fazer match por padrão
            # Exemplo: rota_path = "/api/v1/nfes/<int:pk>/"
            #          normalized_path = "/api/v1/nfes/123"

            # Criar regex a partir do path da rota
            pattern = self._convert_route_to_regex(rota_path)

            if re.match(pattern, normalized_path):
                # Salvar no cache
                cache.set(cache_key, rota.id, self.CACHE_TTL_ACCESS)
                return rota

        return None

    def _convert_route_to_regex(self, route_path):
        """
        Converte uma rota Django com parâmetros para regex
        Exemplo: "/api/v1/nfes/<int:pk>/" → "^/api/v1/nfes/[0-9]+/?$"
        """

        # Normalizar o path
        path = route_path.rstrip('/')

        # Mapeamento de tipos de parâmetros para regex
        param_patterns = {
            r'<int:\w+>': r'[0-9]+',           # inteiro
            r'<uuid:\w+>': r'[a-f0-9-]{36}',    # UUID
            r'<slug:\w+>': r'[a-z0-9-]+',       # slug
            r'<str:\w+>': r'[^/]+',             # string
            r'<\w+>': r'[^/]+',                 # genérico
        }

        # Aplicar cada padrão
        for pattern, replacement in param_patterns.items():
            path = re.sub(pattern, replacement, path)

        # Adicionar âncoras de início e fim, e tornar a barra final opcional
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
        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return True

        # Tentar obter do cache
        cache_key = f"user_manage_rotas_{request.user.id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Verifica se é funcionário
        funcionarios = Funcionario.objects.filter(user=request.user)

        # Se não é funcionário → PERMITE (dono independente)
        if not funcionarios.exists():
            cache.set(cache_key, True, 3600)
            return True

        # Se é funcionário, verifica se é ADMIN em alguma empresa matriz
        if funcionarios.filter(
            role=Funcionario.ADMIN,
            empresa__matriz_filial__isnull=True  # Apenas empresas matriz
        ).exists():
            cache.set(cache_key, True, 3600)
            return True

        cache.set(cache_key, False, 600)
        return False

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class ClearPermissionCache(permissions.BasePermission):
    """
    Permissão especial para limpar o cache de permissões.
    Útil após alterações em permissões de funcionários.
    """

    def has_permission(self, request, view):
        if not request.user.is_superuser:
            return False

        # Limpar caches relacionados a permissões
        cache_keys = [
            "user_system_access_*",
            "user_empresa_access_*",
            "user_funcionario_access_*",
            "user_independent_or_admin_*",
            "rota_access_*",
            "rota_match_*",
            "user_manage_rotas_*",
        ]

        for pattern in cache_keys:
            cache.delete_pattern(pattern)

        return True


# ==================== PERMISSÕES PERSONALIZADAS ====================

class AcessoAzevedoCloudPermission(permissions.BasePermission):
    """Verifica se o usuário tem acesso ao módulo Azevedo Cloud"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Admin tem acesso total
        if request.user.is_superuser:
            return True

        # Verifica se o usuário é funcionário de alguma empresa com acesso ao sistema Azevedo Cloud
        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return False

        # Verifica se a empresa tem o sistema Azevedo Cloud (id=1)
        empresa_sistema = EmpresaSistema.objects.filter(
            empresa=funcionario.empresa,
            sistema_id=1,  # Azevedo dropBox
            ativo=True
        ).exists()

        return empresa_sistema


class PermissaoSegmento(permissions.BasePermission):
    """Verifica se o usuário tem acesso ao segmento específico"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return False

        # Empresa de auditoria dona do segmento
        if obj.empresa_auditoria == funcionario.empresa:
            return True

        # Funcionário é responsável pelo segmento
        if obj.responsaveis.filter(id=funcionario.id).exists():
            return True

        # Empresa cliente vinculada ao segmento
        if obj.clientes.filter(id=funcionario.empresa.id).exists():
            return True

        return False


class PodeCriarSegmento(permissions.BasePermission):
    """
    Permissão para criar segmentos (arquitetura de pastas).

    Quem pode criar:
    - Superusuário (is_superuser)
    - Staff (is_staff) que tenha os cargos: AUDITOR ou ADMINISTRATIVO
    """

    message = "Apenas superusuários, auditores ou administrativos podem criar segmentos."

    # Cargos permitidos para criar segmentos
    ROLES_PERMITIDAS = [
        Funcionario.AUDITOR,
        Funcionario.ADMINISTRATIVO,
    ]

    def has_permission(self, request, view):
        # 1. Superusuário sempre pode
        if request.user.is_superuser:
            return True

        # 2. Verificar se é staff (funcionário da equipe)
        if not request.user.is_staff:
            self.message = "Apenas membros da equipe podem criar segmentos."
            return False

        # 3. Verificar o cargo do funcionário
        funcionario = Funcionario.objects.filter(
            user=request.user,
            status='1'
        ).select_related('empresa').first()

        if not funcionario:
            self.message = "Usuário não está vinculado a nenhuma empresa ativa."
            return False

        # 4. Verificar se o cargo é permitido
        if funcionario.role not in self.ROLES_PERMITIDAS:
            self.message = f"Cargo '{funcionario.get_role_display()}' não tem permissão para criar segmentos. Apenas Auditores e Administrativos."
            return False

        # Armazenar o funcionário no request para uso posterior
        request.current_funcionario = funcionario
        request.current_empresa = funcionario.empresa

        return True

    def has_object_permission(self, request, view, obj):
        # Para operações em objetos existentes (editar/deletar)
        return self.has_permission(request, view)


class PodeGerenciarSegmento(permissions.BasePermission):
    """
    Permissão para gerenciar (editar/deletar) um segmento específico.

    Quem pode:
    - Superusuário
    - Staff que seja ADMIN, AUDITOR ou ADMINISTRATIVO
    - Funcionário que seja responsável pelo segmento
    """

    def has_permission(self, request, view):
        # Superusuário sempre pode
        if request.user.is_superuser:
            return True

        # Verificar se é staff
        if not request.user.is_staff:
            return False

        return True

    def has_object_permission(self, request, view, obj):
        # Superusuário sempre pode
        if request.user.is_superuser:
            return True

        # Buscar funcionário do usuário
        funcionario = Funcionario.objects.filter(
            user=request.user,
            status='1'
        ).select_related('empresa').first()

        if not funcionario:
            return False

        # ADMIN, AUDITOR e ADMINISTRATIVO podem gerenciar
        if funcionario.role in [Funcionario.ADMIN, Funcionario.AUDITOR, Funcionario.ADMINISTRATIVO]:
            # Verificar se o segmento pertence à empresa do funcionário
            if obj.empresa_auditoria == funcionario.empresa:
                return True

        # Funcionário é responsável pelo segmento
        if obj.responsaveis.filter(id=funcionario.id).exists():
            return True

        return False


class PermissaoArquivo(permissions.BasePermission):
    """Verifica se o usuário tem acesso ao arquivo específico"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return False

        # Enviou o arquivo
        if obj.enviado_por == request.user:
            return True

        # Empresa cliente dona do arquivo
        if obj.cliente == funcionario.empresa:
            return True

        # Empresa auditoria dona do segmento
        segmento = obj.subpasta.segmento
        if segmento.empresa_auditoria == funcionario.empresa:
            return True

        return False
