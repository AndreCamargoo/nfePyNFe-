from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.validators import ValidationError

from app.permissions import GlobalDefaultPermission, UsuarioIndependenteOuAdmin
from sistema.models import Sistema, EmpresaSistema, RotaSistema, GrupoRotaSistema
from sistema.serializer import (
    SistemaSerializer, EmpresaSistemaSerializer,
    EmpresaSistemaModelSerializer, RotaSistemaModelSerializer,
    GrupoRotaSistemaListSerializer, GrupoRotaSistemaCreateSerializer
)

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample


@extend_schema(exclude=True)
class SistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = Sistema.objects.all()
    serializer_class = SistemaSerializer


@extend_schema(exclude=True)
class SistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = Sistema.objects.all()
    serializer_class = SistemaSerializer


@extend_schema(exclude=True)
class EmpresaSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    serializer_class = EmpresaSistemaModelSerializer

    def get_queryset(self):
        empresa_id = self.kwargs['empresa_id']
        return EmpresaSistema.objects.filter(empresa_id=empresa_id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['view'] = self
        return context


@extend_schema(exclude=True)
class EmpresaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = EmpresaSistema.objects.all()
    serializer_class = EmpresaSistemaSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Rotas do Sistema"],
        operation_id="01_listar_rotas_por_sistema",
        summary="01 Listar rotas disponíveis por sistema",
        description=(
            "Retorna todas as rotas e endpoints disponíveis para um sistema específico.\n\n"
            "### Funcionalidades:\n"
            "- Lista filtrada de rotas API por sistema\n"
            "- Informações sobre módulos e endpoints associados\n"
            "- Metadados para configuração de controle de acesso\n"
            "- Base para atribuição de permissões a funcionários\n\n"
            "### Parâmetros:\n"
            "- **sistema_id** (obrigatório): ID do sistema para filtrar as rotas\n\n"
            "### Permissões:\n"
            "- **GET**: Apenas a **empresa matriz** pode visualizar as rotas do sistema\n"
            "### Utilização:\n"
            "Esta lista é utilizada para definir quais rotas de um sistema específico "
            "cada funcionário pode acessar através do sistema de permissões hierárquicas."
        ),
        parameters=[
            OpenApiParameter(
                name='sistema_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID do sistema para filtrar as rotas',
                required=True
            )
        ],
        responses={
            200: RotaSistemaModelSerializer(many=True),
            400: {"description": "Parâmetro sistema_id não informado ou inválido"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição',
                value={
                    "sistema_id": 1
                },
                request_only=True
            ),
            OpenApiExample(
                'Exemplo de resposta',
                value=[
                    {
                        "id": 1,
                        "nome": "Módulo Fiscal - Consulta",
                        "descricao": "Endpoint para consulta de documentos fiscais",
                        "path": "/api/fiscal/consultar/",
                        "metodo": "GET",
                        "sistema": {
                            "id": 1,
                            "nome": "ERP Fiscal"
                        }
                    },
                    {
                        "id": 2,
                        "nome": "Módulo Fiscal - Importação",
                        "descricao": "Endpoint para importação de notas fiscais",
                        "path": "/api/fiscal/emitir/",
                        "metodo": "POST",
                        "sistema": {
                            "id": 1,
                            "nome": "ERP Fiscal"
                        }
                    }
                ],
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        exclude=True
    )
)
class RotaSistemaListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = RotaSistemaModelSerializer

    def get_queryset(self):
        """
        Filtra as rotas pelo sistema_id informado no query parameter
        """
        sistema_id = self.request.query_params.get('sistema_id')

        if not sistema_id:
            raise ValidationError({'sistema_id': 'Este parâmetro é obrigatório'})

        try:
            sistema_id = int(sistema_id)
        except (ValueError, TypeError):
            raise ValidationError({'sistema_id': 'Deve ser um número inteiro válido'})

        return RotaSistema.objects.filter(sistema_id=sistema_id)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser(), GlobalDefaultPermission()]
        return [IsAuthenticated(), UsuarioIndependenteOuAdmin()]

    def get_serializer_context(self):
        """
        Adiciona o contexto da requisição ao serializer
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


@extend_schema(exclude=True)
class RotaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser, GlobalDefaultPermission]
    queryset = RotaSistema.objects.all()
    serializer_class = RotaSistemaModelSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="listar_grupos_rotas_usuario",
        summary="Listar grupos de rotas do usuário",
        description=(
            "Retorna todos os Grupos de Rotas associados ao usuário autenticado.\n\n"
            "### Funcionalidades:\n"
            "- Lista personalizada dos grupos criados pelo usuário\n"
            "- Detalhes completos das rotas associadas a cada grupo\n"
            "- Informações do sistema vinculado a cada grupo\n"
            "- Base para gerenciamento de permissões personalizadas\n\n"
            "### Permissões:\n"
            "- **GET**: Usuários autenticados (independentes ou administradores)\n"
            "- **POST**: Usuários autenticados (independentes ou administradores)\n\n"
            "### Observações:\n"
            "- Cada usuário só visualiza seus próprios grupos\n"
            "- Grupos são vinculados automaticamente ao usuário na criação"
        ),
        responses={
            200: GrupoRotaSistemaListSerializer(many=True),
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para acessar este recurso"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta - Lista de grupos',
                value=[
                    {
                        "id": 1,
                        "nome": "Grupo Fiscal Básico",
                        "descricao": "Grupo para operações fiscais básicas",
                        "sistema": {
                            "id": 1,
                            "nome": "ERP Fiscal"
                        },
                        "rotas": [
                            {
                                "id": 1,
                                "nome": "Consulta NFE",
                                "path": "/api/nfe/consulta/",
                                "metodo": "GET",
                                "descricao": "Endpoint para consulta de notas fiscais"
                            },
                            {
                                "id": 2,
                                "nome": "Emissão NFE",
                                "path": "/api/nfe/emissao/",
                                "metodo": "POST",
                                "descricao": "Endpoint para emissão de notas fiscais"
                            }
                        ]
                    }
                ],
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="criar_grupo_rotas",
        summary="Criar novo grupo de rotas",
        description=(
            "Cria um novo grupo de rotas do sistema associado ao usuário autenticado.\n\n"
            "### Funcionalidades:\n"
            "- Criação de grupos personalizados de rotas\n"
            "- Associação automática ao usuário logado\n"
            "- Validação de compatibilidade entre rotas e sistema\n"
            "- Configuração de permissões em lote\n"
            "### Validações:\n"
            "- Todas as rotas devem pertencer ao sistema selecionado\n"
            "- Nome do grupo deve ser único para o usuário\n"
            "- Sistema deve existir e estar ativo\n"
            "### Permissões:\n"
            "- Apenas usuários independentes ou administradores"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            201: GrupoRotaSistemaListSerializer,
            400: {"description": "Dados de entrada inválidos ou rotas não pertencem ao sistema"},
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para criar grupos"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição - Criar grupo',
                value={
                    "nome": "Meu Grupo Fiscal",
                    "descricao": "Grupo para minhas operações fiscais preferidas",
                    "sistema": 1,
                    "rotas": [1, 2, 3, 5]
                },
                request_only=True
            ),
            OpenApiExample(
                'Exemplo de resposta - Grupo criado',
                value={
                    "id": 2,
                    "nome": "Meu Grupo Fiscal",
                    "descricao": "Grupo para minhas operações fiscais preferidas",
                    "sistema": {
                        "id": 1,
                        "nome": "ERP Fiscal"
                    },
                    "rotas": [
                        {
                            "id": 1,
                            "nome": "Consulta NFE",
                            "path": "/api/nfe/consulta/",
                            "metodo": "GET",
                            "descricao": "Endpoint para consulta de notas fiscais"
                        },
                        {
                            "id": 2,
                            "nome": "Emissão NFE",
                            "path": "/api/nfe/emissao/",
                            "metodo": "POST",
                            "descricao": "Endpoint para emissão de notas fiscais"
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class GrupoRotaSistemaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]
    serializer_class = GrupoRotaSistemaCreateSerializer

    def get_queryset(self):
        """Retorna apenas os grupos do usuário logado."""
        return GrupoRotaSistema.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        """Usa serializer diferente para listagem e criação."""
        if self.request.method == 'GET':
            return GrupoRotaSistemaListSerializer
        return GrupoRotaSistemaCreateSerializer

    def get_serializer_context(self):
        """Inclui o request no contexto do serializer."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Garante que o usuário seja definido automaticamente."""
        serializer.save()


