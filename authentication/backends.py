"""
SISTEMA DE AUTENTICAÇÃO CUSTOMIZADO - USUÁRIO DUMMY

ARQUITETURA:
Este sistema permite autenticação para dois tipos de usuários:
1. ADMINISTRADORES: Usuários padrão do Django (tabela auth_user)
2. FUNCIONÁRIOS: Usuários customizados da empresa (tabela UsuarioEmpresa)

PROBLEMA:
O Django REST Framework espera que request.user seja sempre um objeto do modelo User padrão,
mas nossos funcionários estão em uma tabela customizada (UsuarioEmpresa). 

SOLUÇÃO - USUÁRIO DUMMY:
Criar um objeto User "dummy" (em memória) para funcionários que:
- IMITA a interface do modelo User do Django para compatibilidade
- NÃO É SALVO no banco de dados (objeto temporário)
- CONTÉM dados reais do funcionário vindos do token JWT
- PERMITE que o DRF funcione normalmente com ambos os tipos de usuário

FLUXO:
1. Token JWT é validado → 2. Identifica tipo_usuario → 3. Cria User real ou dummy → 4. DRF funciona normalmente
"""

from django.contrib.auth.models import User
from acesso.models import UsuarioEmpresa
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class CustomJWTAuthentication(JWTAuthentication):
    """
    Authentication backend customizado para funcionar com ambos os tipos de usuário.

    HERDA de JWTAuthentication do SimpleJWT e customiza o método get_user()
    para suportar tanto User padrão quanto UsuarioEmpresa através do conceito de usuário dummy.

    IMPORTANTE: Este backend deve ser configurado no settings.py como primeira opção:
    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'authentication.backends.CustomJWTAuthentication',
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ]
    }
    """

    def get_user(self, validated_token):
        """
        Retorna o usuário baseado no token validado.

        PARA ADMIN: Retorna User real do Django (banco de dados)
        PARA FUNCIONÁRIO: Retorna User dummy com dados do token (memória)

        Args:
            validated_token: Token JWT já validado pelo SimpleJWT

        Returns:
            User: Objeto User do Django (real ou dummy)

        Raises:
            AuthenticationFailed: Se usuário não for encontrado ou token inválido

        EXEMPLO DE USO:
        - Token admin: busca User real do banco → request.user = User.objects.get(id=1)
        - Token funcionário: cria User dummy → request.user = User(id=123, username="joao", ...)
        """
        try:
            # Obtém o tipo de usuário das claims do token
            # Valores possíveis: 'admin' (User padrão) ou 'funcionario' (UsuarioEmpresa)
            tipo_usuario = validated_token.get('tipo_usuario')

            # Roteamento baseado no tipo de usuário
            if tipo_usuario == 'admin':
                # CASO 1: USUÁRIO ADMINISTRADOR (User padrão do Django)
                # Busca o usuário real na tabela auth_user usando ID do token
                return self._get_admin_user(validated_token)

            elif tipo_usuario == 'funcionario':
                # CASO 2: USUÁRIO FUNCIONÁRIO (UsuarioEmpresa customizado)
                # Cria um usuário dummy com os dados do token (não busca no banco)
                return self._create_funcionario_user(validated_token)

            else:
                # Token não contém um tipo de usuário reconhecido
                # Isso pode ocorrer se o token foi gerado por outro sistema ou está corrompido
                raise InvalidToken('Token contém formato inválido - tipo_usuario desconhecido')

        except User.DoesNotExist:
            # Usuário admin não encontrado na tabela auth_user
            # Pode ocorrer se o usuário foi deletado mas o token ainda é válido
            raise AuthenticationFailed('Usuário não encontrado', code='user_not_found')
        except Exception as e:
            # Erro genérico durante a autenticação
            # Logar este erro para debugging em produção
            raise AuthenticationFailed(f'Erro na autenticação: {str(e)}')

    def _get_admin_user(self, validated_token):
        """
        Busca e retorna um usuário ADMINISTRADOR real da tabela auth_user.

        Para administradores, usamos o sistema de autenticação padrão do Django.
        O usuário existe fisicamente na tabela auth_user.

        Args:
            validated_token: Token JWT com claims do administrador

        Returns:
            User: Objeto User real do Django

        NOTA: No token de admin, 'empresa_id' contém na verdade o ID do usuário admin.
        Isso é uma convenção do sistema para manter consistência com funcionários.
        """
        # Tenta obter o ID do usuário da claim 'empresa_id' (nome personalizado do sistema)
        user_id = validated_token.get('empresa_id')

        if user_id:
            # Encontra o usuário real no banco de dados
            # Esta query é necessária para verificar se o usuário ainda existe e está ativo
            return User.objects.get(id=user_id)
        else:
            # Fallback: tenta obter da claim padrão 'user_id'
            # Caso a claim personalizada não esteja presente (compatibilidade)
            user_id = validated_token.get('user_id')
            if not user_id:
                raise AuthenticationFailed('Token não contém identificação do usuário')
            return User.objects.get(id=user_id)

    def _create_funcionario_user(self, validated_token):
        """
        Cria e retorna um usuário DUMMY para funcionários.

        IMPORTANTE: Este é um objeto User em MEMÓRIA, não persistido no banco.
        Contém dados reais do funcionário extraídos do token JWT.

        POR QUE USAR DUMMY?
        - O DRF exige que request.user seja um objeto do tipo User
        - Mas nossos funcionários estão na tabela UsuarioEmpresa
        - Solução: criar um objeto User fake com dados reais do token

        Args:
            validated_token: Token JWT com claims do funcionário

        Returns:
            User: Objeto User dummy com dados do funcionário

        SEGURANÇA: Os dados vêm do token JWT validado, que é cryptographicamente seguro.
        """
        # =========================================================================
        # CRIAÇÃO DO OBJETO USER DUMMY (NÃO PERSISTIDO)
        # =========================================================================

        # Cria uma instância de User NÃO SALVA no banco (apenas em memória)
        # Os dados são extraídos diretamente das claims do token JWT
        user = User(
            # ID do funcionário na tabela UsuarioEmpresa (NÃO é o ID do auth_user)
            # Usado apenas para identificação interna, não para buscar no banco
            id=validated_token.get('funcionario_id'),

            # Dados básicos de autenticação (NECESSÁRIOS para o DRF funcionar)
            username=validated_token.get('username', 'funcionario'),  # Fallback caso não exista
            email=validated_token.get('email', ''),                   # Email pode ser vazio
            first_name=validated_token.get('nome', ''),               # Nome real do funcionário

            # Permissões padrão para funcionários (sempre False por segurança)
            is_staff=False,      # Não tem acesso ao admin Django
            is_superuser=False,  # Não é superusuário

            # Marca como ativo para passar nas verificações de autenticação do DRF
            is_active=True
        )

        # =========================================================================
        # ATRIBUTOS CUSTOMIZADOS ADICIONADOS AO OBJETO USER DUMMY
        # =========================================================================
        # Python permite adicionar atributos dinâmicos a objetos.
        # Estes atributos são transparentes para o DRF mas disponíveis para nossa lógica.

        # Identificação do tipo de usuário (CRUCIAL para o sistema)
        # Usado pelas permissions customizadas para diferenciar admin/funcionário
        user.tipo_usuario = 'funcionario'

        # ID real do funcionário na tabela UsuarioEmpresa
        # Usado para verificações adicionais no banco de dados (ex: se ainda está ativo)
        user.funcionario_id = validated_token.get('funcionario_id')

        # ID da empresa à qual o funcionário pertence
        # Usado para filtrar dados específicos da empresa nas queries
        user.empresa_id = validated_token.get('empresa_id')

        # Cargo/função do funcionário na empresa
        # Pode ser usado para lógicas de autorização baseada em cargos
        user.cargo = validated_token.get('cargo')

        # Nome da empresa (para exibição ou lógicas específicas)
        user.empresa_nome = validated_token.get('empresa_nome')

        # =========================================================================
        # VANTAGENS DESSA ABORDAGEM:
        # =========================================================================
        # 1. COMPATIBILIDADE: O DRF vê um objeto User válido
        # 2. PERFORMANCE: Evita query no banco para funcionários
        # 3. FLEXIBILIDADE: Podemos adicionar quantos atributos precisarmos
        # 4. SEGURANÇA: Dados vêm do token JWT validado

        return user


"""
EXEMPLO DE USO NAS VIEWS:

# Após a autenticação, as views podem diferenciar os tipos de usuário:
class MinhaView(APIView):
    permission_classes = [IsAuthenticatedCustom]
    
    def get(self, request):
        # Verifica se é funcionário através do atributo customizado
        if hasattr(request.user, 'tipo_usuario') and request.user.tipo_usuario == 'funcionario':
            # Acesso aos dados customizados do dummy
            funcionario_id = request.user.funcionario_id
            empresa_id = request.user.empresa_id
            cargo = request.user.cargo
            
            # Lógica específica para funcionários
            return Response({'tipo': 'funcionario', 'cargo': cargo})
        else:
            # Usuário admin padrão (não tem atributo tipo_usuario)
            return Response({'tipo': 'admin', 'username': request.user.username})
"""
