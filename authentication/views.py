from django.db import transaction
from django.core.files.storage import default_storage

from rest_framework.generics import ListAPIView
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import authenticate
from django.conf import settings
from django.core.cache import cache

# Black list tokens httponly
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from datetime import datetime

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

# IMPORTANDO NOSSAS PERMISSIONS E MIXINS
from app.permissions import UsuarioIndependenteOuAdmin
from app.mixins import SystemAccessMixin
from app.utils import utils

from empresa.models import Empresa, Funcionario, ConexaoBanco, HistoricoNSU
from sistema.models import EmpresaSistema

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


# LOGIN CUSTOMIZADO COM HTTPONLY COOKIE
@extend_schema(
    tags=['Autenticação'],
    operation_id="01_login",
    summary='01 Login obter token de acesso',
    description='''
    Realiza login e retorna tokens JWT em cookies HttpOnly.

    **Validações:**
    - Usuário deve ter vínculo ativo com pelo menos uma empresa
    - A empresa deve ter pelo menos um sistema ativo contratado

    **Segurança:**
    - Tokens armazenados em cookies HttpOnly (imunes a XSS)
    - Proteção CSRF com SameSite=Lax
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'username': {'type': 'string', 'description': 'Nome de usuário'},
                'password': {'type': 'string', 'format': 'password', 'description': 'Senha'},
            },
            'required': ['username', 'password']
        }
    },
    responses={
        200: OpenApiResponse(
            description='Login realizado com sucesso',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Exemplo de resposta',
                    value={
                        'message': 'Login realizado com sucesso',
                        'user': {
                            'id': 1,
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(description='Credenciais não fornecidas'),
        401: OpenApiResponse(
            description='Credenciais inválidas',
            examples=[OpenApiExample(
                'Credenciais inválidas',
                value={'detail': 'Unable to log in with provided credentials.'}
            )]
        ),
        403: OpenApiResponse(
            description='Sem acesso a sistemas',
            examples=[OpenApiExample(
                'Sem acesso',
                value={
                    'detail': 'Seu usuário não possui acesso a nenhum sistema ativo.',
                    'code': 'no_active_system'
                }
            )]
        ),
    }
)
class CustomTokenObtainAPIView(APIView):
    """
    View para obtenção de token JWT com validação de vínculo empresarial.
    Retorna os tokens em cookies HttpOnly para maior segurança.
    """
    permission_classes = [AllowAny]

    def _verificar_acesso_sistema(self, user):
        """Verifica se o usuário tem acesso a pelo menos um sistema ativo."""
        if user.is_superuser:
            return True

        # Como dono de empresa
        empresas_dono = Empresa.objects.filter(usuario=user, status='1')
        for empresa in empresas_dono:
            if EmpresaSistema.objects.filter(empresa=empresa, ativo=True).exists():
                return True

        # Como funcionário
        funcionarios = Funcionario.objects.filter(
            user=user,
            status='1',
            empresa__status='1'
        ).select_related('empresa')

        for funcionario in funcionarios:
            if EmpresaSistema.objects.filter(
                empresa=funcionario.empresa,
                ativo=True
            ).exists():
                return True

        return False

    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'detail': 'Must include "username" and "password".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request=request, username=username, password=password)

        if not user:
            return Response(
                {'detail': 'Unable to log in with provided credentials.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Verificar acesso a sistemas ativos
        if not self._verificar_acesso_sistema(user):
            return Response(
                {
                    'detail': 'Seu usuário não possui acesso a nenhum sistema ativo. '
                    'Entre em contato com o administrador para contratar o serviço.',
                    'code': 'no_active_system'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Gerar tokens
        refresh = RefreshToken.for_user(user)

        # Determinar se é HTTPS (para secure flag)
        is_secure = not settings.DEBUG

        # Criar resposta com dados básicos do usuário
        response = Response({
            'message': 'Login realizado com sucesso',
            'user': {
                'id': user.id
            }
        }, status=status.HTTP_200_OK)

        # Configurar HttpOnly Cookie para o access token
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            httponly=True,          # Impede acesso via JavaScript
            secure=is_secure,       # Só envia via HTTPS (False em desenvolvimento)
            samesite='Lax',         # Protege contra CSRF
            max_age=60 * 60 * 24,   # 24 horas
            path='/',
        )

        # Configurar HttpOnly Cookie para o refresh token
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=is_secure,
            samesite='Lax',
            max_age=60 * 60 * 24 * 7,  # 7 dias
            path='/',
        )

        return response


# REFRESH TOKEN COM HTTPONLY COOKIE
@extend_schema(
    tags=['Autenticação'],
    operation_id="02_refresh_token",
    summary='02 Refresh token',
    description='Atualiza o access token usando o refresh token armazenado no cookie HttpOnly.',
    responses={
        200: OpenApiResponse(description='Token atualizado com sucesso'),
        401: OpenApiResponse(description='Refresh token inválido ou expirado')
    }
)
class CustomTokenRefreshAPIView(APIView):
    """
    View para refresh de token JWT.
    O refresh token é lido do cookie HttpOnly.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Pegar refresh token do cookie (não do body)
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token não encontrado.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            is_secure = not settings.DEBUG

            response = Response(
                {'message': 'Token atualizado com sucesso'},
                status=status.HTTP_200_OK
            )

            # Atualizar cookie do access token
            response.set_cookie(
                key='access_token',
                value=new_access_token,
                httponly=True,
                secure=is_secure,
                samesite='Lax',
                max_age=60 * 60 * 24,
                path='/',
            )

            return response

        except Exception:
            return Response(
                {'detail': 'Refresh token inválido ou expirado.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


@extend_schema(
    tags=['Autenticação'],
    operation_id="03_logout",
    summary='03 Logout',
    description='Realiza logout removendo os cookies de autenticação.',
    responses={
        200: OpenApiResponse(description='Logout realizado com sucesso'),
        401: OpenApiResponse(description='Usuário não autenticado')
    }
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        access_token = request.COOKIES.get('access_token')
        refresh_token = request.COOKIES.get('refresh_token')

        # print(f"Access token: {access_token[:50] if access_token else 'None'}...")
        # print(f"Refresh token: {refresh_token[:50] if refresh_token else 'None'}...")

        # Invalidar access token
        if access_token:
            try:
                # Decodificar o token para obter o jti
                token = AccessToken(access_token)
                jti = token['jti']

                # Verificar se já existe um OutstandingToken para este jti
                outstanding_token, created = OutstandingToken.objects.get_or_create(
                    jti=jti,
                    defaults={
                        'token': access_token,
                        'user': request.user,
                        'expires_at': datetime.fromtimestamp(token['exp']),
                    }
                )

                # Adicionar à blacklist se não estiver já
                if not BlacklistedToken.objects.filter(token=outstanding_token).exists():
                    BlacklistedToken.objects.create(token=outstanding_token)
                    # print(f"Access token {jti} blacklisted")
                else:
                    # print(f"Access token {jti} já está na blacklist")
                    pass

            except Exception:
                # print(f"❌ Erro ao invalidar access token: {e}")
                pass

        # Invalidar refresh token
        if refresh_token:
            try:
                # Decodificar o token para obter o jti
                token = RefreshToken(refresh_token)
                jti = token['jti']

                # Verificar se já existe um OutstandingToken para este jti
                outstanding_token, created = OutstandingToken.objects.get_or_create(
                    jti=jti,
                    defaults={
                        'token': refresh_token,
                        'user': request.user,
                        'expires_at': datetime.fromtimestamp(token['exp']),
                    }
                )

                # Adicionar à blacklist se não estiver já
                if not BlacklistedToken.objects.filter(token=outstanding_token).exists():
                    BlacklistedToken.objects.create(token=outstanding_token)
                    # print(f"Refresh token {jti} blacklisted")
                else:
                    # print(f"Refresh token {jti} já está na blacklist")
                    pass

            except Exception:
                # print(f"Erro ao invalidar refresh token: {e}")
                pass

        response = Response(
            {'message': 'Logout realizado com sucesso'},
            status=status.HTTP_200_OK
        )

        # Limpar cookies
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')

        return response


# USUÁRIOS
@extend_schema_view(
    post=extend_schema(
        tags=['Usuários'],
        operation_id="01_criar_novo_usuario",
        summary='01 Criar novo usuário',
        description='Cria uma nova conta de usuário no sistema.',
        auth=[],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Nome de usuário único'},
                    'email': {'type': 'string', 'format': 'email', 'description': 'E-mail do usuário'},
                    'password': {'type': 'string', 'format': 'password', 'description': 'Senha do usuário'},
                },
                'required': ['username', 'email', 'password']
            }
        },
        responses={
            201: OpenApiResponse(
                description='Usuário criado com sucesso',
                response=OpenApiTypes.OBJECT
            ),
            400: OpenApiResponse(description='Dados inválidos')
        }
    )
)
class UserProfileCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return Response(
                {"error": f"Os campos obrigatórios estão faltando: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=data['email']).exists():
            return Response({"email": "Este e-mail já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=data['username']).exists():
            return Response({"username": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }, status=status.HTTP_201_CREATED)


@extend_schema_view(
    post=extend_schema(
        tags=['Usuários'],
        operation_id="02_solicitar_redefinicao_senha",
        summary='02 Solicitar redefinição de senha',
        description='Solicita o envio de um e-mail com link para redefinição de senha.',
        auth=[],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'description': 'E-mail cadastrado'}
                },
                'required': ['email']
            }
        },
        responses={
            200: OpenApiResponse(description='E-mail enviado com sucesso'),
            400: OpenApiResponse(description='E-mail não encontrado')
        }
    )
)
class PasswordResetRequestAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'E-mail não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        email_subject = 'Redefinição de Senha'
        email_message = render_to_string('password_reset_email.txt', {
            'user': user,
            'uid': uid,
            'token': token,
            'url_end': settings.CURRENT_URL_FRONTEND_PASSWORD_REQUEST
        })
        send_mail(email_subject, email_message, 'noreply@example.com', [user.email])

        return Response({
            'message': 'E-mail de redefinição de senha enviado. Verifique sua caixa de entrada.'
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=['Usuários'],
        operation_id="03_confirmar_redefinicao_senha",
        summary='03 Confirmar redefinição de senha',
        description='Confirma a redefinição de senha usando o token recebido por e-mail.',
        auth=[],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'uidb64': {'type': 'string', 'description': 'UID codificado em base64 do usuário'},
                    'token': {'type': 'string', 'description': 'Token de redefinição'},
                    'new_password': {'type': 'string', 'format': 'password', 'description': 'Nova senha'}
                },
                'required': ['uidb64', 'token', 'new_password']
            }
        },
        responses={
            200: OpenApiResponse(description='Senha redefinida com sucesso'),
            400: OpenApiResponse(description='Dados inválidos')
        }
    )
)
class PasswordResetConfirmAPIView(APIView):
    def post(self, request):
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')

        if not uidb64:
            return Response({'error': 'UID é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        if not token:
            return Response({'error': 'Token é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Link de redefinição inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'error': 'Senha nova não fornecida.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Senha redefinida com sucesso!'}, status=status.HTTP_200_OK)


# PERFIL DO USUÁRIO (usa SystemAccessMixin)
@extend_schema_view(
    get=extend_schema(
        tags=['Perfil'],
        operation_id="01_obter_perfil",
        summary='01 Obter perfil do usuário',
        description='Retorna os dados do perfil do usuário autenticado.',
        responses={
            200: OpenApiResponse(description='Dados do perfil obtidos com sucesso'),
            401: OpenApiResponse(description='Usuário não autenticado')
        }
    )
)
class UserProfileView(SystemAccessMixin, APIView):
    """
    Retorna o perfil do usuário com suas empresas e permissões.
    O SystemAccessMixin garante que só retorne dados do sistema atual.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        system_id = getattr(request, 'sistema_id', None)
        system_name = getattr(request, 'sistema_nome', None)

        # Empresas onde o usuário é dono
        empresas_como_dono = Empresa.objects.filter(
            usuario=user,
            status='1'
        )

        empresas_data = []
        funcionario_empresas_ids = set()

        for empresa in empresas_como_dono:
            if system_id and empresa.sistema_id != system_id:
                continue

            funcionario = Funcionario.objects.filter(
                user=user,
                empresa=empresa,
                status='1'
            ).first()

            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            sistemas_list = []
            for sys in sistemas_ativos:
                sistemas_list.append({
                    'id': sys.sistema.id,
                    'nome': sys.sistema.nome,
                    'max_funcionarios': sys.max_funcionarios_registros,
                    'criar_banco': sys.criar_banco,
                })

            empresas_data.append({
                'id': empresa.id,
                'razao_social': empresa.razao_social,
                'documento': empresa.documento,
                'uf': empresa.uf,
                'tipo': 'MATRIZ' if not empresa.matriz_filial else 'FILIAL',
                'status': empresa.status,
                'sistemas': sistemas_list,
                'role': funcionario.role if funcionario else 'admin',
                'is_owner': True,
            })
            funcionario_empresas_ids.add(empresa.id)

        # Vínculos como funcionário (não dono)
        funcionarios = Funcionario.objects.filter(
            user=user,
            status='1'
        ).exclude(
            empresa_id__in=funcionario_empresas_ids
        ).select_related('empresa', 'empresa__sistema')

        for funcionario in funcionarios:
            empresa = funcionario.empresa
            if empresa.status != '1':
                continue

            if system_id and empresa.sistema_id != system_id:
                continue

            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            sistemas_list = []
            for sys in sistemas_ativos:
                sistemas_list.append({
                    'id': sys.sistema.id,
                    'nome': sys.sistema.nome,
                    'max_funcionarios': sys.max_funcionarios_registros,
                    'criar_banco': sys.criar_banco,
                })

            empresas_data.append({
                'id': empresa.id,
                'razao_social': empresa.razao_social,
                'documento': empresa.documento,
                'uf': empresa.uf,
                'tipo': 'MATRIZ' if not empresa.matriz_filial else 'FILIAL',
                'status': empresa.status,
                'sistemas': sistemas_list,
                'role': funcionario.role,
                'is_owner': False,
            })

        # ==============================================================
        # DEFINIÇÃO DO ADMIN (flag para front) E ROLE PRINCIPAL
        # ==============================================================
        # A flag 'admin' no front deve ser true APENAS para superuser
        is_superuser = user.is_superuser
        is_staff = user.is_staff

        # Para front, 'admin' é apenas superuser (acesso total ao sistema)
        admin_flag = is_superuser

        # Determinar a role principal para navegação
        # Prioridade: system_admin (superuser) > cargos staff > cargos cliente
        role_priority = {
            'system_admin': 0,
            'auditor': 1,
            'administrativo': 2,
            'suporte': 3,
            'estagiario': 4,
            'cliente_admin': 5,      # dono de empresa (admin da empresa)
            'cliente_externo': 6,    # funcionário comum ou cliente externo
        }

        primary_role = None
        best_priority = 99

        # 1. Se superuser, role = 'system_admin'
        if is_superuser:
            primary_role = 'system_admin'
            best_priority = role_priority['system_admin']

        # 2. Se staff, buscar cargo com maior prioridade (menor número)
        if is_staff and not is_superuser:
            for empresa in empresas_data:
                cargo = empresa.get('role')
                if cargo and cargo in role_priority:
                    priority = role_priority[cargo]
                    if priority < best_priority:
                        best_priority = priority
                        primary_role = cargo

        # 3. Se não staff nem superuser, mas é dono de alguma empresa (is_owner)
        if not is_superuser and not is_staff:
            # Verificar se é dono de alguma empresa (admin da empresa)
            is_company_admin = any(emp.get('is_owner') for emp in empresas_data)
            if is_company_admin:
                primary_role = 'cliente_admin'
                best_priority = role_priority['cliente_admin']
            else:
                # Caso contrário, pegar o primeiro cargo disponível ou 'cliente_externo'
                for empresa in empresas_data:
                    cargo = empresa.get('role')
                    if cargo and cargo in role_priority:
                        priority = role_priority[cargo]
                        if priority < best_priority:
                            best_priority = priority
                            primary_role = cargo

        # Fallback
        if not primary_role:
            primary_role = 'cliente_externo'

        # Construir resposta
        response_data = {
            'id': user.id,
            'username': user.username,
            'admin': admin_flag,                # APENAS superuser
            'is_superuser': is_superuser,
            'is_staff': is_staff,
            'status': user.is_active,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': primary_role,               # role principal para navegação
            'empresas': empresas_data,
            'has_empresas': len(empresas_data) > 0,
        }

        if system_id:
            response_data['current_system'] = {
                'id': system_id,
                'name': system_name
            }

        if not empresas_data:
            response_data['message'] = 'Usuário não possui vínculo com nenhuma empresa ativa.'

        return Response(response_data)


@extend_schema_view(
    put=extend_schema(
        tags=['Perfil'],
        operation_id="02_atualizar_perfil",
        summary='02 Atualizar perfil do usuário',
        description='Atualiza os dados do perfil do usuário.',
        parameters=[
            OpenApiParameter(name='pk', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID do usuário')
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Novo nome de usuário'},
                    'email': {'type': 'string', 'format': 'email', 'description': 'Novo e-mail'},
                    'first_name': {'type': 'string', 'description': 'Novo primeiro nome'},
                    'last_name': {'type': 'string', 'description': 'Novo sobrenome'},
                    'password': {'type': 'string', 'format': 'password', 'description': 'Nova senha'},
                }
            }
        },
        responses={
            200: OpenApiResponse(description='Perfil atualizado com sucesso'),
            400: OpenApiResponse(description='Dados inválidos'),
            403: OpenApiResponse(description='Permissão negada')
        }
    )
)
class UserUpdateProfile(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        if user.id != pk:
            return Response({"error": "Você não tem permissão para atualizar este perfil."}, status=status.HTTP_403_FORBIDDEN)

        is_superuser = user.is_superuser
        data = request.data

        if 'username' in data:
            if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response({"error": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)
            user.username = data['username']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.set_password(data['password'])

        if 'is_active' in data and is_superuser:
            user.is_active = data['is_active']
        if 'is_staff' in data and is_superuser:
            user.is_staff = data['is_staff']

        user.save()

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
        }, status=status.HTTP_200_OK)


# PERMISSÕES DO USUÁRIO (usa cache para performance)
@extend_schema(
    tags=['Perfil'],
    operation_id="03_obter_permissoes",
    summary='03 Obter permissões do usuário',
    description='Retorna as permissões do usuário para o frontend.',
    responses={
        200: OpenApiResponse(description='Permissões obtidas com sucesso'),
        401: OpenApiResponse(description='Usuário não autenticado')
    }
)
class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        cache_key = f"user_permissions_{user.id}"
        cached_result = cache.get(cache_key)

        if cached_result:
            return Response(cached_result)

        sistemas_acesso = []

        # Como dono
        empresas_dono = Empresa.objects.filter(usuario=user, status='1')
        for empresa in empresas_dono:
            empresa_sistemas = EmpresaSistema.objects.filter(empresa=empresa, ativo=True).select_related('sistema')
            for es in empresa_sistemas:
                sistemas_acesso.append({
                    'sistema_id': es.sistema.id,
                    'sistema_nome': es.sistema.nome,
                    'empresa_id': empresa.id,
                    'empresa_nome': empresa.razao_social,
                    'role': 'admin'
                })

        # Como funcionário
        funcionarios = Funcionario.objects.filter(user=user, status='1', empresa__status='1').select_related('empresa')
        for func in funcionarios:
            empresa = func.empresa
            empresa_sistemas = EmpresaSistema.objects.filter(empresa=empresa, ativo=True).select_related('sistema')
            for es in empresa_sistemas:
                sistemas_acesso.append({
                    'sistema_id': es.sistema.id,
                    'sistema_nome': es.sistema.nome,
                    'empresa_id': empresa.id,
                    'empresa_nome': empresa.razao_social,
                    'role': func.role
                })

        # Remover duplicatas (manter o de maior prioridade)
        role_priority = {'admin': 1, 'auditor': 2, 'administrativo': 3, 'suporte': 4, 'estagiario': 5, 'cliente_externo': 6}
        sistemas_dict = {}

        for sistema in sistemas_acesso:
            sistema_id = sistema['sistema_id']
            if sistema_id not in sistemas_dict:
                sistemas_dict[sistema_id] = sistema
            else:
                existing_priority = role_priority.get(sistemas_dict[sistema_id]['role'], 99)
                new_priority = role_priority.get(sistema['role'], 99)
                if new_priority < existing_priority:
                    sistemas_dict[sistema_id] = sistema

        result = {
            'user_id': user.id,
            'username': user.username,
            'sistemas': list(sistemas_dict.values()),
            'has_any_access': len(sistemas_dict) > 0
        }

        cache.set(cache_key, result, 3600)

        return Response(result)


# LISTA DE USUÁRIOS (para admin)
@extend_schema_view(
    get=extend_schema(
        exclude=True
    ),
    post=extend_schema(
        exclude=True
    )
)
class UsersList(ListAPIView):
    permission_classes = [
        IsAuthenticated,
        # IsAdminUser,
        UsuarioIndependenteOuAdmin
    ]
    pagination_class = utils.CustomPageSizePagination

    def initial(self, request, *args, **kwargs):
        paginate = request.query_params.get("disablePaginate", "false").lower()
        if paginate in ["true", "1", "yes"]:
            self.pagination_class = None
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return User.objects.all().order_by("id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        users = page if page is not None else queryset

        user_ids = [user.id for user in users]
        funcionarios = Funcionario.objects.filter(user_id__in=user_ids).select_related('empresa')

        funcionarios_dict = {}
        for funcionario in funcionarios:
            funcionarios_dict.setdefault(funcionario.user_id, []).append(funcionario)

        serializer_data = []
        for user in users:
            empresas_data = []
            for funcionario in funcionarios_dict.get(user.id, []):
                empresa = funcionario.empresa
                empresas_data.append({
                    'role': funcionario.role,
                    'empresa_id': empresa.id,
                    'razao_social': empresa.razao_social,
                    'documento': empresa.documento,
                    'is_branch': empresa.matriz_filial_id is not None,
                })

            serializer_data.append({
                'id': user.id,
                'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                'email': user.email,
                'admin': user.is_superuser,
                'status': user.is_active,
                'created_at': user.date_joined,
                'empresas': empresas_data,
            })

        if page is not None:
            return self.get_paginated_response(serializer_data)
        return Response(serializer_data)


@extend_schema_view(
    get=extend_schema(
        tags=['Usuários'],
        operation_id="04_obter_usuario_por_id",
        summary='04 Obter usuário por ID (Admin)',
        description='Retorna os dados completos de um usuário específico. Apenas administradores podem acessar.',
        parameters=[
            OpenApiParameter(name='pk', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID do usuário')
        ],
        responses={
            200: OpenApiResponse(description='Dados do usuário obtidos com sucesso'),
            403: OpenApiResponse(description='Permissão negada - apenas administradores'),
            404: OpenApiResponse(description='Usuário não encontrado')
        }
    )
)
class UserDetailAdminView(APIView):
    """
    View para administrador buscar qualquer usuário por ID.
    Apenas superusuários podem acessar.
    """
    permission_classes = [
        IsAuthenticated,
        # IsAdminUser,
        UsuarioIndependenteOuAdmin
    ]

    def get(self, request, pk):
        # Verifica se o usuário logado é superusuário
        if not request.user.is_superuser:
            return Response(
                {"error": "Apenas administradores podem acessar esta funcionalidade."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Busca empresas vinculadas ao usuário
        empresas_data = []

        # Como dono de empresa
        empresas_dono = Empresa.objects.filter(usuario=user, status='1')
        for empresa in empresas_dono:
            funcionario = Funcionario.objects.filter(
                user=user,
                empresa=empresa,
                status='1'
            ).first()

            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            sistemas_list = []
            for sys in sistemas_ativos:
                sistemas_list.append({
                    'id': sys.sistema.id,
                    'nome': sys.sistema.nome,
                    'max_funcionarios': sys.max_funcionarios_registros,
                    'criar_banco': sys.criar_banco,
                })

            empresas_data.append({
                'id': empresa.id,
                'razao_social': empresa.razao_social,
                'documento': empresa.documento,
                'uf': empresa.uf,
                'tipo': 'MATRIZ' if not empresa.matriz_filial else 'FILIAL',
                'status': empresa.status,
                'sistemas': sistemas_list,
                'role': funcionario.role if funcionario else 'admin',
                'is_owner': True,
            })

        # Como funcionário
        funcionarios_ids = [emp['id'] for emp in empresas_data]
        funcionarios = Funcionario.objects.filter(
            user=user,
            status='1'
        ).exclude(
            empresa_id__in=funcionarios_ids
        ).select_related('empresa')

        for funcionario in funcionarios:
            empresa = funcionario.empresa
            if empresa.status != '1':
                continue

            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            sistemas_list = []
            for sys in sistemas_ativos:
                sistemas_list.append({
                    'id': sys.sistema.id,
                    'nome': sys.sistema.nome,
                    'max_funcionarios': sys.max_funcionarios_registros,
                    'criar_banco': sys.criar_banco,
                })

            empresas_data.append({
                'id': empresa.id,
                'razao_social': empresa.razao_social,
                'documento': empresa.documento,
                'uf': empresa.uf,
                'tipo': 'MATRIZ' if not empresa.matriz_filial else 'FILIAL',
                'status': empresa.status,
                'sistemas': sistemas_list,
                'role': funcionario.role,
                'is_owner': False,
            })

        # Determina o role global
        role_priority = {
            'admin': 1,
            'auditor': 2,
            'administrativo': 3,
            'suporte': 4,
            'estagiario': 5,
            'cliente_externo': 6,
            'secretaria': 7,
            'financeiro': 8,
            'auxiliar_geral': 9
        }
        global_role = None
        global_role_priority = 99

        for empresa_data in empresas_data:
            role = empresa_data.get('role')
            if role and role in role_priority:
                priority = role_priority[role]
                if priority < global_role_priority:
                    global_role_priority = priority
                    global_role = role

        if user.is_superuser or user.is_staff:
            global_role = 'admin'

        if not global_role and empresas_data:
            global_role = empresas_data[0].get('role', 'cliente_externo')

        if not global_role:
            global_role = 'sem_vínculo'

        response_data = {
            'id': user.id,
            'username': user.username,
            'admin': user.is_staff or user.is_superuser,
            'status': user.is_active,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': global_role,
            'empresas': empresas_data,
            'has_empresas': len(empresas_data) > 0,
        }

        return Response(response_data)


@extend_schema_view(
    post=extend_schema(
        tags=['Usuários - Admin'],
        operation_id="05_criar_usuario_admin",
        summary='05 Criar usuário (Admin)',
        description='Cria um novo usuário. Apenas super administradores podem criar outros super administradores.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'email': {'type': 'string', 'format': 'email'},
                    'password': {'type': 'string', 'format': 'password'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'is_active': {'type': 'boolean'},
                    'is_staff': {'type': 'boolean'},
                    'is_superuser': {'type': 'boolean'},
                },
                'required': ['username', 'email', 'password']
            }
        },
        responses={
            201: OpenApiResponse(description='Usuário criado com sucesso'),
            400: OpenApiResponse(description='Dados inválidos'),
            403: OpenApiResponse(description='Permissão negada')
        }
    ),
    put=extend_schema(
        tags=['Usuários - Admin'],
        operation_id="06_atualizar_usuario_admin",
        summary='06 Atualizar usuário (Admin)',
        description='Atualiza um usuário existente. Apenas super administradores podem modificar permissões de admin/superuser.',
        parameters=[
            OpenApiParameter(name='pk', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID do usuário')
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'email': {'type': 'string', 'format': 'email'},
                    'password': {'type': 'string', 'format': 'password'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'is_active': {'type': 'boolean'},
                    'is_staff': {'type': 'boolean'},
                    'is_superuser': {'type': 'boolean'},
                }
            }
        },
        responses={
            200: OpenApiResponse(description='Usuário atualizado com sucesso'),
            400: OpenApiResponse(description='Dados inválidos'),
            403: OpenApiResponse(description='Permissão negada'),
            404: OpenApiResponse(description='Usuário não encontrado')
        }
    )
)
class UserAdminManageView(APIView):
    """
    View para administrador gerenciar usuários (criar/atualizar).
    Apenas superusuários podem acessar.
    """
    permission_classes = [
        IsAuthenticated,
        # IsAdminUser,
        UsuarioIndependenteOuAdmin
    ]

    def _verificar_permissao_admin(self, request, target_user=None):
        """Verifica permissões para operações de admin"""
        current_user = request.user

        # Apenas superusuários podem acessar esta view
        if not current_user.is_superuser:
            return False, "Apenas super administradores podem gerenciar usuários."

        # Se estiver atualizando um usuário que não é ele mesmo
        if target_user and target_user.id != current_user.id:
            return True, None

        return True, None

    def post(self, request):
        """Criar novo usuário"""
        # Verificar permissão
        has_permission, error_msg = self._verificar_permissao_admin(request)
        if not has_permission:
            return Response({"error": error_msg}, status=status.HTTP_403_FORBIDDEN)

        data = request.data

        # Validações básicas
        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response(
                {"error": f"Campos obrigatórios faltando: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar duplicatas
        if User.objects.filter(username=data['username']).exists():
            return Response({"error": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=data['email']).exists():
            return Response({"error": "Este e-mail já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        # Apenas superusuário pode criar outro superusuário
        is_superuser = data.get('is_superuser', False)
        if is_superuser and not request.user.is_superuser:
            return Response({"error": "Apenas super administradores podem criar super usuários."}, status=status.HTTP_403_FORBIDDEN)

        # Criar usuário
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            is_active=data.get('is_active', True),
        )

        # Definir permissões de staff/superuser (apenas se for superusuário logado)
        if request.user.is_superuser:
            user.is_staff = data.get('is_staff', False)
            user.is_superuser = is_superuser
            user.save()

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        """Atualizar usuário existente"""
        # Verificar permissão
        has_permission, error_msg = self._verificar_permissao_admin(request)
        if not has_permission:
            return Response({"error": error_msg}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        current_user = request.user

        # Proteção: não permitir que um usuário não-superuser remova privilégios de superuser
        if user.is_superuser and not current_user.is_superuser:
            return Response({"error": "Apenas super administradores podem modificar super usuários."}, status=status.HTTP_403_FORBIDDEN)

        # Atualizar campos básicos
        if 'username' in data:
            if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response({"error": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)
            user.username = data['username']

        if 'email' in data:
            if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response({"error": "Este e-mail já está em uso."}, status=status.HTTP_400_BAD_REQUEST)
            user.email = data['email']

        if 'first_name' in data:
            user.first_name = data['first_name']

        if 'last_name' in data:
            user.last_name = data['last_name']

        if 'password' in data and data['password']:
            user.set_password(data['password'])

        if 'is_active' in data:
            user.is_active = data['is_active']

        # Atualizar permissões (apenas superusuário pode)
        if current_user.is_superuser and current_user.id != user.id:
            if 'is_staff' in data:
                user.is_staff = data['is_staff']
            if 'is_superuser' in data:
                # Não permitir remover superuser de si mesmo
                if user.id == current_user.id and not data['is_superuser']:
                    return Response({"error": "Você não pode remover seus próprios privilégios de super usuário."}, status=status.HTTP_403_FORBIDDEN)
                user.is_superuser = data['is_superuser']

        user.save()

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    delete=extend_schema(
        tags=['Usuários - Admin'],
        operation_id="07_deletar_usuario_admin",
        summary='07 Deletar usuário (Admin)',
        description='''
        Deleta um usuário do sistema. Apenas super administradores podem deletar usuários.

        **O que é removido:**
        - Vínculos como funcionário de empresas
        - Vínculos como dono de empresas (as empresas são deletadas com CASCADE)
        - Conexões com banco de dados
        - Certificados digitais
        - Todos os dados relacionados

        **Importante:** Esta ação é irreversível!
        ''',
        parameters=[
            OpenApiParameter(name='pk', type=OpenApiTypes.INT, location=OpenApiParameter.PATH, description='ID do usuário')
        ],
        responses={
            200: OpenApiResponse(description='Usuário deletado com sucesso'),
            403: OpenApiResponse(description='Permissão negada - apenas administradores'),
            404: OpenApiResponse(description='Usuário não encontrado')
        }
    )
)
class UserAdminDeleteView(APIView):
    """
    View para administrador deletar qualquer usuário.
    Remove todos os vínculos e dados relacionados.
    Apenas superusuários podem acessar.
    """
    permission_classes = [
        IsAuthenticated,
        # IsAdminUser,
    ]

    def delete(self, request, pk):
        # Verifica se o usuário logado é superusuário
        if not request.user.is_superuser:
            return Response(
                {"error": "Apenas super administradores podem deletar usuários."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Não permitir deletar a si mesmo
        if user.id == request.user.id:
            return Response(
                {"error": "Você não pode deletar sua própria conta."},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            resultado = {
                'user_id': user.id,
                'username': user.username,
                'acoes': []
            }

            # 1. Busca empresas onde o usuário é dono
            empresas_dono = Empresa.objects.filter(usuario=user)

            for empresa in empresas_dono:
                # Remove arquivo de certificado
                if empresa.file and empresa.file.name:
                    try:
                        if default_storage.exists(empresa.file.name):
                            default_storage.delete(empresa.file.name)
                            resultado['acoes'].append(f"Arquivo removido: {empresa.file.name}")
                    except Exception as e:
                        resultado['acoes'].append(f"Erro ao remover arquivo: {str(e)}")

                # Remove conexão com banco
                ConexaoBanco.objects.filter(empresa=empresa).delete()

                # Remove vínculos com sistemas
                EmpresaSistema.objects.filter(empresa=empresa).delete()

                # Remove histórico NSU
                HistoricoNSU.objects.filter(empresa=empresa).delete()

                # Remove funcionários da empresa (exceto o dono)
                for func in Funcionario.objects.filter(empresa=empresa).exclude(user=user):
                    if func.user.is_active:
                        func.user.is_active = False
                        func.user.save()
                    func.delete()

                resultado['acoes'].append(f"Empresa '{empresa.razao_social}' e seus dados removidos")
                empresa.delete()

            # 2. Remove vínculos como funcionário de outras empresas
            funcionarios = Funcionario.objects.filter(user=user)
            for func in funcionarios:
                empresa = func.empresa
                resultado['acoes'].append(f"Removido vínculo como {func.role} da empresa '{empresa.razao_social}'")
                func.delete()

            # 3. Remove tokens do usuário (blacklist)
            OutstandingToken.objects.filter(user=user).delete()

            # 4. Por fim, deleta o usuário
            user.delete()
            resultado['acoes'].append("Usuário deletado do sistema")
            resultado['success'] = True
            resultado['message'] = f"Usuário '{resultado['username']}' foi deletado com sucesso."

            return Response(resultado, status=status.HTTP_200_OK)
