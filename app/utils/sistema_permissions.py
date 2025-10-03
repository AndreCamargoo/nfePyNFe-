import re

from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

from empresa.models import Empresa
from sistema.models import EmpresaSistema, RotaSistema, GrupoRotaSistema
from acesso.models import UsuarioEmpresa, UsuarioSistema, UsuarioPermissaoRota


class AcessoNegadoException(PermissionDenied):
    """Exceção personalizada para acesso negado com mensagens específicas"""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class IsAuthenticatedCustom(BasePermission):
    """
    PERMISSÃO PERSONALIZADA DE AUTENTICAÇÃO - SISTEMA HÍBRIDO

    Versão aprimorada do IsAuthenticated padrão que suporta dois tipos de usuários:
    1. ADMINISTRADORES: Usuários padrão do Django (auth_user)
    2. FUNCIONÁRIOS: Usuários customizados da empresa (UsuarioEmpresa)

    CARACTERÍSTICAS:
    - Verifica autenticação para ambos os tipos de usuário
    - Valida se o usuário ainda está ativo no banco de dados
    - Armazena objetos completos no request para uso posterior
    - Mantém compatibilidade com o ecossistema DRF

    FLUXO:
    1. Verifica autenticação básica → 2. Identifica tipo de usuário → 
    3. Valida status no banco → 4. Armazena objeto completo
    """

    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão para acessar a view.

        REALIZA TRÊS VERIFICAÇÕES EM CAMADAS:
        1. Usuário autenticado pelo Django (request.user.is_authenticated)
        2. Token JWT válido (request.auth exists)
        3. Usuário ativo no banco de dados (verificação adicional de segurança)

        Args:
            request: HttpRequest object com usuário e token
            view: View que está sendo acessada

        Returns:
            bool: True se usuário tem permissão, False caso contrário
        """

        # CAMADA 1: Verifica autenticação básica do Django
        # Garante que o authentication backend populou request.user corretamente
        if not request.user or not request.user.is_authenticated:
            return False

        # CAMADA 2: Verifica se o token JWT é válido
        # Importante para garantir que o token não foi revogado ou é inválido
        if not request.auth:
            return False

        # CAMADA 3: Verificações específicas por tipo de usuário
        if hasattr(request.user, 'tipo_usuario'):
            if request.user.tipo_usuario == 'funcionario':
                # VERIFICAÇÃO PARA FUNCIONÁRIOS: Valida se ainda está ativo na empresa
                return self._verificar_funcionario_ativo(request)
            elif request.user.tipo_usuario == 'admin':
                # VERIFICAÇÃO PARA ADMINS: Valida se usuário ainda está ativo no sistema
                return self._verificar_admin_ativo(request)

        # Fallback: Se não tem tipo_usuario, assume admin padrão (compatibilidade)
        return self._verificar_admin_ativo(request)

    def _verificar_funcionario_ativo(self, request):
        """
        VERIFICAÇÃO ESPECÍFICA PARA FUNCIONÁRIOS

        Valida se o funcionário ainda está ativo na empresa, mesmo tendo um token válido.
        Isso previne acesso por funcionários que foram desativados após a geração do token.

        CASOS DE USO:
        - Funcionário foi demitido mas ainda tem token válido
        - Funcionário foi desativado temporariamente
        - Empresa revogou acesso do funcionário

        Args:
            request: HttpRequest com usuário dummy populado

        Returns:
            bool: True se funcionário está ativo, False caso contrário
        """
        # Obtém o ID do funcionário do atributo customizado do usuário dummy
        funcionario_id = getattr(request.user, 'funcionario_id', None)

        # Safety check: garante que o ID existe
        if not funcionario_id:
            return False

        try:
            # BUSCA NO BANCO: Verifica se o funcionário ainda existe e está ativo
            # Esta query é crucial para segurança - valida o estado atual no banco
            usuario_empresa = UsuarioEmpresa.objects.get(
                id=funcionario_id,
                ativo=True
            )

            # ARMAZENA NO REQUEST: Objeto completo para uso posterior nas views
            # Isso evita ter que buscar novamente o mesmo objeto nas views
            request.usuario_empresa = usuario_empresa

            return True

        except UsuarioEmpresa.DoesNotExist:
            # Funcionário não encontrado ou não está mais ativo
            # Possíveis causas: foi deletado, desativado, ou ID inválido
            return False

    def _verificar_admin_ativo(self, request):
        """
        VERIFICAÇÃO ESPECÍFICA PARA ADMINISTRADORES

        Valida se o usuário admin ainda está ativo no sistema, mesmo com token válido.
        Importante para revogar acesso de administradores desativados.

        CASOS DE USO:
        - Admin foi desativado mas token ainda é válido
        - Conta de admin foi suspensa temporariamente
        - Usuário foi deletado do sistema

        Args:
            request: HttpRequest com usuário admin populado

        Returns:
            bool: True se admin está ativo, False caso contrário
        """
        # Obtém o ID do usuário admin
        # Para admin, usamos request.user.id (objeto User real)
        usuario_id = request.user.id

        # Safety check
        if not usuario_id:
            return False

        try:
            # BUSCA NO BANCO: Verifica se o admin ainda existe e está ativo
            User = get_user_model()

            usuario = User.objects.get(
                id=usuario_id,
                is_active=True
            )

            # ARMAZENA NO REQUEST: Embora request.user já seja o objeto completo,
            # armazenamos novamente para consistência com funcionários
            request.usuario = usuario

            return True

        except User.DoesNotExist:
            # Admin não encontrado ou não está mais ativo
            return False


class TemAcessoSistema(BasePermission):
    """
    PERMISSÃO DE ACESSO AO SISTEMA - CONTROLE MULTINÍVEL COM GRUPOS

    Verifica se o usuário/empresa tem permissão para acessar o sistema específico da rota atual.
    Implementa um sistema de controle de acesso em 4 camadas:

    CAMADAS DE VERIFICAÇÃO:
    1. IDENTIFICAÇÃO: Detecta qual sistema e rota estão sendo acessados
    2. EMPRESA: Verifica se a empresa tem acesso ao sistema
    3. USUÁRIO: Verifica se o usuário tem acesso ao sistema
    4. ROTA: Verifica se o usuário tem permissão para a rota (individual ou via grupo)

    ARQUITETURA DO SISTEMA:
    - EmpresaSistema: Relação empresa × sistema (empresa tem acesso ao sistema?)
    - UsuarioSistema: Relação usuário × sistema (usuário tem acesso ao sistema?)
    - RotaSistema: Cadastro de rotas × sistema (qual rota pertence a qual sistema?)
    - GrupoRotaSistema: Grupos de rotas × sistema (agrupamento lógico de rotas)
    - UsuarioPermissaoRota: Permissões usuário × rota (individual ou via grupo)

    FLUXO COMPLETO:
    1. Identifica rota → 2. Encontra sistema → 3. Valida empresa → 4. Valida usuário → 5. Valida rota
    """

    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão para acessar o sistema da rota atual.

        LÓGICA PRINCIPAL:
        - Para ADMIN: Usa ID do usuário como empresa_id (admin é dono da empresa)
        - Para FUNCIONÁRIO: Usa empresa_id e funcionario_id do token
        - Verifica se a EMPRESA tem acesso ao SISTEMA
        - Verifica se o USUÁRIO tem acesso ao SISTEMA
        - Verifica se o USUÁRIO tem permissão para a ROTA (individual ou grupo)

        Args:
            request: HttpRequest com usuário autenticado
            view: View que está sendo acessada

        Returns:
            bool: True se tem acesso completo ao sistema, False caso contrário
        """
        # =========================================================================
        # FASE 1: PREPARAÇÃO DOS IDs (EMPRESA E USUÁRIO)
        # =========================================================================

        empresa_id = None
        funcionario_id = None

        # Para ADMIN: tem acesso total, mas ainda precisa verificar a rota e sistema
        if request.auth.get('tipo_usuario') == 'admin':
            # Admin tem acesso, mas ainda precisa identificar o sistema da rota
            empresa_id = request.user.id  # Para possíveis verificações futuras
        else:
            # CASO FUNCIONÁRIO: Obtém IDs da empresa e do funcionário
            # Esses IDs vêm das claims do token JWT
            empresa_id = request.user.empresa_id
            funcionario_id = request.user.funcionario_id

            # Safety check: garante que ambos IDs existem
            if not empresa_id:
                raise AcessoNegadoException(
                    "ID da empresa não encontrado no token",
                    code="empresa_id_missing"
                )

            if not funcionario_id:
                raise AcessoNegadoException(
                    "ID do funcionário não encontrado no token",
                    code="funcionario_id_missing"
                )

        # =========================================================================
        # FASE 2: IDENTIFICAÇÃO DA ROTA E SISTEMA (OBRIGATÓRIA PARA TODOS)
        # =========================================================================

        # Busca a rota atual no banco de dados baseada no path e método
        rota = self.get_rota_atual(request)

        if not rota:
            # Rota não encontrada no cadastro - NEGA acesso por segurança
            # Isso previne acesso a rotas não mapeadas no sistema de permissões
            raise AcessoNegadoException(
                f"Rota não encontrada ou não cadastrada: {request.method} {request.path}",
                code="rota_nao_encontrada"
            )

        # Obtém o sistema ao qual a rota pertence
        sistema = rota.sistema

        # =========================================================================
        # FASE 3: VERIFICAÇÃO DE ACESSO DA EMPRESA AO SISTEMA
        # =========================================================================

        try:
            # Verifica se a EMPRESA tem acesso ao SISTEMA
            # Relação: EmpresaSistema (empresa × sistema)
            EmpresaSistema.objects.get(
                empresa_id=empresa_id,  # ID da empresa
                sistema=sistema,  # Sistema da rota atual
                ativo=True  # MUST be active
            )
        except EmpresaSistema.DoesNotExist:
            # Empresa não tem acesso ao sistema ou acesso está inativo
            raise AcessoNegadoException(
                f"Empresa não tem acesso ao sistema '{sistema.nome}'",
                code="empresa_sem_acesso_sistema"
            )

        # =========================================================================
        # FASE 4: VERIFICAÇÃO DE ACESSO DO USUÁRIO AO SISTEMA
        # =========================================================================

        # Para ADMIN: não verifica UsuarioSistema (admin tem acesso total)
        if request.auth.get('tipo_usuario') == 'admin':
            # Admin tem acesso a todos os sistemas da sua empresa
            request.sistema_atual = sistema  # Armazena para uso posterior
            return True

        # Para FUNCIONÁRIO: verifica acesso específico ao sistema
        try:
            # Verifica se o FUNCIONÁRIO tem acesso ao SISTEMA
            # Relação: UsuarioSistema (usuário × sistema)
            usuario_sistema = UsuarioSistema.objects.get(
                usuario_empresa_id=funcionario_id,  # ID do funcionário
                sistema=sistema,  # Sistema da rota atual
                ativo=True  # MUST be active
            )

            # =========================================================================
            # ARMAZENAMENTO PARA USO POSTERIOR NAS VIEWS
            # =========================================================================

            # Armazena a relação usuário-sistema no request
            # Evita ter que buscar novamente nas views ou outras permissions
            request.usuario_sistema = usuario_sistema

            # Armazena o sistema atual para referência
            request.sistema_atual = sistema

        except UsuarioSistema.DoesNotExist:
            # Funcionário não tem acesso ao sistema ou acesso está inativo
            raise AcessoNegadoException(
                f"Usuário não tem acesso ao sistema '{sistema.nome}'",
                code="usuario_sem_acesso_sistema"
            )

        # =========================================================================
        # FASE 5: VERIFICAÇÃO DE ACESSO DO FUNCIONÁRIO À ROTA (INDIVIDUAL OU GRUPO)
        # =========================================================================

        # Verifica se o FUNCIONÁRIO tem permissão para a ROTA específica
        # ESTRATÉGIA: Busca por permissão INDIVIDUAL primeiro, depois por GRUPO
        permissao_encontrada = self._buscar_permissao_rota(usuario_sistema, rota)

        if permissao_encontrada:
            # PERMISSÃO ENCONTRADA - Armazena detalhes e permite acesso
            request.permissao_rota = permissao_encontrada
            request.tipo_permissao = "individual" if permissao_encontrada.rota else "grupo"
            return True
        else:
            # NENHUMA PERMISSÃO ENCONTRADA - Acesso negado
            raise AcessoNegadoException(
                f"Usuário não tem permissão para acessar a rota '{rota.nome}' "
                f"({request.method} {rota.path}) - nem individualmente nem via grupo",
                code="usuario_sem_permissao_rota"
            )

    def _buscar_permissao_rota(self, usuario_sistema, rota):
        """
        Busca permissão do usuário para uma rota específica.

        ESTRATÉGIA DE BUSCA EM DUAS ETAPAS:
        1. PERMISSÃO INDIVIDUAL: Verifica se há permissão explícita para a rota
        2. PERMISSÃO VIA GRUPO: Verifica se a rota está em algum grupo permitido

        Prioridade: Individual > Grupo (permissões individuais sobrescrevem grupos)

        Args:
            usuario_sistema: Objeto UsuarioSistema do usuário
            rota: Objeto RotaSistema da rota atual

        Returns:
            UsuarioPermissaoRota: Objeto de permissão encontrado ou None
        """
        # =========================================================================
        # ETAPA 1: BUSCA POR PERMISSÃO INDIVIDUAL EXPLÍCITA
        # =========================================================================
        try:
            permissao_individual = UsuarioPermissaoRota.objects.get(
                usuario_sistema=usuario_sistema,
                rota=rota,  # Permissão específica para esta rota
                permitido=True  # MUST be True
            )
            # PERMISSÃO INDIVIDUAL ENCONTRADA - Retorna imediatamente
            return permissao_individual
        except UsuarioPermissaoRota.DoesNotExist:
            # Não tem permissão individual, continua para verificação de grupo
            pass

        # =========================================================================
        # ETAPA 2: BUSCA POR PERMISSÃO VIA GRUPO
        # =========================================================================
        try:
            # Busca grupos que contenham esta rota específica
            grupos_com_rota = GrupoRotaSistema.objects.filter(
                sistema=rota.sistema,
                rotas=rota  # Grupos que contêm esta rota
            )

            if not grupos_com_rota.exists():
                # Rota não está em nenhum grupo - não há como ter permissão via grupo
                return None

            # Busca permissão do usuário em algum desses grupos
            permissao_grupo = UsuarioPermissaoRota.objects.get(
                usuario_sistema=usuario_sistema,
                grupo__in=grupos_com_rota,  # Usuário tem permissão em grupo que contém a rota
                permitido=True  # MUST be True
            )
            # PERMISSÃO VIA GRUPO ENCONTRADA
            return permissao_grupo

        except UsuarioPermissaoRota.DoesNotExist:
            # Não tem permissão via grupo também
            return None

    def get_rota_atual(self, request):
        """
        IDENTIFICA A ROTA ATUAL NO BANCO DE DADOS

        Busca a rota cadastrada que corresponde ao path e método da request.
        Suporta URLs com parâmetros através de conversão para regex.

        EXEMPLOS DE MATCH:
        - Path request: "/api/v1/nfes/123/" 
        - Path cadastrado: "/api/v1/nfes/{id}/" → Match
        - Path cadastrado: "/api/v1/clientes/" → No match

        Args:
            request: HttpRequest com path e método

        Returns:
            RotaSistema: Objeto da rota encontrada ou None se não encontrada
        """
        path = request.path
        metodo = request.method.upper()

        try:
            # Busca TODAS as rotas cadastradas no sistema com eager loading do sistema
            # select_related('sistema') otimiza performance evitando N+1 queries
            rotas = RotaSistema.objects.select_related('sistema').all()

            # Itera por todas as rotas cadastradas para encontrar match
            for rota in rotas:
                # Verifica primeiro o método HTTP (filtro rápido)
                if rota.metodo.upper() != metodo:
                    continue  # Pula se método não coincide

                # Converte o pattern da rota cadastrada para regex
                pattern = self.converter_path_para_regex(rota.path)

                # Verifica se o path da request match com o pattern da rota
                if re.match(pattern, path):
                    return rota  # Rota encontrada!

            # Nenhuma rota cadastrada corresponde à request
            return None

        except Exception as e:
            # Em caso de erro no banco ou processamento, log e retorna None
            # Em produção, considerar logging do erro para debugging
            return None

    def converter_path_para_regex(self, path):
        """
        CONVERSÃO DE PATH PARA REGEX - SUPORTE A PARÂMETROS

        Converte paths com placeholders ({param}) para patterns regex
        que podem matchar URLs com valores dinâmicos.

        TRANSFORMAÇÕES:
        - "/api/nfes/{id}/" → "^/api/nfes/[^/]+/$"
        - "/api/users/{user_id}/posts/{post_id}/" → "^/api/users/[^/]+/posts/[^/]+/$"

        Args:
            path (str): Path da rota cadastrado (ex: "/api/nfes/{id}/")

        Returns:
            str: Pattern regex para matching
        """
        # FASE 1: Substitui placeholders {param} por grupos regex [^/]+
        # [^/]+ = um ou mais caracteres que não sejam barra
        pattern = re.sub(r'\{[^}]+\}', r'[^/]+', path)

        # FASE 2: Escapa caracteres especiais do path (exceto placeholders)
        # Ex: "/api.v1/nfes/" → "/api\.v1/nfes/" (ponto é escapado)
        pattern = re.escape(pattern)

        # FASE 3: Corrige as barras que foram escapadas indevidamente
        pattern = pattern.replace(r'\/', '/')

        # FASE 4: Corrige os placeholders que foram escapados
        pattern = pattern.replace(r'[^/]+', '[^/]+')

        # FASE 5: Adiciona âncoras para match exato
        pattern = '^' + pattern + '$'

        return pattern
