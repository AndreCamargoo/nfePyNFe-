
from django.db import transaction
from django.core.files.storage import default_storage

from django.db.models import Q
from django.db.models import Prefetch

from rest_framework import generics
from rest_framework.views import APIView

from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404

from app.utils import utils

from empresa.models import (
    Empresa, CategoriaEmpresa, ConexaoBanco,
    Funcionario, RotasPermitidas
)
from sistema.models import EmpresaSistema

from empresa.serializer import (
    EmpresaModelSerializer, EmpresaCreateSerializer, EmpresaUpdateSerializer, EmpresaListSerializer,
    EmpresaAllModelSerializer, CategoriaEmpresaModelSerializer, ConexaoBancoModelSerializer,
    FuncionarioListSerializer, FuncionarioSerializer, FuncionarioAllModelSerializer,
    FuncionarioRotaModelSerializer, EmpresaDetalhesVinculadasSerializer, EmpresaAdminSerializer
)

from app.permissions import GlobalDefaultPermission, UsuarioIndependenteOuAdmin

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample


class EmpresaBaseView:
    """Classe base com configurações comuns"""

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), UsuarioIndependenteOuAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return Empresa.objects.none()

        user = self.request.user

        try:
            # Verifica se é funcionário ativo
            funcionario = Funcionario.objects.filter(
                user=user,
                status='1',
                role='funcionario'
            ).select_related('empresa').first()

            if funcionario:
                empresa = funcionario.empresa

                # Verifica se a empresa ainda está ativa
                if empresa.status != '1':
                    raise PermissionDenied(
                        detail="A empresa vinculada à sua conta está inativa. "
                               "O acesso a esta funcionalidade foi bloqueado."
                    )

                # Funcionário ativo + empresa ativa → retorna só ela
                return Empresa.objects.filter(id=empresa.id)

        except PermissionDenied:
            raise  # Repassa a exceção corretamente
        except Exception:
            return Empresa.objects.none()

        # Caso o usuário não seja funcionário → verificar empresas ativas dele
        empresas = Empresa.objects.filter(
            Q(usuario=user) | Q(matriz_filial__usuario=user),
            status='1'  # Apenas empresas ativas
        )

        if not empresas.exists():
            raise PermissionDenied(
                detail="Você não possui nenhuma empresa ativa vinculada à sua conta."
            )

        return empresas


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="01_empresa_list",
        summary="01 Listar empresas do usuário",
        description=(
            "Retorna todas as empresas vinculadas ao usuário autenticado **ou** "
            "empresas que sejam filiais de alguma empresa pertencente ao usuário autenticado."
        ),
        responses={
            200: EmpresaListSerializer(many=True)
        },
    ),
    post=extend_schema(
        tags=["Empresa"],
        operation_id="02_empresa_create",
        summary="02 Criar empresa",
        description=(
            "Cria uma nova empresa vinculada ao usuário autenticado.\n\n"
            "### Regras de negócio:\n"
            "- O campo **documento** deve ser único (não pode repetir).\n"
            "- Se **matriz_filial** for informado:\n"
            "  - A empresa matriz deve **pertencer ao usuário autenticado**.\n"
            "  - A empresa matriz não pode ser uma filial (ou seja, deve ter `matriz_filial=null`).\n"
            "  - O usuário precisa já ter ao menos uma empresa **matriz** cadastrada.\n"
            "- O campo **usuario** é automaticamente vinculado ao usuário autenticado."
        ),
        request=EmpresaCreateSerializer,

        responses={
            201: EmpresaCreateSerializer,
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class EmpresaListCreateAPIView(EmpresaBaseView, generics.ListCreateAPIView):

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EmpresaCreateSerializer
        return EmpresaListSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="03_empresa_detail",
        summary="03 Detalhar empresa",
        description=(
            "Retorna os dados de uma empresa específica.\n\n"
            "### Permissões:\n"
            "- A empresa deve pertencer ao usuário autenticado **OU**\n"
            "- Ser uma filial de alguma empresa pertencente ao usuário autenticado"
        ),
        responses={
            200: EmpresaListSerializer,
            404: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    put=extend_schema(
        tags=["Empresa"],
        summary="04 Atualizar empresa (PUT)",
        description=(
            "Atualiza **todos os campos** de uma empresa.\n\n"
            "### Permissões:\n"
            "- A empresa deve pertencer ao usuário autenticado **OU**\n"
            "- Ser uma filial de alguma empresa pertencente ao usuário autenticado"
        ),
        request=EmpresaUpdateSerializer,
        responses={200: EmpresaUpdateSerializer},
    ),
    patch=extend_schema(
        tags=["Empresa"],
        summary="05 Atualizar empresa (PATCH)",
        description=(
            "Atualiza **parcialmente** os campos de uma empresa.\n\n"
            "### Permissões:\n"
            "- A empresa deve pertencer ao usuário autenticado **OU**\n"
            "- Ser uma filial de alguma empresa pertencente ao usuário autenticado"
        ),
        request=EmpresaUpdateSerializer,
        responses={200: EmpresaUpdateSerializer},
    ),
    delete=extend_schema(
        tags=["Empresa"],
        summary="06 Deletar empresa",
        description=(
            "Remove uma empresa.\n\n"
            "### Permissões:\n"
            "- A empresa deve pertencer ao usuário autenticado **OU**\n"
            "- Ser uma filial de alguma empresa pertencente ao usuário autenticado"
        ),
        responses={
            204: None,
            404: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class EmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Permite recuperar, atualizar ou deletar apenas empresas
    pertencentes ao usuário autenticado.
    """

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), UsuarioIndependenteOuAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        # Verificar se o usuário é super admin
        if user.is_superuser or user.is_staff:
            return Empresa.objects.all()

        # Para usuários normais, retorna apenas empresas que pertencem a ele
        # ou empresas onde ele é funcionário
        return Empresa.objects.filter(
            # Empresas onde o usuário é dono
            Q(usuario=user) |
            # Empresas onde é funcionário
            Q(funcionarios_empresa__user=user, funcionarios_empresa__status='1')
        ).distinct()

    def get_object(self):
        """
        Retorna a empresa apenas se o usuário tiver permissão.
        Sobrescreve para garantir segurança extra.
        """
        queryset = self.get_queryset()
        pk = self.kwargs.get('pk')

        try:
            obj = queryset.get(pk=pk)
        except Empresa.DoesNotExist:
            raise NotFound(detail="Empresa não encontrada ou você não tem permissão para acessá-la.")

        # Verificação adicional de permissão
        user = self.request.user
        if not (user.is_superuser or user.is_staff or obj.usuario == user):
            # Verificar se é funcionário ativo
            is_employee = Funcionario.objects.filter(
                user=user,
                empresa=obj,
                status='1'
            ).exists()

            if not is_employee:
                raise PermissionDenied(detail="Você não tem permissão para acessar esta empresa.")

        return obj

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return EmpresaUpdateSerializer
        return EmpresaListSerializer

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class EmpresaDetalhesVinculadasAPIView(generics.RetrieveAPIView):
    """
    Retorna os detalhes de uma empresa específica e todas as suas empresas vinculadas (filiais),
    incluindo funcionários da matriz e das filiais.
    """
    permission_classes = [
        IsAuthenticated,
        UsuarioIndependenteOuAdmin
    ]
    serializer_class = EmpresaDetalhesVinculadasSerializer

    def get_object(self):
        user = self.request.user
        pk = self.kwargs.get('pk')

        try:
            empresa = Empresa.objects.get(pk=pk)
        except Empresa.DoesNotExist:
            raise NotFound(detail="Empresa não encontrada.")

        # Permissão
        if not (user.is_superuser or user.is_staff or empresa.usuario == user):
            is_employee = Funcionario.objects.filter(
                user=user,
                empresa=empresa,
                status='1'
            ).exists()

            if not is_employee:
                raise PermissionDenied(
                    detail="Você não tem permissão para acessar esta empresa."
                )

        return empresa

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Filiais com funcionários (OTIMIZADO)
        filiais = Empresa.objects.filter(
            matriz_filial=instance,
            status='1'
        ).prefetch_related(
            Prefetch(
                'funcionarios_empresa',
                queryset=Funcionario.objects.filter(status='1').select_related('user')
            )
        )

        # Funcionários da empresa principal
        funcionarios = Funcionario.objects.filter(
            empresa=instance,
            status='1'
        ).select_related('user')

        funcionarios_data = [
            {
                'id': func.id,
                'user_id': func.user.id,
                'username': func.user.username,
                'email': func.user.email,
                'role': func.role,
                'status': func.status,
            }
            for func in funcionarios
        ]

        # Monta filiais com funcionários
        filiais_data = []

        for filial in filiais:
            funcionarios_filial_data = [
                {
                    'id': f.id,
                    'user_id': f.user.id,
                    'username': f.user.username,
                    'email': f.user.email,
                    'role': f.role,
                    'status': f.status,
                }
                for f in filial.funcionarios_empresa.all()
            ]

            filiais_data.append({
                'id': filial.id,
                'razao_social': filial.razao_social,
                'documento': filial.documento,
                'uf': filial.uf,
                'status': filial.status,
                'funcionarios': funcionarios_filial_data
            })

        # Matriz (se for filial)
        matriz = instance.matriz_filial if instance.matriz_filial else None

        # Conexão banco
        conexao_banco = None
        if hasattr(instance, 'conexao_banco') and instance.conexao_banco.status:
            conexao_banco = {
                'id': instance.conexao_banco.id,
                'host': instance.conexao_banco.get_host(),
                'porta': instance.conexao_banco.get_porta(),
                'usuario': instance.conexao_banco.get_usuario(),
                'database': instance.conexao_banco.get_database(),
            }

        # =========================================================
        # LISTA DE SISTEMAS (MÚLTIPLOS) - USANDO EmpresaSistema
        # =========================================================
        sistemas = []

        # Busca todos os sistemas vinculados via EmpresaSistema
        empresa_sistemas = EmpresaSistema.objects.filter(
            empresa=instance,
            ativo=True
        ).select_related('sistema')

        for es in empresa_sistemas:
            sistemas.append({
                'id': es.sistema.id,
                'nome': es.sistema.nome,
                'descricao': getattr(es.sistema, 'descricao', ''),
                'max_funcionarios_registros': es.max_funcionarios_registros,
                'criar_banco': es.criar_banco,
            })

        # RESPONSE FINAL
        data = {
            'id': instance.id,
            'razao_social': instance.razao_social,
            'documento': instance.documento,
            'ie': instance.ie,
            'uf': instance.uf,
            'status': instance.status,
            'tipo': 'FILIAL' if instance.matriz_filial else 'MATRIZ',

            'categoria': {
                'id': instance.categoria.id,
                'nome': instance.categoria.nome,
            } if instance.categoria else None,

            'sistemas': sistemas,  # LISTA de sistemas
            'sistemas_ids': [s['id'] for s in sistemas],  # IDs dos sistemas

            'matriz': {
                'id': matriz.id,
                'razao_social': matriz.razao_social,
                'documento': matriz.documento,
            } if matriz else None,

            'filiais': filiais_data,
            'conexao_banco': conexao_banco,
            'funcionarios': funcionarios_data,
        }

        return Response(data)


class EmpresaPorUsuarioAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]
    serializer_class = EmpresaModelSerializer

    def get_object(self):
        user = self.request.user  # Usuário autenticado

        try:
            # Retorna apenas a empresa matriz do usuário logado
            return Empresa.objects.get(usuario=user, matriz_filial__isnull=True)
        except Empresa.DoesNotExist:
            raise NotFound("Empresa matriz não encontrada para este usuário.")


class EmpresasGeraisAPIView(generics.ListAPIView):
    permission_classes = [
        IsAuthenticated,
        # IsAdminUser,
        UsuarioIndependenteOuAdmin,
    ]
    serializer_class = EmpresaAllModelSerializer
    queryset = Empresa.objects.filter(status=1, matriz_filial__isnull=True).order_by('created_at')
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        """Aplica a mesma lógica de paginação da view original"""
        paginate = self.request.query_params.get("paginate", "false")

        if paginate.lower() in ["true", "1", "yes"]:
            return super().paginate_queryset(queryset)

        return None  # padrão SEM paginação


@extend_schema_view(
    get=extend_schema(
        tags=["Categoria empresa"],
        operation_id="01_listar_categorias",
        summary="01 Listar todas as categorias de empresas",
        description="Retorna a lista de categorias e subcategorias de empresas.",
        responses={
            200: CategoriaEmpresaModelSerializer(many=True),
        },
    ),
    post=extend_schema(
        exclude=True
    )
)
class CategoriaEmpresaListCreateAPIView(generics.ListCreateAPIView):
    queryset = CategoriaEmpresa.objects.all()
    serializer_class = CategoriaEmpresaModelSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), GlobalDefaultPermission()]
        return [IsAuthenticated()]

    def get(self, request, *args, **kwargs):
        """Método GET para listar categorias e subcategorias"""
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Método POST para criar categorias de empresas"""
        return super().post(request, *args, **kwargs)


@extend_schema(exclude=True)
class CategoriaEmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CategoriaEmpresa.objects.all()
    serializer_class = CategoriaEmpresaModelSerializer
    permission_classes = [IsAuthenticated, GlobalDefaultPermission]


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="07_conexao_banco_list",
        summary="07 Listar conexão de banco",
        description=(
            "Retorna a configuração de conexão com o banco de dados da empresa matriz do usuário autenticado.\n\n"
            "### Regras de negócio:\n"
            "- Apenas a **empresa matriz** do usuário pode ter configuração de banco\n"
            "- Retorna apenas **uma conexão** (a primeira encontrada)\n"
            "- Campos sensíveis como senha são descriptografados automaticamente\n"
            "- Se nenhuma conexão for encontrada, retorna lista vazia"
        ),
        responses={
            200: ConexaoBancoModelSerializer(many=False),
            400: {"description": "Empresa matriz ativa não encontrada"},
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta',
                value={
                    "id": 1,
                    "empresa": 1,
                    "host": "localhost",
                    "porta": 5432,
                    "usuario": "meu_usuario",
                    "database": "meu_banco",
                    "senha": "********"
                },
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        tags=["Empresa"],
        operation_id="08_conexao_banco_create",
        summary="08 Criar conexão de banco",
        description=(
            "Cria uma nova configuração de conexão com banco de dados para a empresa matriz do usuário.\n\n"
            "### Regras de negócio:\n"
            "- O usuário deve ter uma **empresa matriz ativa**\n"
            "- Apenas **uma conexão por empresa matriz** é permitida\n"
            "- O campo **criar banco** só será considerado se:\n"
            "  - O administrador do sistema tiver liberado a permissão\n"
            "- Campos sensíveis como senha são **criptografados** automaticamente antes do armazenamento"
        ),
        request=ConexaoBancoModelSerializer,
        responses={
            201: ConexaoBancoModelSerializer,
            400: {"description": "Erro de validação ou empresa matriz não encontrada"},
            403: {"description": "Permissão para criar banco não concedida pelo administrador"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    "host": "meu-servidor.com",
                    "porta": 5432,
                    "usuario": "usuario_banco",
                    "database": "nome_banco",
                    "senha": "senha_segura",
                    "criar_banco": True
                },
                request_only=True
            )
        ]
    )
)
class ConexaoBancoListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ConexaoBancoModelSerializer
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]
    pagination_class = None

    # def get_queryset(self):
    #     user = self.request.user
    #     conexao = ConexaoBanco.objects.filter(empresa__usuario=user).first()

    #     if conexao:
    #         try:
    #             print(
    #                 "HOST:", conexao.get_host(),
    #                 "\nPORTA:", conexao.get_porta(),
    #                 "\nUSUÁRIO:", conexao.get_usuario(),
    #                 "\nDATABASE:", conexao.get_database(),
    #                 "\nSENHA:", conexao.get_senha(),
    #                 "\nUSUÁRIO LOGADO:", user
    #             )
    #         except Exception as e:
    #             print("Erro ao descriptografar campos:", e)

    #         # Retorna como queryset (dentro de uma lista)
    #         return ConexaoBanco.objects.filter(pk=conexao.pk)
    #     else:
    #         print("Nenhuma conexão encontrada.")
    #         return ConexaoBanco.objects.none()

    def get_queryset(self):
        user = self.request.user

        # Retorna a conexão da empresa matriz do usuário (apenas ativa)
        conexao = (
            ConexaoBanco.objects.filter(
                empresa__usuario=user,
                empresa__status='1',
                empresa__matriz_filial__isnull=True,
                status=True
            ).first()
        )

        return [conexao] if conexao else []

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user

        # Verifica se o usuário possui empresa matriz ativa
        empresa = (
            Empresa.objects.filter(
                usuario=user,
                matriz_filial__isnull=True,
                status='1'
            ).first()
        )

        if not empresa:
            raise PermissionDenied('A empresa vinculada à sua conta está inativa.')

        context['empresa'] = empresa
        return context


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="09_funcionario_list",
        summary="09 Listar funcionários",
        description=(
            "Retorna todos os funcionários ativos das empresas vinculadas ao usuário autenticado.\n\n"
            "### Regras de negócio:\n"
            "- Lista apenas funcionários\n"
            "- Mostra apenas funcionários das empresas onde o usuário tem acesso\n"
            "- Se o limite for excedido, novas criações serão bloqueadas"
        ),
        responses={
            200: FuncionarioListSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta',
                value=[{
                    "id": 1,
                    "nome": "João Silva",
                    "email": "joao@empresa.com",
                    "empresa": {"id": 1, "razao_social": "Empresa XYZ LTDA"},
                    "cargo": "Analista",
                    "status": "1",
                    "user": 123
                }],
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        tags=["Empresa"],
        operation_id="10_funcionario_create",
        summary="10 Criar funcionário",
        description=(
            "Cria um novo funcionário vinculado a uma empresa do usuário autenticado.\n\n"
            "### Regras de negócio:\n"
            "- A empresa deve pertencer ao usuário autenticado\n"
            "- **Limite de funcionários** de acordo com o contrato`\n"
            "- Se `limite de funcionários` for excedido, retorna erro 400\n"
            "- O email do funcionário deve ser único no sistema\n"
        ),
        request=FuncionarioSerializer,
        responses={
            201: FuncionarioListSerializer,
            400: {"description": "Erro de validação ou limite excedido"},
            403: {"description": "Permissão negada para a empresa"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    "nome": "Maria Santos",
                    "email": "maria@empresa.com",
                    "empresa": 1,
                    "cargo": "Desenvolvedor",
                    "telefone": "(11) 99999-9999"
                },
                request_only=True
            )
        ]
    )
)
class FuncionarioListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = FuncionarioListSerializer
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]

    def get_queryset(self):
        # Retorna os funcionários apenas das empresas em que o usuário está vinculado
        return Funcionario.objects.filter(empresa__in=self.request.user.empresas.all())

    def post(self, request, *args, **kwargs):
        serializer = FuncionarioSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            funcionario = serializer.save()
            # Retorna os dados completos do funcionário criado
            response_serializer = FuncionarioListSerializer(funcionario)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="11_funcionario_detail",
        summary="11 Detalhar funcionário",
        description=(
            "Retorna os dados completos de um funcionário específico.\n\n"
            "### Regras de negócio:\n"
            "- O funcionário deve pertencer a uma empresa do usuário autenticado\n"
            "- Apenas funcionários com **status='1' (ativo)** são retornados\n"
            "- Inclui dados do usuário vinculado no sistema"
        ),
        responses={
            200: FuncionarioListSerializer,
            404: {"description": "Funcionário não encontrado"}
        }
    ),
    put=extend_schema(
        tags=["Empresa"],
        operation_id="12_funcionario_update_put",
        summary="12 Atualizar funcionário (PUT)",
        description=(
            "Atualiza **todos os campos** de um funcionário.\n\n"
            "### Regras de negócio:\n"
            "- O funcionário deve pertencer a uma empresa do usuário autenticado\n"
            "- Atualiza também o usuário vinculado no sistema\n"
            "- O email deve permanecer único no sistema\n"
            "- Não é possível alterar o status por esta operação (use DELETE para desativar)"
        ),
        request=FuncionarioSerializer,
        responses={
            200: FuncionarioSerializer,
            400: {"description": "Erro de validação"},
            404: {"description": "Funcionário não encontrado"}
        }
    ),
    patch=extend_schema(
        tags=["Empresa"],
        operation_id="13_funcionario_update_patch",
        summary="13 Atualizar funcionário (PATCH)",
        description=(
            "Atualiza **parcialmente** os campos de um funcionário.\n\n"
            "### Regras de negócio:\n"
            "- O funcionário deve pertencer a uma empresa do usuário autenticado\n"
            "- Atualiza também o usuário vinculado no sistema\n"
            "- O email deve permanecer único no sistema\n"
            "- Não é possível alterar o status por esta operação (use DELETE para desativar)"
        ),
        request=FuncionarioSerializer,
        responses={
            200: FuncionarioSerializer,
            400: {"description": "Erro de validação"},
            404: {"description": "Funcionário não encontrado"}
        }
    ),
    delete=extend_schema(
        tags=["Empresa"],
        operation_id="14_funcionario_delete",
        summary="14 Desativar funcionário",
        description=(
            "Realiza **soft delete** (desativação) de um funcionário.\n\n"
            "### Regras de negócio:\n"
            "- Altera o status do funcionário para '2' (inativo)\n"
            "- Se o usuário **não estiver vinculado a outras empresas ativas**, desativa também a conta de usuário\n"
            "- Se o usuário **estiver vinculado a outras empresas**, mantém a conta ativa\n"
        ),
        responses={
            200: {"description": "Funcionário desativado com sucesso"},
            404: {"description": "Funcionário não encontrado"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta',
                value={
                    "message": "Funcionário desativado com sucesso."
                },
                response_only=True
            )
        ]
    )
)
class FuncionarioRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    # Mostra apenas funcionários ativos
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]

    def get_queryset(self):
        # Retorna apenas funcionários ativos das empresas do usuário
        return Funcionario.objects.filter(
            empresa__in=self.request.user.empresas.all(),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = instance.user

        # Verificar se o usuário está vinculado a OUTRAS empresas ATIVAS
        outras_vinculacoes_ativas = Funcionario.objects.filter(
            user=user,
            status='1'
        ).exclude(id=instance.id)

        # Se ele NÃO tem vínculo com mais nenhuma empresa, excluímos o login dele de vez.
        if not outras_vinculacoes_ativas.exists():
            # Hard delete no auth_user
            # (isso apaga em cascata o Funcionario devido ao on_delete=models.CASCADE)
            user.delete()
            return Response(
                {"message": "Funcionário e login excluídos definitivamente com sucesso."},
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            # Se ele ainda está em outra empresa (raro, mas possível), deletamos apenas este vínculo
            instance.delete()
            return Response(
                {"message": "Vínculo do funcionário com esta empresa removido com sucesso."},
                status=status.HTTP_204_NO_CONTENT
            )


class FuncionarioGeraisAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FuncionarioAllModelSerializer
    queryset = Funcionario.objects.filter(status=1).order_by('criado_em')
    pagination_class = utils.CustomPageSizePagination

    def paginate_queryset(self, queryset):
        paginate = self.request.query_params.get("paginate", "false")

        if paginate.lower() in ["true", "1", "yes"]:
            return super().paginate_queryset(queryset)

        return None  # padrão SEM paginação


class FuncionarioAdminDetail(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = FuncionarioAllModelSerializer

    def get_object(self):
        pk = self.kwargs.get('pk')

        try:
            # Get the funcionario by primary key and ensure it's active
            funcionario = Funcionario.objects.filter(
                pk=pk,
                status='1'
            ).select_related('empresa', 'user').first()

            if not funcionario:
                raise Http404("Funcionário não encontrado ou inativo")

            return funcionario

        except Funcionario.DoesNotExist:
            raise Http404("Funcionário não encontrado")


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="15_funcionario_rotas_list",
        summary="15 Listar rotas permitidas por funcionário",
        description=(
            "Retorna todas as **rotas permitidas** vinculadas aos funcionários das empresas "
            "que pertencem ao usuário autenticado.\n\n"
            "### Regras de negócio:\n"
            "- Somente **usuários independentes** ou **administradores** têm acesso.\n"
            "- Cada registro vincula um funcionário a um grupo de rotas (`GrupoRotaSistema`).\n"
            "- O campo `status` indica se o acesso está **ativo ('1')** ou **inativo ('2')**."
        ),
        responses={
            200: FuncionarioRotaModelSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Exemplo de resposta",
                value=[
                    {
                        "id": 1,
                        "funcionario": {
                            "id": 5,
                            "user": 12,
                            "empresa": {"id": 3, "razao_social": "Tech Solutions LTDA"},
                            "role": "admin",
                            "status": "1"
                        },
                        "rota": {
                            "id": 2,
                            "nome": "Módulo Fiscal",
                            "descricao": "Acesso ao módulo de NF-e",
                            "sistema": {"id": 1, "nome": "ERP Fiscal"}
                        },
                        "status": "Ativo",
                        "criado_em": "2025-10-06T10:30:00Z",
                        "atualizado_em": "2025-10-06T10:31:00Z"
                    }
                ],
                response_only=True
            )
        ],
    ),
    post=extend_schema(
        tags=["Empresa"],
        operation_id="16_funcionario_rota_create",
        summary="16 Criar rota permitida para funcionário",
        description=(
            "Cria uma nova permissão de rota para um funcionário específico.\n\n"
            "### Regras de negócio:\n"
            "- Apenas **usuários independentes** ou **administradores** podem criar.\n"
            "- A combinação `(funcionario, rota)` deve ser **única**.\n"
            "- O campo `status` deve ser `'1'` (Ativo) ou `'2'` (Inativo).\n"
            "- Caso a rota já esteja cadastrada para o funcionário, retorna erro 400."
        ),
        request=FuncionarioRotaModelSerializer,
        responses={
            201: FuncionarioRotaModelSerializer,
            400: {"description": "Erro de validação ou rota já cadastrada"},
            403: {"description": "Permissão negada"},
        },
        examples=[
            OpenApiExample(
                "Exemplo de requisição",
                value={
                    "funcionario": 5,
                    "rota": 2,
                    "status": "1"
                },
                request_only=True
            ),
            OpenApiExample(
                "Exemplo de resposta",
                value={
                    "id": 10,
                    "funcionario": {
                        "id": 5,
                        "user": 12,
                        "empresa": {"id": 3, "razao_social": "Tech Solutions LTDA"},
                        "role": "admin",
                        "status": "1"
                    },
                    "rota": {
                        "id": 2,
                        "nome": "Módulo Fiscal",
                        "descricao": "Acesso ao módulo de NF-e",
                        "sistema": {"id": 1, "nome": "ERP Fiscal"}
                    },
                    "status": "Ativo",
                    "criado_em": "2025-10-06T10:30:00Z",
                    "atualizado_em": "2025-10-06T10:31:00Z"
                },
                response_only=True
            )
        ],
    )
)
class FuncionarioRotasListCreateAPIView(generics.ListCreateAPIView):
    queryset = RotasPermitidas.objects.all()
    serializer_class = FuncionarioRotaModelSerializer
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]