@extend_schema_view(
    get=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="recuperar_grupo_rotas",
        summary="Recuperar grupo de rotas específico",
        description=(
            "Retorna os detalhes completos de um grupo de rotas específico.\n\n"
            "### Funcionalidades:\n"
            "- Visualização detalhada de um grupo específico\n"
            "- Lista completa das rotas associadas\n"
            "- Informações do sistema e metadados\n"
            "### Permissões:\n"
            "- Apenas o proprietário do grupo pode visualizá-lo\n"
            "- Usuários independentes ou administradores\n"
            "### Observações:\n"
            "- Retorna 404 se o grupo não existir ou não pertencer ao usuário"
        ),
        responses={
            200: GrupoRotaSistemaListSerializer,
            404: {"description": "Grupo não encontrado ou não pertence ao usuário"},
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para acessar este recurso"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta - Grupo específico',
                value={
                    "id": 1,
                    "nome": "Grupo Fiscal Avançado",
                    "descricao": "Grupo para operações fiscais avançadas",
                    "sistema": {
                        "id": 1,
                        "nome": "ERP Fiscal"
                    },
                    "rotas": [
                        {
                            "id": 1,
                            "nome": "Consulta NFE",
                            "path": "/api/nfe/consulta/",
                            "metodo": "GET",
                            "descricao": "Endpoint para consulta de notas fiscais"
                        },
                        {
                            "id": 3,
                            "nome": "Cancelamento NFE",
                            "path": "/api/nfe/cancelamento/",
                            "metodo": "POST",
                            "descricao": "Endpoint para cancelamento de notas fiscais"
                        },
                        {
                            "id": 4,
                            "nome": "Relatório Fiscal",
                            "path": "/api/fiscal/relatorios/",
                            "metodo": "GET",
                            "descricao": "Endpoint para geração de relatórios fiscais"
                        }
                    ],
                    "usuario": 1
                },
                response_only=True
            )
        ]
    ),
    put=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="atualizar_grupo_rotas",
        summary="Atualizar grupo de rotas completo",
        description=(
            "Atualiza completamente um grupo de rotas existente.\n\n"
            "### Funcionalidades:\n"
            "- Substitui todos os dados do grupo\n"
            "- Permite alterar nome, descrição, sistema e rotas\n"
            "- Validações de integridade mantidas\n"
            "### Validações:\n"
            "- Todas as rotas devem pertencer ao novo sistema (se alterado)\n"
            "- Nome deve permanecer único para o usuário\n"
            "- Sistema deve existir e estar ativo\n"
            "### Permissões:\n"
            "- Apenas o proprietário do grupo pode atualizá-lo"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            200: GrupoRotaSistemaListSerializer,
            400: {"description": "Dados de entrada inválidos"},
            404: {"description": "Grupo não encontrado ou não pertence ao usuário"},
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para atualizar este grupo"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição - Atualização completa',
                value={
                    "nome": "Grupo Fiscal Atualizado",
                    "descricao": "Descrição atualizada do grupo fiscal",
                    "sistema": 1,
                    "rotas": [1, 3, 4, 6]
                },
                request_only=True
            )
        ]
    ),
    patch=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="atualizar_parcial_grupo_rotas",
        summary="Atualização parcial do grupo de rotas",
        description=(
            "Atualiza parcialmente um grupo de rotas existente.\n"
            "### Funcionalidades:\n"
            "- Permite atualizar apenas campos específicos\n"
            "- Mantém dados não enviados na requisição\n"
            "- Ideal para atualizações incrementais\n"
            "### Validações:\n"
            "- Aplica validações apenas nos campos enviados\n"
            "- Mantém validações de integridade para rotas e sistema\n"
            "### Permissões:\n"
            "- Apenas o proprietário do grupo pode atualizá-lo"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            200: GrupoRotaSistemaListSerializer,
            400: {"description": "Dados de entrada inválidos"},
            404: {"description": "Grupo não encontrado ou não pertence ao usuário"},
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para atualizar este grupo"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de requisição - Atualização parcial',
                value={
                    "nome": "Novo Nome do Grupo",
                    "rotas": [1, 2]
                },
                request_only=True
            )
        ]
    ),
    delete=extend_schema(
        tags=["Grupos de Rotas"],
        operation_id="excluir_grupo_rotas",
        summary="Excluir grupo de rotas",
        description=(
            "Exclui permanentemente um grupo de rotas específico.\n"
            "### Funcionalidades:\n"
            "- Remove completamente o grupo do sistema\n"
            "- Não afeta as rotas em si, apenas a associação\n"
            "- Operação irreversível\n"
            "### Permissões:\n"
            "- Apenas o proprietário do grupo pode excluí-lo\n"
            "### Observações:\n"
            "- Esta operação não pode ser desfeita\n"
            "- Verifique dependências antes da exclusão"
        ),
        responses={
            204: {"description": "Grupo excluído com sucesso"},
            404: {"description": "Grupo não encontrado ou não pertence ao usuário"},
            401: {"description": "Credenciais de autenticação não fornecidas ou inválidas"},
            403: {"description": "Usuário não tem permissão para excluir este grupo"}
        }
    )
)
class GrupoRotaSistemaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, UsuarioIndependenteOuAdmin]
    serializer_class = GrupoRotaSistemaListSerializer

    def get_queryset(self):
        return GrupoRotaSistema.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        """Usa serializer diferente para diferentes métodos."""
        if self.request.method == 'GET':
            return GrupoRotaSistemaListSerializer
        return GrupoRotaSistemaCreateSerializer  # Para PUT/PATCH

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
