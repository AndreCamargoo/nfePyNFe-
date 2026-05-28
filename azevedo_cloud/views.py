from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from empresa.models import Empresa, Funcionario

from azevedo_cloud.models import Segmento, Subpasta, Arquivo, Circularizacao
from azevedo_cloud.serializers import (
    SegmentoListSerializer, SegmentoCreateUpdateSerializer, SegmentoDetailSerializer,
    SubpastaSerializer, SubpastaCreateUpdateSerializer,
    ArquivoSerializer, ArquivoCreateSerializer,
    CircularizacaoListSerializer, CircularizacaoCreateSerializer,
    CircularizacaoUpdateSerializer, CircularizacaoDetailSerializer,
    FuncionarioListSerializer, EmpresaListSerializer
)

from app.permissions import (
    AcessoAzevedoCloudPermission,
    PermissaoSegmento,
    PodeCriarSegmento,
    PermissaoArquivo,
    PodeGerenciarSegmento,
)

from app.utils import utils
from django_filters.rest_framework import DjangoFilterBackend
from azevedo_cloud.filters import SegmentoFilter


# ==================== VIEWS PARA SEGMENTO ====================
class SegmentoListCreateAPIView(generics.ListCreateAPIView):
    """Lista e cria segmentos (pastas raiz)"""

    filter_backends = [DjangoFilterBackend]
    filterset_class = SegmentoFilter
    pagination_class = utils.CustomPageSizePagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), AcessoAzevedoCloudPermission(), PodeCriarSegmento()]
        return [IsAuthenticated(), AcessoAzevedoCloudPermission()]

    def get_queryset(self):
        user = self.request.user
        funcionario = Funcionario.objects.filter(user=user, status='1').first()

        if not funcionario:
            return Segmento.objects.none()

        return Segmento.objects.filter(
            Q(empresa_auditoria=funcionario.empresa) | Q(clientes=funcionario.empresa) | Q(responsaveis=funcionario)).distinct()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SegmentoCreateUpdateSerializer
        return SegmentoListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        if hasattr(self.request, 'current_funcionario'):
            funcionario = self.request.current_funcionario
        else:
            funcionario = Funcionario.objects.filter(
                user=self.request.user,
                status='1'
            ).select_related('empresa').first()

        if not funcionario:
            raise PermissionDenied("Você não está vinculado a nenhuma empresa ativa.")

        serializer.save(empresa_auditoria=funcionario.empresa)


class SegmentoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Detalha, atualiza e deleta um segmento"""

    def get_permissions(self):
        # Para DELETE: precisa de permissão de gerenciamento
        if self.request.method == 'DELETE':
            return [
                IsAuthenticated(),
                AcessoAzevedoCloudPermission(),
                PodeGerenciarSegmento()
            ]
        # Para GET, PUT, PATCH: usa a permissão de objeto existente
        return [
            IsAuthenticated(),
            AcessoAzevedoCloudPermission(),
            PermissaoSegmento()
        ]

    queryset = Segmento.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SegmentoDetailSerializer
        return SegmentoCreateUpdateSerializer


# ==================== VIEWS PARA SUBPASTA ====================
class SubpastaListCreateAPIView(generics.ListCreateAPIView):
    """Lista e cria subpastas"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get_queryset(self):
        segmento_id = self.request.query_params.get('segmento_id')
        if segmento_id:
            return Subpasta.objects.filter(segmento_id=segmento_id)
        return Subpasta.objects.none()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SubpastaCreateUpdateSerializer
        return SubpastaSerializer

    def perform_create(self, serializer):
        segmento_id = self.request.data.get('segmento')
        segmento = get_object_or_404(Segmento, id=segmento_id)

        # Verifica permissão
        permission = PermissaoSegmento()
        if not permission.has_object_permission(self.request, self, segmento):
            raise PermissionDenied("Você não tem permissão para adicionar subpastas a este segmento.")

        serializer.save()


class SubpastaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Detalha, atualiza e deleta uma subpasta"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]
    queryset = Subpasta.objects.all()
    serializer_class = SubpastaCreateUpdateSerializer

    def perform_destroy(self, instance):
        # Verifica permissão no segmento pai
        permission = PermissaoSegmento()
        if not permission.has_object_permission(self.request, self, instance.segmento):
            raise PermissionDenied("Você não tem permissão para deletar esta subpasta.")
        instance.delete()


# ==================== VIEWS PARA PERMISSÃO DE USUARIO EM SEGMENTO ====================
class PermissaoUsuarioSegmentoListAPIView(generics.ListAPIView):
    serializer_class = FuncionarioListSerializer
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get_queryset(self):
        # Retorna os funcionários apenas das empresas em que o usuário está vinculado
        # (considerando o usuário logado, mas queremos todos os funcionários da empresa dele?)
        # Ajuste conforme sua regra de negócio.
        return Funcionario.objects.filter(empresa__in=self.request.user.empresas.all())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['segmento_id'] = self.request.query_params.get('segmento_id')
        return context


# ==================== VIEWS PARA PERMISSÃO DE USUARIO EM SEGMENTO ====================
class ListCompanyListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]
    serializer_class = EmpresaListSerializer

    def get_queryset(self):
        return Empresa.objects.filter(
            sistemas__sistema_id=1,
            sistemas__ativo=True,
            status='1'
        ).distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['segmento_id'] = self.request.query_params.get('segmento_id')
        return context


# ==================== VIEWS PARA ARQUIVO ====================

class ArquivoListCreateAPIView(generics.ListCreateAPIView):
    """Lista e cria arquivos"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get_queryset(self):
        subpasta_id = self.request.query_params.get('subpasta_id')
        if subpasta_id:
            return Arquivo.objects.filter(subpasta_id=subpasta_id)
        return Arquivo.objects.none()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ArquivoCreateSerializer
        return ArquivoSerializer

    def perform_create(self, serializer):
        subpasta_id = self.request.data.get('subpasta')
        subpasta = get_object_or_404(Subpasta, id=subpasta_id)

        # Verifica permissão
        permission = PermissaoSegmento()
        if not permission.has_object_permission(self.request, self, subpasta.segmento):
            raise PermissionDenied("Você não tem permissão para enviar arquivos para esta pasta.")

        serializer.save()


class ArquivoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Detalha, atualiza e deleta um arquivo"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission, PermissaoArquivo]
    queryset = Arquivo.objects.all()
    serializer_class = ArquivoSerializer

    def perform_destroy(self, instance):
        instance.delete()


# ==================== VIEWS PARA CIRCULARIZAÇÃO ====================

class CircularizacaoListCreateAPIView(generics.ListCreateAPIView):
    """Lista e cria circularizações (links externos)"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get_queryset(self):
        user = self.request.user
        funcionario = Funcionario.objects.filter(user=user, status='1').first()

        if not funcionario:
            return Circularizacao.objects.none()

        # Se for cliente, mostra apenas suas circularizações
        if funcionario.role == Funcionario.CLIENTE_EXTERNO:
            return Circularizacao.objects.filter(cliente=funcionario.empresa)

        # Se for auditoria, mostra todas que pertencem à sua empresa
        return Circularizacao.objects.filter(segmento__empresa_auditoria=funcionario.empresa)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CircularizacaoCreateSerializer
        return CircularizacaoListSerializer


class CircularizacaoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Detalha, atualiza e deleta uma circularização"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]
    queryset = Circularizacao.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CircularizacaoDetailSerializer
        elif self.request.method in ['PUT', 'PATCH']:
            return CircularizacaoUpdateSerializer
        return CircularizacaoListSerializer

    def perform_destroy(self, instance):
        # Deleta também o segmento associado
        segmento = instance.segmento
        instance.delete()
        segmento.delete()


# ==================== VIEWS PARA NAVEGAÇÃO (DEEP LINKS) ====================

