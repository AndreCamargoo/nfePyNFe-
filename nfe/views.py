import re
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import connection

from empresa.models import Empresa
from .filters import (
    NotaFiscalFilter, ProdutoFilter, FornecedorFilter
)
from . import models
from . import utils
from app.permissions import GlobalDefaultPermission
from nfe.serializer import (
    NfeSerializer, NfeModelSerializer, ProdutoModelSerializer,
    EmitenteModelSerializer, NfeFaturamentoOutputSerializer,
    NfeFaturamentoMesOutputSerializer, NfeProdutosOutputSerializer
)
from nfe.processor.nfe_processor import NFeProcessor

from datetime import datetime


class NfeListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = models.NotaFiscal.objects.order_by('-pk').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NfeSerializer
        return NfeModelSerializer

    def post(self, request, *args, **kwargs):
        try:
            empresa_id = request.data.get('empresa_id')
            xml_string_raw = request.data.get('xml')
            nsu = request.data.get('nsu')
            fileXml = request.data.get('fileXml')

            if not empresa_id or not xml_string_raw or not nsu:
                return response.Response({'error': 'empresa_id, xml e nsu são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

            empresa = Empresa.objects.filter(pk=empresa_id).first()
            if not empresa:
                return response.Response({'error': 'Empresa não encontrada.'}, status=status.HTTP_400_BAD_REQUEST)

            # Limpeza da string XML
            xml_clean = str(xml_string_raw).replace('\\"', '"').replace('\n', '').replace('\r', '').replace('\t', '')
            xml_clean = re.sub(r'\s+', ' ', xml_clean).strip()

            processor = NFeProcessor(empresa, xml_clean, nsu, fileXml)
            nota = processor.processar(debug=False)

            return response.Response({
                'message': 'XML processado com sucesso!',
                'chave': nota.chave,
                'versao': nota.versao
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return response.Response({'error': f'Ocorreu um erro inesperado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NfeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = models.NotaFiscal.objects.all()
    serializer_class = NfeModelSerializer


class NfeListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NfeModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotaFiscalFilter

    def get_queryset(self):
        user = self.request.user
        documento = self.kwargs.get('documento', None)
        empresas_filtradas = utils.get_empresas_filtradas(user=user, documento=documento)

        nfe = models.NotaFiscal.objects.filter(empresa__in=empresas_filtradas).distinct()

        if nfe.exists():
            return nfe

        return response.Response(
            {'message': 'Nenhum registro encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )


class NfeProdutosListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProdutoModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProdutoFilter

    def get_queryset(self):
        user = self.request.user
        documento = self.kwargs.get('documento', None)
        empresas_filtradas = utils.get_empresas_filtradas(user=user, documento=documento)

        # Filtrando as Notas Fiscais pela empresa, e usando prefetch_related para evitar consultas N+1
        nfe = models.NotaFiscal.objects.filter(empresa__in=empresas_filtradas).distinct().prefetch_related('produtos')

        # Aplicando o filtro usando o Django Filter
        filtered_nfe = NotaFiscalFilter(self.request.GET, queryset=nfe).qs

        # Agora pegamos os produtos relacionados às Notas Fiscais filtradas
        produtos = models.Produto.objects.filter(nota_fiscal__in=filtered_nfe)  # Filtrando produtos das NFe filtradas

        # Se há produtos encontrados
        if produtos.exists():
            # Retorna os produtos encontrados
            return produtos

        return response.Response(
            {'message': 'Nenhum produto encontrado'},
            status=status.HTTP_204_NO_CONTENT
        )


class NfeFornecedorListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmitenteModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = FornecedorFilter

    def get_queryset(self):
        user = self.request.user
        documento = self.kwargs.get('documento', None)
        empresas_filtradas = utils.get_empresas_filtradas(user=user, documento=documento)

        nfe = models.NotaFiscal.objects.filter(empresa__in=empresas_filtradas).distinct().prefetch_related('emitente')

        filtered_nfe = NotaFiscalFilter(self.request.GET, queryset=nfe).qs

        fornecedores = models.Emitente.objects.filter(nota_fiscal__in=filtered_nfe)

        if fornecedores.exists():
            return fornecedores


class NfeFaturamentoAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id  # ajusta conforme seu modelo

        # Mês e ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        mes = int(request.query_params.get("mes", now.month))
        ano = int(request.query_params.get("ano", now.year))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM calcular_faturamento_nfe(%s, %s, %s)",
                [empresa_id, mes, ano]
            )
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()

        if row is None:
            return response.Response({}, status=204)  # Nenhum dado

        data_dict = dict(zip(columns, row))
        serializer = NfeFaturamentoOutputSerializer(data_dict)

        return response.Response(serializer.data)


class NfeFaturamentoMesAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id  # ajusta conforme seu modelo

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        ano = int(request.query_params.get("ano", now.year))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM calcular_faturamento_nfe_por_mes(%s, %s)",
                [empresa_id, ano]
            )
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()

        if row is None:
            return response.Response({}, status=204)  # Nenhum dado

        data_dict = dict(zip(columns, row))
        serializer = NfeFaturamentoMesOutputSerializer(data_dict)

        return response.Response(serializer.data)


class NfeProdutosAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id  # ajusta conforme seu modelo

        order = str(request.query_params.get("order", ''))
        limit = int(request.query_params.get("limit", 10))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_produtos_empresa(%s, %s, %s)",
                [empresa_id, order, limit]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()  # Usando fetchall para pegar todas as linhas

        if not rows:
            return response.Response([], status=204)  # Nenhum dado

        # Converte todas as linhas em um dicionário
        data_list = [dict(zip(columns, row)) for row in rows]

        # Serializa a lista de dicionários
        serializer = NfeProdutosOutputSerializer(data_list, many=True)

        return response.Response(serializer.data)