@extend_schema_view(
    get=extend_schema(
        tags=["Empresa"],
        operation_id="17_funcionario_rota_detail",
        summary="17 Detalhar rota permitida de funcionário",
        description=(
            "Retorna os detalhes de uma rota permitida específica.\n\n"
            "### Regras de negócio:\n"
            "- Apenas **usuários independentes** ou **administradores** têm acesso.\n"
            "- O registro deve existir e estar vinculado a um funcionário ativo."
        ),
        responses={
            200: FuncionarioRotaModelSerializer,
            404: {"description": "Rota permitida não encontrada"}
        },
    ),
    put=extend_schema(
        tags=["Empresa"],
        operation_id="18_funcionario_rota_update_put",
        summary="18 Atualizar rota permitida (PUT)",
        description=(
            "Atualiza todos os campos de uma permissão de rota de funcionário.\n\n"
            "### Regras de negócio:\n"
            "- Apenas **usuários independentes** ou **administradores** podem atualizar.\n"
            "- A combinação `(funcionario, rota)` deve continuar única.\n"
            "- Não é possível alterar `funcionario` e `rota` para um par já existente."
        ),
        request=FuncionarioRotaModelSerializer,
        responses={
            200: FuncionarioRotaModelSerializer,
            400: {"description": "Erro de validação ou duplicidade"},
            404: {"description": "Rota permitida não encontrada"},
        },
    ),
    patch=extend_schema(
        tags=["Empresa"],
        operation_id="19_funcionario_rota_update_patch",
        summary="19 Atualizar rota permitida (PATCH)",
        description=(
            "Atualiza parcialmente os campos de uma permissão de rota de funcionário.\n\n"
            "### Regras de negócio:\n"
            "- Apenas **usuários independentes** ou **administradores** podem atualizar.\n"
            "- O par `(funcionario, rota)` deve permanecer único.\n"
            "- O campo `status` pode ser alterado para ativar/inativar o acesso."
        ),
        request=FuncionarioRotaModelSerializer,
        responses={
            200: FuncionarioRotaModelSerializer,
            400: {"description": "Erro de validação"},
            404: {"description": "Rota permitida não encontrada"},
        },
    ),
    delete=extend_schema(
        tags=["Empresa"],
        operation_id="20_funcionario_rota_delete",
        summary="20 Remover rota permitida",
        description=(
            "Remove uma permissão de rota de funcionário.\n\n"
            "### Regras de negócio:\n"
            "- Apenas **usuários independentes** ou **administradores** podem excluir.\n"
            "- A exclusão é **definitiva** (remoção física).\n"
            "- Caso o registro não exista, retorna 404."
        ),
        responses={
            204: {"description": "Permissão de rota removida com sucesso"},
            404: {"description": "Rota permitida não encontrada"}
        },
        examples=[
            OpenApiExample(
                "Exemplo de resposta",
                value={"message": "Permissão de rota removida com sucesso."},
                response_only=True
            )
        ]
    )
)
class FuncionarioRotasRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RotasPermitidas.objects.all()
    serializer_class = FuncionarioRotaModelSerializer
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]