class ClientesComAcessoAPIView(APIView):
    """Retorna clientes que têm acesso a segmentos do usuário"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get(self, request):
        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return Response([])

        # Busca empresas clientes vinculadas aos segmentos da auditoria
        segmentos = Segmento.objects.filter(empresa_auditoria=funcionario.empresa)
        clientes_ids = set()
        for seg in segmentos:
            for cliente in seg.clientes.all():
                clientes_ids.add(cliente.id)

        # Busca os detalhes dos clientes
        clientes = Empresa.objects.filter(id__in=clientes_ids, status='1')

        result = []
        for cliente in clientes:
            segmentos_cliente = segmentos.filter(clientes=cliente)
            arquivos_count = Arquivo.objects.filter(
                cliente=cliente,
                subpasta__segmento__in=segmentos_cliente
            ).count()

            result.append({
                'id': cliente.id,
                'nome': cliente.razao_social,
                'segmentos_count': segmentos_cliente.count(),
                'arquivos_count': arquivos_count
            })

        return Response(result)


class NavegacaoSegmentoAPIView(APIView):
    """Retorna a estrutura de navegação para um cliente específico"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get(self, request, cliente_id):
        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return Response([])

        cliente = get_object_or_404(Empresa, id=cliente_id, status='1')

        # Busca segmentos que o cliente tem acesso
        segmentos = Segmento.objects.filter(
            Q(empresa_auditoria=funcionario.empresa) |
            Q(clientes=cliente)
        ).filter(clientes=cliente).distinct()

        result = []
        for segmento in segmentos:
            subpastas = segmento.subpastas.all()
            total_subpastas = subpastas.count()
            subpastas_com_arquivos = 0

            for subpasta in subpastas:
                if Arquivo.objects.filter(subpasta=subpasta, cliente=cliente).exists():
                    subpastas_com_arquivos += 1

            progresso = (subpastas_com_arquivos / total_subpastas * 100) if total_subpastas > 0 else 0

            result.append({
                'id': segmento.id,
                'nome': segmento.nome,
                'ano': segmento.ano,
                'is_circ': segmento.is_circ,
                'progresso': round(progresso, 2),
                'subpastas': SubpastaSerializer(subpastas, many=True).data
            })

        return Response(result)


class SubpastaArquivosAPIView(APIView):
    """Retorna os arquivos de uma subpasta para um cliente específico"""
    permission_classes = [IsAuthenticated, AcessoAzevedoCloudPermission]

    def get(self, request, subpasta_id, cliente_id):
        funcionario = Funcionario.objects.filter(user=request.user, status='1').first()
        if not funcionario:
            return Response([])

        subpasta = get_object_or_404(Subpasta, id=subpasta_id)
        cliente = get_object_or_404(Empresa, id=cliente_id, status='1')

        # Verifica permissão
        if subpasta.segmento.empresa_auditoria != funcionario.empresa and \
           not subpasta.segmento.clientes.filter(id=cliente_id).exists():
            raise PermissionDenied("Você não tem acesso a esta pasta.")

        arquivos = Arquivo.objects.filter(subpasta=subpasta, cliente=cliente)
        return Response(ArquivoSerializer(arquivos, many=True).data)


# ==================== VIEWS PARA ACESSO CONVIDADO (LINK EXTERNO) ====================

class GuestAcessoCircularizacaoAPIView(APIView):
    """Acesso público via link de circularização (não requer autenticação)"""
    permission_classes = []

    def get(self, request, uuid):
        circularizacao = get_object_or_404(Circularizacao, id_uuid=uuid, status='ativo')
        segmento = circularizacao.segmento

        # Retorna informações básicas para o frontend guest
        return Response({
            'circularizacao_id': circularizacao.id,
            'uuid': str(circularizacao.id_uuid),
            'cliente_id': circularizacao.cliente.id,
            'cliente_nome': circularizacao.cliente.razao_social,
            'ano': circularizacao.ano,
            'segmento_id': segmento.id,
            'segmento_nome': segmento.nome,
            'subpastas': SubpastaSerializer(segmento.subpastas.all(), many=True).data
        })

    def post(self, request, uuid):
        """Envio de arquivo via link convidado"""
        circularizacao = get_object_or_404(Circularizacao, id_uuid=uuid, status='ativo')

        serializer = ArquivoCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(
                subpasta_id=request.data.get('subpasta_id'),
                cliente=circularizacao.cliente,
                nome_remetente=request.data.get('nome_remetente', 'Visitante')
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
