from django.db.models import Q

from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from empresa.models import Empresa, CategoriaEmpresa, ConexaoBanco
from empresa.serializer import (
    EmpresaCreateSerializer, EmpresaUpdateSerializer, EmpresaListSerializer,
    CategoriaEmpresaModelSerializer, ConexaoBancoModelSerializer
)

from app.permissions import GlobalDefaultPermission

from drf_spectacular.utils import extend_schema, extend_schema_view


class EmpresaBaseView:
    """Classe base com configurações comuns"""
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return Empresa.objects.filter(
            Q(usuario=user) | Q(matriz_filial__usuario=user)
        ).distinct()


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

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return EmpresaUpdateSerializer
        return EmpresaListSerializer

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


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
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)


class ConexaoBancoListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ConexaoBancoModelSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    # def get_queryset(self):
    #     user = self.request.user
    #     conexao_queryset = ConexaoBanco.objects.filter(empresa__usuario=user).first()

    #     # for conexao in conexao_queryset:
    #     #     print(
    #     #         conexao.get_host(),
    #     #         conexao.get_porta(),
    #     #         conexao.get_usuario(),
    #     #         conexao.get_database(),
    #     #         conexao.get_senha(),
    #     #         user
    #     #     )

    #     return conexao_queryset

    def get_queryset(self):
        user = self.request.user
        conexao_queryset = ConexaoBanco.objects.filter(empresa__usuario=user).first()

        # Retornando o único objeto dentro de uma lista
        return [conexao_queryset] if conexao_queryset else []

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user

        try:
            empresa = Empresa.objects.filter(
                usuario=user,
                matriz_filial__isnull=True,  # É matriz
                status='1'  # Ativa
            ).first()

            if not empresa:
                raise ValidationError('Empresa matriz ativa não encontrada para o usuário.')

        except Empresa.DoesNotExist:
            raise ValidationError('Empresa não encontrada para o usuário.')

        context['empresa'] = empresa
        return context
