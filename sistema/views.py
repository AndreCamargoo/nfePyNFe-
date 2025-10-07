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
        tags=["Grupos de Permissões"],
        operation_id="01_listar_grupos_permissoes",
        summary="01 Listar grupos de permissões da empresa",
        description=(
            "Retorna todos os grupos de permissões criados pela empresa para gerenciar acesso de funcionários.\n\n"
            "### Funcionalidades:\n"
            "- Lista de grupos de permissões personalizados da empresa\n"
            "- Visualização das rotas e endpoints associados a cada grupo\n"
            "- Base para atribuição de permissões a funcionários\n"
            "- Controle granular de acesso por módulos do sistema\n\n"
            "### Caso de Uso:\n"
            "A empresa cria grupos como 'Administrador', 'Financeiro', 'Operacional' com diferentes conjuntos \n"
            "de permissões, depois associa esses grupos aos funcionários conforme suas funções.\n\n"
            "### Exemplos Práticos:\n"
            "- **Grupo Administrador**: Todas as rotas do sistema\n"
            "- **Grupo Financeiro**: Apenas módulos financeiros e relatórios\n"
            "- **Grupo Vendas**: Módulos de pedidos, clientes e CRM\n"
            "- **Grupo Consulta**: Apenas visualização de dados\n\n"
            "### Permissões:\n"
            "- Apenas usuários autenticados da empresa matriz\n"
            "- Administradores da empresa"
        ),
        responses={
            200: GrupoRotaSistemaListSerializer(many=True),
            401: {"description": "Credenciais de autenticação não fornecidas"},
            403: {"description": "Acesso restrito à empresa matriz"}
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta - Grupos da empresa',
                value=[
                    {
                        "id": 1,
                        "nome": "Administradores",
                        "descricao": "Acesso total a todos os módulos do sistema",
                        "sistema": {
                            "id": 1,
                            "nome": "ERP Corporativo"
                        },
                        "rotas": [
                            {
                                "id": 1,
                                "nome": "Gestão de Usuários",
                                "path": "/api/usuarios/",
                                "metodo": "GET,POST,PUT,DELETE",
                                "descricao": "Gerenciamento completo de usuários"
                            },
                            {
                                "id": 2,
                                "nome": "Relatórios Financeiros",
                                "path": "/api/financeiro/relatorios/",
                                "metodo": "GET,POST",
                                "descricao": "Geração e visualização de relatórios"
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "nome": "Equipe Financeira",
                        "descricao": "Acesso aos módulos financeiros e contábeis",
                        "sistema": {
                            "id": 1,
                            "nome": "ERP Corporativo"
                        },
                        "rotas": [
                            {
                                "id": 2,
                                "nome": "Relatórios Financeiros",
                                "path": "/api/financeiro/relatorios/",
                                "metodo": "GET,POST",
                                "descricao": "Geração e visualização de relatórios"
                            },
                            {
                                "id": 3,
                                "nome": "Contas a Pagar/Receber",
                                "path": "/api/financeiro/contas/",
                                "metodo": "GET,POST,PUT",
                                "descricao": "Gestão de contas financeiras"
                            }
                        ]
                    }
                ],
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        tags=["Grupos de Permissões"],
        operation_id="02_criar_grupo_permissoes",
        summary="02 Criar novo grupo de permissões",
        description=(
            "Cria um novo grupo de permissões para definir quais rotas os funcionários podem acessar.\n\n"
            "### Fluxo de Configuração:\n"
            "1. Empresa cria um grupo (ex: 'Coordenadores')\n"
            "2. Seleciona as rotas que esse grupo pode acessar\n"
            "3. Associa funcionários a este grupo\n"
            "4. Funcionários herdam as permissões do grupo\n\n"
            "### Casos de Uso Comuns:\n"
            "```json\n"
            "{\n"
            "  \"nome\": \"Supervisores\",\n"
            "  \"descricao\": \"Acesso a gestão de equipe e relatórios\",\n"
            "  \"sistema\": 1,\n"
            "  \"rotas\": [10, 15, 20, 25]\n"
            "}\n"
            "```\n\n"
            "### Validações:\n"
            "- Nome deve ser único por empresa\n"
            "- Rotas devem pertencer ao sistema selecionado\n"
            "- Sistema deve estar ativo para a empresa\n\n"
            "### Permissões:\n"
            "- Apenas administradores da empresa matriz"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            201: GrupoRotaSistemaListSerializer,
            400: {
                "description": "Erros de validação",
                "examples": {
                    "rotas_sistema_invalido": {
                        "value": {
                            "error": "Algumas rotas não pertencem ao sistema selecionado"
                        }
                    },
                    "nome_duplicado": {
                        "value": {
                            "nome": "Já existe um grupo com este nome"
                        }
                    }
                }
            },
            401: {"description": "Credenciais de autenticação não fornecidas"},
            403: {"description": "Apenas administradores podem criar grupos"}
        },
        examples=[
            OpenApiExample(
                'Exemplo 1 - Grupo Administrativo',
                value={
                    "nome": "Administradores",
                    "descricao": "Acesso completo a todas as funcionalidades",
                    "sistema": 1,
                    "rotas": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
                },
                request_only=True,
                description="Grupo com acesso total ao sistema"
            ),
            OpenApiExample(
                'Exemplo 2 - Grupo Operacional',
                value={
                    "nome": "Equipe Operacional",
                    "descricao": "Acesso às funcionalidades do dia a dia",
                    "sistema": 1,
                    "rotas": [3, 4, 7, 8]
                },
                request_only=True,
                description="Grupo com acesso limitado às operações rotineiras"
            ),
            OpenApiExample(
                'Exemplo de resposta - Grupo criado',
                value={
                    "id": 3,
                    "nome": "Equipe Financeira",
                    "descricao": "Acesso aos módulos financeiros",
                    "sistema": {
                        "id": 1,
                        "nome": "ERP Corporativo"
                    },
                    "rotas": [
                        {
                            "id": 2,
                            "nome": "Relatórios Financeiros",
                            "path": "/api/financeiro/relatorios/",
                            "metodo": "GET,POST",
                            "descricao": "Geração de relatórios financeiros"
                        },
                        {
                            "id": 5,
                            "nome": "Conciliação Bancária",
                            "path": "/api/financeiro/conciliacao/",
                            "metodo": "GET,POST,PUT",
                            "descricao": "Conciliação de extratos bancários"
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
        tags=["Grupos de Permissões"],
        operation_id="03_visualizar_grupo_permissoes",
        summary="03 Visualizar detalhes do grupo de permissões",
        description=(
            "Retorna os detalhes completos de um grupo de permissões específico.\n"
            "### Utilização:\n"
            "- Verificar quais permissões um grupo possui\n"
            "- Validar configurações antes de associar funcionários\n"
            "- Auditoria de acessos concedidos\n"
            "### Informações Incluídas:\n"
            "- Lista completa de rotas permitidas\n"
            "- Metadados do sistema\n"
            "- Descrição e finalidade do grupo\n"
            "### Permissões:\n"
            "- Apenas administradores da empresa dona do grupo"
        ),
        responses={
            200: GrupoRotaSistemaListSerializer,
            404: {"description": "Grupo não encontrado ou não pertence à empresa"},
            403: {"description": "Acesso permitido apenas à empresa proprietária"}
        },
        examples=[
            OpenApiExample(
                'Exemplo - Grupo de Coordenadores',
                value={
                    "id": 4,
                    "nome": "Coordenadores",
                    "descricao": "Acesso a gestão de equipes e indicadores",
                    "sistema": {
                        "id": 1,
                        "nome": "ERP Corporativo"
                    },
                    "rotas": [
                        {
                            "id": 6,
                            "nome": "Gestão de Equipe",
                            "path": "/api/rh/equipe/",
                            "metodo": "GET,POST,PUT",
                            "descricao": "Gerenciamento de membros da equipe"
                        },
                        {
                            "id": 7,
                            "nome": "Indicadores de Performance",
                            "path": "/api/indicadores/",
                            "metodo": "GET",
                            "descricao": "Visualização de KPIs e métricas"
                        },
                        {
                            "id": 8,
                            "nome": "Relatórios Gerenciais",
                            "path": "/api/relatorios/gerenciais/",
                            "metodo": "GET,POST",
                            "descricao": "Relatórios para tomada de decisão"
                        }
                    ],
                    "usuario": 1
                },
                response_only=True,
                description="Exemplo de grupo para coordenadores com acesso a gestão"
            )
        ]
    ),
    put=extend_schema(
        tags=["Grupos de Permissões"],
        operation_id="04_atualizar_grupo_permissoes",
        summary="04 Atualizar grupo de permissões",
        description=(
            "Atualiza completamente as permissões de um grupo existente.\n"
            "### Cenários de Uso:\n"
            "- Adicionar novas rotas a um grupo existente\n"
            "- Remover permissões não mais necessárias\n"
            "- Corrigir configurações de acesso\n"
            "- Expandir/restringir permissões do grupo\n"
            "### Impacto:\n"
            "- Todas as alterações afetam imediatamente os funcionários associados\n"
            "- Recomendado comunicar mudanças aos usuários afetados\n"
            "### Permissões:\n"
            "- Apenas administradores da empresa proprietária"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            200: GrupoRotaSistemaListSerializer,
            400: {"description": "Dados inválidos ou rotas incompatíveis"},
            404: {"description": "Grupo não encontrado"}
        },
        examples=[
            OpenApiExample(
                'Exemplo - Adicionar permissões financeiras',
                value={
                    "nome": "Coordenadores Expandido",
                    "descricao": "Acesso ampliado para incluir módulo financeiro",
                    "sistema": 1,
                    "rotas": [6, 7, 8, 2, 5]  # Adicionando rotas financeiras
                },
                request_only=True,
                description="Expansão de permissões para incluir módulo financeiro"
            )
        ]
    ),
    patch=extend_schema(
        tags=["Grupos de Permissões"],
        operation_id="05_atualizar_parcial_grupo_permissoes",
        summary="05 Atualização parcial do grupo",
        description=(
            "Atualiza apenas campos específicos do grupo de permissões.\n"
            "### Casos de Uso:\n"
            "- Renomear grupo sem alterar permissões\n"
            "- Atualizar descrição do grupo\n"
            "- Adicionar/remover rotas específicas\n"
            "- Corrigir pequenos ajustes\n"
            "### Vantagens:\n"
            "- Não precisa enviar todos os dados\n"
            "- Menor risco de erro\n"
            "- Mais eficiente para pequenas mudanças\n"
            "### Permissões:\n"
            "- Apenas administradores da empresa proprietária"
        ),
        request=GrupoRotaSistemaCreateSerializer,
        responses={
            200: GrupoRotaSistemaListSerializer,
            400: {"description": "Dados inválidos"},
            404: {"description": "Grupo não encontrado"}
        },
        examples=[
            OpenApiExample(
                'Exemplo 1 - Apenas renomear',
                value={
                    "nome": "Líderes de Equipe"
                },
                request_only=True,
                description="Apenas alterando o nome do grupo"
            ),
            OpenApiExample(
                'Exemplo 2 - Adicionar rotas',
                value={
                    "rotas": [6, 7, 8, 9]
                },
                request_only=True,
                description="Apenas atualizando a lista de rotas"
            )
        ]
    ),
    delete=extend_schema(
        tags=["Grupos de Permissões"],
        operation_id="06_excluir_grupo_permissoes",
        summary="06 Excluir grupo de permissões",
        description=(
            "Remove permanentemente um grupo de permissões do sistema.\n\n"
            "### Verificações de Segurança:\n"
            "- Grupo não pode estar associado a funcionários ativos\n"
            "- Backup das configurações é recomendado\n"
            "- Operação irreversível\n\n"
            "### Fluxo Recomendado:\n"
            "1. Verificar funcionários associados ao grupo\n"
            "2. Migrar funcionários para outro grupo se necessário\n"
            "3. Confirmar exclusão\n"
            "4. Registrar a ação no log do sistema\n\n"
            "### Permissões:\n"
            "- Apenas administradores da empresa proprietária\n"
            "- Grupo não pode ter funcionários associados"
        ),
        responses={
            204: {"description": "Grupo excluído com sucesso"},
            400: {
                "description": "Grupo não pode ser excluído",
                "examples": {
                    "grupo_com_funcionarios": {
                        "value": {
                            "error": "Não é possível excluir grupo com funcionários associados"
                        }
                    }
                }
            },
            404: {"description": "Grupo não encontrado"}
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
