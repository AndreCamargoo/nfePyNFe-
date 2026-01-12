from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from empresa.models import Empresa, Funcionario


@extend_schema_view(
    post=extend_schema(
        tags=['Autenticação'],
        operation_id="01_obter_token_acesso",
        summary='01 Obter token de acesso',
        description='Retorna um par de tokens (access e refresh) para autenticação JWT.',
        request={
            'application/x-www-form-urlencoded': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Nome de usuário'},
                    'password': {'type': 'string', 'format': 'password', 'description': 'Senha do usuário'},
                },
                'required': ['username', 'password']
            }
        },
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Tokens gerados com sucesso',
                examples=[
                    OpenApiExample(
                        'Exemplo de resposta',
                        value={
                            'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                            'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Credenciais inválidas',
                examples=[
                    OpenApiExample(
                        'Credenciais inválidas',
                        value={
                            'detail': 'No active account found with the given credentials'
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    'username': 'usuario123',
                    'password': 'senha123'
                },
                media_type='application/x-www-form-urlencoded'
            )
        ]
    )
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass


@extend_schema_view(
    post=extend_schema(
        tags=['Autenticação'],
        operation_id="02_atualizar_token_acesso",
        summary='02 Atualizar token de acesso',
        description='Usa o token de refresh para obter um novo token de acesso.',
        request={
            'application/x-www-form-urlencoded': {
                'type': 'object',
                'properties': {
                    'refresh': {'type': 'string', 'description': 'Token de refresh'},
                },
                'required': ['refresh']
            }
        },
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Token atualizado com sucesso',
                examples=[
                    OpenApiExample(
                        'Exemplo de resposta',
                        value={
                            'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Token de refresh inválido ou expirado',
                examples=[
                    OpenApiExample(
                        'Token inválido',
                        value={
                            'detail': 'Token is invalid or expired',
                            'code': 'token_not_valid'
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                },
                media_type='application/x-www-form-urlencoded'
            )
        ]
    )
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema_view(
    post=extend_schema(
        tags=['Autenticação'],
        operation_id="03_verificar_token_acesso",
        summary='03 Verificar token',
        description='Verifica se um token (access ou refresh) é válido.',
        request={
            'application/x-www-form-urlencoded': {
                'type': 'object',
                'properties': {
                    'token': {'type': 'string', 'description': 'Token a ser verificado'},
                },
                'required': ['token']
            }
        },
        responses={
            200: OpenApiResponse(
                description='Token válido',
                examples=[
                    OpenApiExample(
                        'Resposta de sucesso',
                        value={}
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Token inválido',
                examples=[
                    OpenApiExample(
                        'Token inválido',
                        value={
                            'detail': 'Token is invalid or expired',
                            'code': 'token_not_valid'
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    'token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                },
                media_type='application/x-www-form-urlencoded'
            )
        ]
    )
)
class CustomTokenVerifyView(TokenVerifyView):
    pass


@extend_schema_view(
    post=extend_schema(
        tags=['Autenticação'],
        operation_id="04_criar_novo_usuario",
        summary='04 Criar novo usuário',
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
                response=OpenApiTypes.OBJECT,
                description='Usuário criado com sucesso',
                examples=[
                    OpenApiExample(
                        'Exemplo de resposta',
                        value={
                            'id': 1,
                            'username': 'usuario123',
                            'email': 'usuario@example.com'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Dados inválidos ou campos faltando',
                examples=[
                    OpenApiExample(
                        'Campos faltando',
                        value={'error': 'Os campos obrigatórios estão faltando: username, email'}
                    ),
                    OpenApiExample(
                        'E-mail em uso',
                        value={'error': 'Este e-mail já está em uso.'}
                    ),
                    OpenApiExample(
                        'Username em uso',
                        value={'error': 'Este nome de usuário já está em uso.'}
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    'username': 'novousuario',
                    'email': 'novo@example.com',
                    'password': 'senhasegura123'
                }
            )
        ]
    )
)
class UserProfileCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validações obrigatórias
        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return Response(
                {"error": f"Os campos obrigatórios estão faltando: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se o e-mail já está em uso
        if User.objects.filter(email=data['email']).exists():
            return Response({"email": "Este e-mail já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        # Verifica se o username já está em uso
        if User.objects.filter(username=data['username']).exists():
            return Response({"username": "Este nome de usuário já está em uso."}, status=status.HTTP_400_BAD_REQUEST)

        # Criação do usuário
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
        tags=['Autenticação'],
        operation_id="05_solicitar_redefinicao_senha",
        summary='05 Solicitar redefinição de senha',
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
            200: OpenApiResponse(
                description='E-mail enviado com sucesso',
                examples=[
                    OpenApiExample(
                        'Resposta de sucesso',
                        value={
                            'message': 'E-mail de redefinição de senha enviado. Verifique sua caixa de entrada.'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='E-mail não encontrado',
                examples=[
                    OpenApiExample(
                        'E-mail não cadastrado',
                        value={'error': 'E-mail não encontrado.'}
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={'email': 'usuario@example.com'}
            )
        ]
    )
)
class PasswordResetRequestAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')

        # Verifica se o e-mail existe no banco de dados
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'E-mail não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cria o token de redefinição de senha
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Envia o e-mail de notificação ao usuário
        email_subject = 'Redefinição de Senha'
        email_message = render_to_string('password_reset_email.txt', {
            'user': user,
            'uid': uid,
            'token': token,
            'url_end': settings.CURRENT_URL_FRONTEND_PASSWORD_REQUEST
        })
        send_mail(email_subject, email_message, 'noreply@example.com', [user.email])

        # Retorna apenas uma confirmação de que o e-mail foi enviado
        return Response({
            'message': 'E-mail de redefinição de senha enviado. Verifique sua caixa de entrada.'
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=['Autenticação'],
        operation_id="06_confirmar_redefinicao_senha",
        summary='06 Confirmar redefinição de senha',
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
            200: OpenApiResponse(
                description='Senha redefinida com sucesso',
                examples=[
                    OpenApiExample(
                        'Resposta de sucesso',
                        value={'message': 'Senha redefinida com sucesso!'}
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Dados inválidos',
                examples=[
                    OpenApiExample(
                        'UID ou token faltando',
                        value={'error': 'UID é obrigatório.'}
                    ),
                    OpenApiExample(
                        'Token inválido',
                        value={'error': 'Link de redefinição inválido ou expirado.'}
                    ),
                    OpenApiExample(
                        'Senha não fornecida',
                        value={'error': 'Senha nova não fornecida.'}
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    'uidb64': 'MQ',
                    'token': 'abc123def456',
                    'new_password': 'novasenha123'
                }
            )
        ]
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

        # Decodifica o uid para obter o ID do usuário
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))  # Corrigido aqui
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Link de redefinição inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verifica se o token é válido
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Token inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Atualiza a senha
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'error': 'Senha nova não fornecida.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Senha redefinida com sucesso!'}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=['Perfil do Usuário'],
        operation_id="01_obter_perfil",
        summary='01 Obter perfil do usuário',
        description='Retorna os dados do perfil do usuário autenticado.',
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Dados do perfil obtidos com sucesso',
                examples=[
                    OpenApiExample(
                        'Exemplo de resposta',
                        value={
                            'id': 1,
                            'username': 'usuario123',
                            'email': 'usuario@example.com',
                            'first_name': 'João',
                            'last_name': 'Silva'
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description='Usuário não autenticado'
            )
        }
    )
)
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        empresas = Empresa.objects.filter(usuario=user).select_related('sistema')

        empresas_data = []
        for empresa in empresas:
            empresas_data.append({
                'id': empresa.id,
                'razao_social': empresa.razao_social,
                'documento': empresa.documento,
                'sistema': {
                    'id': empresa.sistema.id if empresa.sistema else None,
                    'nome': empresa.sistema.nome if empresa.sistema else None,
                }
            })

        return Response({
            'id': user.id,
            'username': user.username,
            'admin': user.is_staff,
            'status': user.is_active,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'empresas': empresas_data,
        })


@extend_schema_view(
    put=extend_schema(
        tags=['Perfil do Usuário'],
        operation_id="02_atualizar_perfil",
        summary='02 Atualizar perfil do usuário',
        description='Atualiza os dados do perfil do usuário.',
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID do usuário a ser atualizado'
            )
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
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Perfil atualizado com sucesso',
                examples=[
                    OpenApiExample(
                        'Exemplo de resposta',
                        value={
                            'id': 1,
                            'username': 'usuario123',
                            'email': 'usuario@example.com',
                            'first_name': 'João',
                            'last_name': 'Silva',
                            'is_active': True,
                            'is_staff': False
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description='Dados inválidos',
                examples=[
                    OpenApiExample(
                        'Username em uso',
                        value={'error': 'Este nome de usuário já está em uso.'}
                    )
                ]
            ),
            403: OpenApiResponse(
                description='Permissão negada',
                examples=[
                    OpenApiExample(
                        'Sem permissão',
                        value={'error': 'Você não tem permissão para atualizar este perfil.'}
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição para usuário normal',
                value={
                    'first_name': 'João',
                    'last_name': 'Silva',
                    'email': 'joao.silva@example.com'
                }
            ),
            OpenApiExample(
                'Exemplo de requisição para superusuário',
                value={
                    'first_name': 'João',
                    'last_name': 'Silva',
                    'email': 'joao.silva@example.com',
                    'is_active': True,
                    'is_staff': True
                }
            )
        ]
    )
)
class UserUpdateProfile(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # Verifica se o usuário é o dono do perfil
        if user.id != pk:
            return Response({"error": "Você não tem permissão para atualizar este perfil."}, status=status.HTTP_403_FORBIDDEN)

        # Checa se o usuário é superadministrador, se for, permite modificar is_staff e is_active
        is_superuser = user.is_superuser

        data = request.data

        # Atualiza apenas os campos passados na requisição
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

        # Permitir a atualização de is_active e is_staff somente para superadministradores
        if 'is_active' in data and is_superuser:
            user.is_active = data['is_active']
        if 'is_staff' in data and is_superuser:
            user.is_staff = data['is_staff']

        user.save()
        print(f"User saved: {user.id}, {user.first_name}, {user.last_name}")

        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
        }, status=status.HTTP_200_OK)


class FuncionarioPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class FuncionarioPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class UsersList(ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = FuncionarioPagination

    def get_queryset(self):
        return User.objects.all().order_by('id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            user_ids = [user.id for user in page]

            # Bulk fetch all funcionarios for these users
            funcionarios = Funcionario.objects.filter(
                user_id__in=user_ids
            ).select_related('empresa')

            # Create a mapping of user_id -> list of funcionarios
            funcionarios_dict = {}
            for funcionario in funcionarios:
                if funcionario.user_id not in funcionarios_dict:
                    funcionarios_dict[funcionario.user_id] = []
                funcionarios_dict[funcionario.user_id].append(funcionario)

            serializer_data = []

            for user in page:
                empresas_data = []
                user_funcionarios = funcionarios_dict.get(user.id, [])

                for funcionario in user_funcionarios:
                    empresa = funcionario.empresa

                    # Check if empresa exists and has sistema_id=3
                    if empresa and empresa.sistema_id == 1:
                        empresas_data.append({
                            'role': funcionario.role,
                            'empresa_id': empresa.id,
                            'razao_social': empresa.razao_social,
                            'documento': empresa.documento,
                            'is_branch': True if empresa.matriz_filial_id is not None else False,
                        })
                    elif empresa:
                        # Empresa exists but sistema_id != 3
                        empresas_data.append({
                            'role': funcionario.role,
                            'empresa_id': empresa.id,
                            'sistema_id': empresa.sistema_id,
                            'razao_social': empresa.razao_social,
                            'documento': empresa.documento,
                            'is_branch': True if empresa.matriz_filial_id is not None else False,
                            'note': f"Sistema ID é {empresa.sistema_id}, não 1"
                        })
                    else:
                        # No empresa associated
                        empresas_data.append({
                            'role': funcionario.role,
                            'empresa_id': funcionario.empresa_id,
                            'razao_social': None,
                            'documento': None,
                            'is_branch': True if empresa.matriz_filial_id is not None else False,
                            'note': 'Empresa não encontrada'
                        })

                data = {
                    'id': user.id,
                    'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                    'email': user.email,
                    'admin': user.is_staff,
                    'status': user.is_active,
                    'created_at': user.date_joined,
                    'empresas': empresas_data,
                }

                serializer_data.append(data)

            return self.get_paginated_response(serializer_data)

        return Response([])
