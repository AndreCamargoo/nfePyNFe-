from django.db.models import Q

from rest_framework import generics

from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from empresa.models import (
    Empresa, CategoriaEmpresa, ConexaoBanco,
    Funcionario, RotasPermitidas
)
from empresa.serializer import (
    EmpresaModelSerializer, EmpresaCreateSerializer, EmpresaUpdateSerializer, EmpresaListSerializer,
    CategoriaEmpresaModelSerializer, ConexaoBancoModelSerializer,
    FuncionarioListSerializer, FuncionarioSerializer,
    FuncionarioRotaModelSerializer
)

from app.permissions import GlobalDefaultPermission, UsuarioIndependenteOuAdmin

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample


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
class EmpresaRetrieveUpdateDestroyAPIView(EmpresaBaseView, generics.RetrieveUpdateDestroyAPIView):
    """
    Permite recuperar, atualizar ou deletar apenas empresas
    pertencentes ao usuário autenticado.
    """

    def get_queryset(self):
        """
        Filtra para retornar apenas empresas do usuário logado.
        """
        user = self.request.user
        return Empresa.objects.filter(usuario=user)

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return EmpresaUpdateSerializer
        return EmpresaListSerializer

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


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

        # Verificar se o usuário está vinculado a outras empresas ATIVAS
        outras_vinculacoes_ativas = Funcionario.objects.filter(
            user=user,
            status='1'
        ).exclude(id=instance.id)

        if not outras_vinculacoes_ativas.exists():
            user.is_active = False
            user.save()

        # Soft delete
        instance.status = '2'
        instance.save()

        return Response(
            {"message": "Funcionário desativado com sucesso."},
            status=status.HTTP_200_OK
        )


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
