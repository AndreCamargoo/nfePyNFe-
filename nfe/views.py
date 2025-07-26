import os
import re
from pathlib import Path

from django_filters.rest_framework import DjangoFilterBackend
from django.db import connection
from django.conf import settings

from rest_framework import generics, status, response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

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
from brazilfiscalreport.danfe import Danfe


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
    pagination_class = utils.CustomPageSizePagination

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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if not queryset.exists():
            return response.Response(
                {'message': 'Nenhum produto encontrado'},
                status=status.HTTP_204_NO_CONTENT
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return response.Response(serializer.data)


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

        fornecedores = models.Emitente.objects.filter(nota_fiscal__in=filtered_nfe).order_by('CNPJ').distinct('CNPJ')

        if fornecedores.exists():
            return fornecedores


class NfeFornecedorDetailListAPIView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = models.Emitente.objects.all()
    serializer_class = EmitenteModelSerializer


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

        order = str(request.query_params.get("order", ""))
        limit = request.query_params.get("limit")
        search = request.query_params.get("q", "")
        offset = request.query_params.get("offset")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_produtos_empresa(%s, %s, %s, %s, %s)",
                [empresa_id, order, limit, search, offset]
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


class GerarDanfeAPIView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = models.NotaFiscal.objects.all()

    @staticmethod
    def _gerar_danfe_pdf(xml_file_path, pasta_saida='media/danfe'):
        """Gera e salva o PDF da DANFE a partir do XML."""
        if not os.path.exists(pasta_saida):
            os.makedirs(pasta_saida)

        with open(xml_file_path, "r", encoding="utf8") as file:
            xml_content = file.read()

        nome_base = os.path.splitext(os.path.basename(xml_file_path))[0]
        caminho_pdf = os.path.join(pasta_saida, f'{nome_base}.pdf')

        danfe = Danfe(xml=xml_content)
        danfe.output(caminho_pdf)

        return caminho_pdf

    def get(self, request, *args, **kwargs):
        nota_fiscal = self.get_object()

        if not nota_fiscal.fileXml:
            return response.Response(
                {'error': 'Arquivo XML não encontrado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Corrige possíveis barras invertidas salvas incorretamente no caminho
            xml_file_name = nota_fiscal.fileXml.name.replace('\\', '/')
            xml_file_path = os.path.join(settings.MEDIA_ROOT, xml_file_name)

            # Verifica se já existe PDF gerado e válido
            if nota_fiscal.filePdf and nota_fiscal.filePdf.path and os.path.exists(nota_fiscal.filePdf.path):
                return response.Response({
                    'message': 'DANFE já gerado anteriormente.',
                    'pdf_path': request.build_absolute_uri(nota_fiscal.filePdf.url)
                }, status=status.HTTP_200_OK)

            # Gera o PDF
            pdf_path = self._gerar_danfe_pdf(xml_file_path, pasta_saida='media/danfe')

            # Resolve os caminhos para salvar no FileField
            pdf_path_absolute = Path(os.path.abspath(pdf_path))
            media_root_path = Path(settings.MEDIA_ROOT).resolve()
            relative_path = pdf_path_absolute.relative_to(media_root_path)

            # Salva o novo caminho do PDF no objeto
            nota_fiscal.filePdf.name = str(relative_path)
            nota_fiscal.save()

            return response.Response({
                'message': 'DANFE gerado com sucesso!',
                'pdf_path': request.build_absolute_uri(nota_fiscal.filePdf.url)
            }, status=status.HTTP_200_OK)

        except FileNotFoundError as fnf:
            return response.Response(
                {'error': f'Arquivo XML não encontrado no caminho: {xml_file_path}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return response.Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