# SOMENTE PARA ADMINISTRADORES
@extend_schema(exclude=True)
class CriarEmpresaAdminAPIView(APIView):
    """
    API para criar ou atualizar empresa via admin
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Prepara os dados
        data = request.data.copy()

        # Processa arquivo de certificado
        if request.FILES.get('certificado_file'):
            data['certificado_file'] = request.FILES['certificado_file']

        # Processa documento (limpa caracteres)
        if data.get('documento'):
            import re
            data['documento'] = re.sub(r'[^0-9]', '', str(data['documento']))

        # Converte sistemas_ids
        if data.get('sistemas_ids') and isinstance(data['sistemas_ids'], str):
            try:
                import json
                data['sistemas_ids'] = json.loads(data['sistemas_ids'])
            except Exception:
                data['sistemas_ids'] = [int(x.strip()) for x in data['sistemas_ids'].split(',') if x.strip()]

        # Converte funcionarios
        if data.get('funcionarios') and isinstance(data['funcionarios'], str):
            try:
                import json
                data['funcionarios'] = json.loads(data['funcionarios'])
            except Exception:
                data['funcionarios'] = []

        # Converte conexao_banco
        if data.get('conexao_banco') and isinstance(data['conexao_banco'], str):
            try:
                import json
                data['conexao_banco'] = json.loads(data['conexao_banco'])
            except Exception:
                data['conexao_banco'] = None

        # Determina se é update ou create
        instance = None
        if data.get('empresa_id'):
            try:
                from empresa.models import Empresa
                instance = Empresa.objects.get(id=data['empresa_id'])
            except Empresa.DoesNotExist:
                pass

        serializer = EmpresaAdminSerializer(
            instance=instance,
            data=data,
            context={'request': request}
        )

        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(exclude=True)
class DeletarEmpresaAdminAPIView(APIView):
    """
    API para deletar empresa via admin
    - Remove todos os vínculos da empresa
    - Desativa funcionários (exceto o admin/dono)
    - Remove arquivo de certificado
    - Remove conexões com banco
    - Remove vínculos com sistemas
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        empresa_id = request.data.get('empresa_id') or kwargs.get('empresa_id')

        if not empresa_id:
            return Response(
                {'error': 'empresa_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            return Response(
                {'error': 'Empresa não encontrada.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verifica permissão
        user = request.user
        if not user.is_superuser:
            return Response(
                {'error': 'Apenas superusuários podem deletar empresas.'},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            resultado = {
                'empresa_id': empresa.id,
                'razao_social': empresa.razao_social,
                'acoes': []
            }

            # 1. Remove o arquivo de certificado se existir
            if empresa.file and empresa.file.name:
                try:
                    if default_storage.exists(empresa.file.name):
                        default_storage.delete(empresa.file.name)
                        resultado['acoes'].append(f"Arquivo removido: {empresa.file.name}")
                except Exception as e:
                    resultado['acoes'].append(f"Erro ao remover arquivo: {str(e)}")

            # 2. Remove conexão com banco de dados
            conexao_banco = ConexaoBanco.objects.filter(empresa=empresa).first()
            if conexao_banco:
                conexao_banco.delete()
                resultado['acoes'].append("Conexão com banco de dados removida")

            # 3. Remove vínculos com sistemas
            sistemas_vinculados = EmpresaSistema.objects.filter(empresa=empresa)
            qtd_sistemas = sistemas_vinculados.count()
            sistemas_vinculados.delete()
            resultado['acoes'].append(f"{qtd_sistemas} vínculo(s) de sistema(s) removido(s)")

            # 4. Desativa funcionários (exceto o admin/dono)
            funcionarios = Funcionario.objects.filter(empresa=empresa)
            admin_user = empresa.usuario
            funcionarios_desativados = 0

            for funcionario in funcionarios:
                if funcionario.user.id != admin_user.id:
                    # Desativa o usuário
                    user_func = funcionario.user
                    if user_func.is_active:
                        user_func.is_active = False
                        user_func.save()
                        funcionarios_desativados += 1
                    # Remove o vínculo do funcionário
                    funcionario.delete()

            resultado['acoes'].append(f"{funcionarios_desativados} funcionário(s) desativado(s) e desvinculado(s)")

            # 5. Remove filiais (se existirem)
            filiais = Empresa.objects.filter(matriz_filial=empresa)
            qtd_filiais = filiais.count()

            for filial in filiais:
                # Remove arquivos das filiais
                if filial.file and filial.file.name:
                    try:
                        if default_storage.exists(filial.file.name):
                            default_storage.delete(filial.file.name)
                    except Exception:
                        pass

                # Remove conexões das filiais
                ConexaoBanco.objects.filter(empresa=filial).delete()

                # Remove vínculos de sistemas das filiais
                EmpresaSistema.objects.filter(empresa=filial).delete()

                # Desativa funcionários das filiais
                for func in Funcionario.objects.filter(empresa=filial):
                    if func.user.id != filial.usuario.id:
                        user_func = func.user
                        if user_func.is_active:
                            user_func.is_active = False
                            user_func.save()
                    func.delete()

                # Deleta a filial
                filial.delete()

            if qtd_filiais > 0:
                resultado['acoes'].append(f"{qtd_filiais} filial(is) removida(s)")

            # 6. Remove histórico NSU (se existir)
            from empresa.models import HistoricoNSU
            historicos = HistoricoNSU.objects.filter(empresa=empresa)
            qtd_historicos = historicos.count()
            historicos.delete()

            if qtd_historicos > 0:
                resultado['acoes'].append(f"{qtd_historicos} registro(s) de histórico removido(s)")

            # 7. Por fim, deleta a empresa
            empresa.delete()
            resultado['acoes'].append("Empresa deletada com sucesso")
            resultado['success'] = True
            resultado['message'] = f"Empresa '{resultado['razao_social']}' foi deletada com sucesso."

            return Response(resultado, status=status.HTTP_200_OK)
