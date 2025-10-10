from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiExample, OpenApiResponse
import os
from pathlib import Path

from datetime import datetime
from brazilfiscalreport.danfe import Danfe

from django.db.models import Q

from django_filters.rest_framework import DjangoFilterBackend
from django.db import connection
from django.conf import settings

from rest_framework import generics, status, response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from rest_framework.views import APIView

from . import models
from app.utils import utils

from empresa.models import (
    Empresa, HistoricoNSU, Funcionario
)
from .filters import (
    NotaFiscalFilter, ProdutoFilter, FornecedorFilter
)

from nfe.serializer import (
    NfeSerializer, NfeModelSerializer, ProdutoModelSerializer,
    EmitenteModelSerializer, NfeFaturamentoOutputSerializer,
    NfeFaturamentoMesOutputSerializer, NfeProdutosOutputSerializer
)
from nfe.processor.nfe_processor import NFeProcessor
from nfe.processor.nfe_lote_zip import NFeLoteProcessor

from app.permissions import PodeAcessarRotasFuncionario

from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes


class NFeBaseView:
    """Classe base com configurações comuns"""

    def get_permissions(self):
        return [IsAuthenticated(), PodeAcessarRotasFuncionario()]

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.NotaFiscal.objects.none()

        user = self.request.user

        try:
            # Verifica se é funcionário ativo
            funcionario = Funcionario.objects.filter(
                user=user,
                status='1',
                role='funcionario',
                empresa__sistema_id=3
            ).select_related('empresa').first()

            if funcionario:
                empresa = funcionario.empresa

                # Verifica se a empresa ainda está ativa
                if empresa.status != '1':
                    raise PermissionDenied(
                        detail="A empresa vinculada à sua conta está inativa. "
                               "O acesso a esta funcionalidade foi bloqueado."
                    )

                verificaEmpresa = utils.verificaRestricaoAdministrativa(empresa.id, 3)
                if not verificaEmpresa:
                    raise PermissionDenied(
                        detail="A empresa vinculada à sua conta está desativada, contate um administrador."
                    )

                # Funcionário ativo + empresa / filial ativa → retorna notas
                return models.NotaFiscal.objects.filter(
                    Q(empresa_id=empresa.id) |  # Notas da matriz
                    Q(empresa__matriz_filial_id=empresa.id),  # Notas das filiais
                    deleted_at__isnull=True
                ).order_by('-dhEmi')

        except PermissionDenied:
            raise  # Repassa a exceção corretamente
        except Exception:
            return models.NotaFiscal.objects.none()

        empresa_usuario = Empresa.objects.filter(usuario=user, sistema=3).first()

        if not empresa_usuario:
            return models.NotaFiscal.objects.none()

        # Verifica restrição administrativa para cada empresa do usuário
        verificaEmpresa = utils.verificaRestricaoAdministrativa(empresa_usuario.id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        return models.NotaFiscal.objects.filter(
            Q(empresa__usuario=user) |  # Matrizes do usuário
            Q(empresa__matriz_filial__usuario=user),  # Filiais de matrizes do usuário
            deleted_at__isnull=True,
            empresa__sistema=3
        ).order_by('-dhEmi')


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF"],
        operation_id="01_listar_notas_fisicais",
        summary="01 Listar notas fiscais",
        description="""
        Retorna uma lista paginada de notas fiscais da matriz e todas filiais com filtros avançados.
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        
        **Filtros disponíveis:**
        - `ide_cUF`: Código da UF do emitente
        - `emitente_nome`: Nome do emitente
        - `chave`: Chave da nota fiscal
        - `dhEmi`: Data de emissão (range: dhEmi_after & dhEmi_before)
        - `emitente_CNPJ`: CNPJ do emitente
        - `emitente_xNome`: Razão social do emitente
        - `q`: Pesquisa geral (CNPJ, nome ou chave)
        """,
        parameters=[
            OpenApiParameter(
                name='ide_cUF',
                type=OpenApiTypes.STR,
                description='Filtrar por código UF do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_nome',
                type=OpenApiTypes.STR,
                description='Filtrar por nome do emitente',
                required=False
            ),
            OpenApiParameter(
                name='chave',
                type=OpenApiTypes.STR,
                description='Filtrar por chave da nota fiscal',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_after',
                type=OpenApiTypes.DATE,
                description='Data de emissão inicial (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_before',
                type=OpenApiTypes.DATE,
                description='Data de emissão final (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='emitente_CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do emitente',
                required=False
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, nome, chave ou data)',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: NfeModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo de resposta (dados fictícios)',
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1001,
                            "chave": "35250912345678000170550010000000000000000000",
                            "versao": "4.00",
                            "dhEmi": "2025-09-15T10:12:30-03:00",
                            "dhSaiEnt": "2025-09-15T10:12:30-03:00",
                            "fileXml": "https://example.com/media/xml/nfe_1001.xml",
                            "filePdf": "https://example.com/media/pdf/nfe_1001.pdf",
                            "empresa": {
                                "id": 10,
                                "razao_social": "CONFEITARIA DOCE LAR LTDA",
                                "documento": "12345678000199",
                                "ie": "123456789112",
                                "uf": "SP",
                                "file": "https://example.com/media/certificados/doce_lar_cert.pfx",
                                "status": "1",
                                "created_at": "2025-01-05T09:00:00-03:00",
                                "updated_at": "2025-09-20T14:30:00-03:00",
                                "usuario": 2,
                                "sistema": 1,
                                "categoria": 1,
                                "matriz_filial": None
                            },
                            "ide": {
                                "id": 1001,
                                "cUF": "35",
                                "natOp": "VENDA MERCADO INTERNO",
                                "mod": "55",
                                "serie": "1",
                                "nNF": "10001",
                                "tpNF": 1,
                                "idDest": 1,
                                "cMunFG": "3552205",
                                "tpImp": 1,
                                "tpEmis": 1,
                                "cDV": "5",
                                "finNFe": 1,
                                "indFinal": 0,
                                "indPres": 1,
                                "indIntermed": 0,
                                "procEmi": 0,
                                "verProc": "4.00",
                                "nota_fiscal": 1001
                            },
                            "emitente": {
                                "id": 1001,
                                "CNPJ": "98765432000166",
                                "xNome": "ALIMENTOS SAUDAVEIS S/A",
                                "xFant": "ALIMENTOS SAUDAVEIS",
                                "IE": "987654321119",
                                "CRT": 3,
                                "xLgr": "RUA DA INDUSTRIA, 500",
                                "nro": "500",
                                "xBairro": "PARQUE INDUSTRIAL",
                                "cMun": "3552205",
                                "xMun": "SAO PAULO",
                                "UF": "SP",
                                "CEP": "04567000",
                                "cPais": "1058",
                                "xPais": "BRASIL",
                                "fone": "1130000000",
                                "nota_fiscal": 1001
                            },
                            "destinatario": {
                                "id": 1001,
                                "CNPJ": "12345678000199",
                                "xNome": "CONFEITARIA DOCE LAR LTDA",
                                "IE": "123456789112",
                                "indIEDest": 1,
                                "xLgr": "RUA DAS FLORES, 200",
                                "nro": "200",
                                "xCpl": "LOJA 02",
                                "xBairro": "CENTRO",
                                "cMun": "3552205",
                                "xMun": "SAO PAULO",
                                "UF": "SP",
                                "CEP": "01010010",
                                "cPais": "1058",
                                "xPais": "BRASIL",
                                "nota_fiscal": 1001
                            },
                            "produtos": [
                                {
                                    "id": 3001,
                                    "nItem": 1,
                                    "cProd": "A001",
                                    "cEAN": "0001234500012",
                                    "xProd": "Bolo de Chocolate 1kg",
                                    "NCM": "19059090",
                                    "CFOP": "5101",
                                    "uCom": "UN",
                                    "qCom": "5.0000",
                                    "vUnCom": "25.0000",
                                    "vProd": "125.00",
                                    "uTrib": "UN",
                                    "qTrib": "5.0000",
                                    "vUnTrib": "25.0000",
                                    "indTot": 1,
                                    "nota_fiscal": 1001,
                                    "imposto": {
                                        "id": 3001,
                                        "vTotTrib": "5.00",
                                        "orig": "0",
                                        "CST": "00",
                                        "vIPI": "0.00",
                                        "vPIS": "0.50",
                                        "vCOFINS": "1.50",
                                        "produto": 3001
                                    }
                                },
                                {
                                    "id": 3002,
                                    "nItem": 2,
                                    "cProd": "B002",
                                    "cEAN": "0001234500029",
                                    "xProd": "Suco de Laranja 1,5L",
                                    "NCM": "20091900",
                                    "CFOP": "5102",
                                    "uCom": "UN",
                                    "qCom": "10.0000",
                                    "vUnCom": "8.0000",
                                    "vProd": "80.00",
                                    "uTrib": "UN",
                                    "qTrib": "10.0000",
                                    "vUnTrib": "8.0000",
                                    "indTot": 1,
                                    "nota_fiscal": 1001,
                                    "imposto": {
                                        "id": 3002,
                                        "vTotTrib": "3.20",
                                        "orig": "0",
                                        "CST": "60",
                                        "vIPI": "0.00",
                                        "vPIS": "0.32",
                                        "vCOFINS": "0.96",
                                        "produto": 3002
                                    }
                                }
                            ],
                            "total": {
                                "vBC": "0.00",
                                "vICMS": "0.00",
                                "vICMSDeson": None,
                                "vFCP": None,
                                "vBCST": None,
                                "vST": None,
                                "vFCPST": None,
                                "vFCPSTRet": None,
                                "vProd": "205.00",
                                "vFrete": "10.00",
                                "vSeg": "0.00",
                                "vDesc": "0.00",
                                "vII": None,
                                "vIPI": "0.00",
                                "vIPIDevol": None,
                                "vPIS": "0.82",
                                "vCOFINS": "2.46",
                                "vOutro": "0.00",
                                "vNF": "217.28",
                                "vTotTrib": "8.00",
                                "nota_fiscal": 1001
                            },
                            "transporte": {
                                "modFrete": 0,
                                "qVol": 1,
                                "nota_fiscal": 1001
                            },
                            "cobranca": {
                                "nFat": "FAT-2025-0001",
                                "vOrig": "217.28",
                                "vDesc": "0.00",
                                "vLiq": "217.28",
                                "nota_fiscal": 1001
                            },
                            "pagamentos": [
                                {
                                    "forma": "01",
                                    "valor": "217.28",
                                    "meio": "DINHEIRO",
                                    "nota_fiscal": 1001
                                }
                            ]
                        }
                    ]
                },
                response_only=True
            )
        ]
    ),
    post=extend_schema(
        exclude=True
    )
    # post=extend_schema(
    #     tags=["Nota fiscal"],
    #     summary="Processar XML de nota fiscal",
    #     description="""
    #     Processa um arquivo XML de nota fiscal e importa para o sistema usando o NFeProcessor.

    #     **Tratamento de duplicatas:**
    #     - Se a nota já existe e está deletada → reativa
    #     - Se não existe → cria nova

    #     **Permissões requeridas:**
    #     - Usuário autenticado
    #     - Acesso via funcionário ativo ou proprietário da empresa
    #     - Permissão específica para esta rota

    #     **Campos obrigatórios:**
    #     - `empresa_id`: ID da empresa
    #     - `nsu`: Número sequencial único
    #     - `tipo`: deve ser enviado 'nfe_nsu'
    #     - `fileXml`: Caminho relativo do arquivo XML

    #     **Tipos suportados:**
    #     - `nfe_nsu`: Nota Fiscal Eletrônica

    #     **Estrutura do XML processada:**
    #     - Dados da nota (chave, versão, datas)
    #     - Identificação (IDE)
    #     - Emitente e endereço
    #     - Destinatário e endereço
    #     - Produtos e impostos
    #     - Totais
    #     - Transporte
    #     - Cobrança e pagamentos
    #     """,
    #     request={
    #         'multipart/form-data': {
    #             'type': 'object',
    #             'properties': {
    #                 'empresa_id': {
    #                     'type': 'integer',
    #                     'description': 'ID da empresa que emitiu a nota'
    #                 },
    #                 'nsu': {
    #                     'type': 'string',
    #                     'description': 'Número Sequencial Único da nota'
    #                 },
    #                 'tipo': {
    #                     'type': 'string',
    #                     'enum': ['nfe_nsu'],
    #                     'description': 'Tipo de documento a ser processado'
    #                 },
    #                 'fileXml': {
    #                     'type': 'string',
    #                     'format': 'file-path',
    #                     'description': 'Caminho relativo do arquivo XML dentro do MEDIA_ROOT'
    #                 }
    #             },
    #             'required': ['empresa_id', 'nsu', 'tipo', 'fileXml']
    #         }
    #     },
    #     responses={
    #         200: OpenApiTypes.OBJECT,
    #         400: OpenApiTypes.OBJECT,
    #         401: OpenApiTypes.OBJECT,
    #         403: OpenApiTypes.OBJECT,
    #         404: OpenApiTypes.OBJECT,
    #         500: OpenApiTypes.OBJECT
    #     },
    #     examples=[
    #         OpenApiExample(
    #             'Exemplo de requisição válida',
    #             value={
    #                 "empresa_id": 123,
    #                 "nsu": "000001234",
    #                 "tipo": "nfe_nsu",
    #                 "fileXml": "xml/notas/nota_1234.xml"
    #             },
    #             request_only=True
    #         ),
    #         OpenApiExample(
    #             'Exemplo de sucesso - Nova nota',
    #             value={
    #                 "message": "XML processado com sucesso!",
    #                 "chave": "35210507564634000135550010000012341000012345",
    #                 "versao": "4.00",
    #                 "status": "nova"
    #             },
    #             response_only=True
    #         ),
    #         OpenApiExample(
    #             'Exemplo de sucesso - Nota reativada',
    #             value={
    #                 "message": "XML processado com sucesso!",
    #                 "chave": "35210507564634000135550010000012341000012345",
    #                 "versao": "4.00",
    #                 "status": "reativada"
    #             },
    #             response_only=True
    #         ),
    #         OpenApiExample(
    #             'Exemplo de erro - Campos obrigatórios',
    #             value={
    #                 "error": "empresa_id, nsu, tipo e fileXml são obrigatórios"
    #             },
    #             response_only=True,
    #             status_codes=['400']
    #         ),
    #         OpenApiExample(
    #             'Exemplo de erro - Empresa não encontrada',
    #             value={
    #                 "error": "Empresa não encontrada."
    #             },
    #             response_only=True,
    #             status_codes=['400']
    #         ),
    #         OpenApiExample(
    #             'Exemplo de erro - XML inválido',
    #             value={
    #                 "error": "Erro ao processar o XML: Elemento infNFe não encontrado no XML"
    #             },
    #             response_only=True,
    #             status_codes=['400']
    #         ),
    #         OpenApiExample(
    #             'Exemplo de erro - Arquivo não encontrado',
    #             value={
    #                 "error": "Arquivo não encontrado: /app/media/xml/notas/nota_inexistente.xml"
    #             },
    #             response_only=True,
    #             status_codes=['404']
    #         )
    #     ]
    # )
)
class NfeListCreateAPIView(NFeBaseView, generics.ListCreateAPIView):
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotaFiscalFilter
    pagination_class = utils.CustomPageSizePagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return NfeSerializer
        return NfeModelSerializer

    def post(self, request, *args, **kwargs):
        try:
            empresa_id = request.data.get('empresa_id')
            nsu = request.data.get('nsu')
            fileXml = request.data.get('fileXml')  # Caminho do arquivo
            tipo = request.data.get('tipo')  # Tipo de documento (ex: nfe_nsu, resumo_nsu, etc.)

            if not empresa_id or not nsu or not tipo or not fileXml:
                return response.Response({'error': 'empresa_id, nsu, tipo e fileXml são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

            empresa = Empresa.objects.filter(pk=empresa_id).first()
            if not empresa:
                return response.Response({'error': 'Empresa não encontrada.'}, status=status.HTTP_400_BAD_REQUEST)

            # Processa o tipo e chama o NFeProcessor adequado
            if tipo == 'nfe_nsu':
                processor = NFeProcessor(empresa, nsu, fileXml)  # Passa o caminho do arquivo
                nota = processor.processar(debug=False)

                return response.Response({
                    'message': 'XML processado com sucesso!',
                    'chave': nota.chave,
                    'versao': nota.versao
                }, status=status.HTTP_200_OK)

            else:
                return response.Response({'error': 'Tipo de documento não suportado'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return response.Response({'error': f'Ocorreu um erro inesperado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema_view(
    post=extend_schema(
        tags=["[Allnube] NF"],
        operation_id="02_processar_lote_nfe",
        summary='02 Processar lote de NFe',
        description="""
        Processa um lote de arquivos XML de NFe, Eventos e Resumos contidos em um arquivo ZIP.

        ## Funcionalidades
        - Processa automaticamente diferentes tipos de XML (NFe, Eventos, Resumos)
        - Atualiza o NSU (Número Sequencial Único) da empresa
        - Retorna estatísticas detalhadas do processamento

        ## Tipos de XML Suportados
        - **nfeProc**: Notas Fiscais Eletrônicas
        - **procEventoNFe**: Eventos de NFe (cancelamentos, correções, etc.)
        - **resNFe/resEvento**: Resumos de NFe e Eventos

        ## Fluxo de Processamento
        1. Validação dos dados de entrada
        2. Verificação de permissões da empresa
        3. Extração do arquivo ZIP
        4. Processamento de cada XML individualmente
        5. Roteamento para o processador específico
        6. Retorno dos resultados consolidados
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'empresa_id': {
                        'type': 'integer',
                        'description': 'ID da empresa que está processando o lote',
                        'example': 3
                    },
                    'arquivo_zip': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Arquivo ZIP contendo os XMLs a serem processados'
                    }
                },
                'required': ['empresa_id', 'arquivo_zip']
            }
        },
        responses={
            201: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Sucesso',
                value={
                    'mensagem': 'Processamento concluído com sucesso',
                    'resultados': {
                        'nfe_processadas': 5,
                        'eventos_processados': 2,
                        'resumos_processados': 3,
                        'erros': []
                    }
                },
                response_only=True,
                status_codes=['201']
            ),
            OpenApiExample(
                'Empresa obrigatória',
                value={'error': 'empresa_id é obrigatório'},
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Arquivo obrigatório',
                value={'error': 'arquivo_zip é obrigatório'},
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Empresa não encontrada',
                value={'error': 'Empresa com ID 999 não encontrada'},
                response_only=True,
                status_codes=['404']
            ),
            OpenApiExample(
                'Empresa não autorizada',
                value={'error': 'Empresa não autorizada para processamento em lote'},
                response_only=True,
                status_codes=['403']
            ),
            OpenApiExample(
                'Erro interno',
                value={'error': 'Erro interno no processamento do lote'},
                response_only=True,
                status_codes=['500']
            ),
        ]
    )
)
class ProcessarLoteNFeAPIView(APIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)

    def post(self, request, *args, **kwargs):
        try:
            empresa_id = request.data.get('empresa_id')
            arquivo_zip = request.FILES.get('arquivo_zip')

            # Validação dos campos obrigatórios
            if not empresa_id:
                return response.Response(
                    {'error': 'empresa_id é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not arquivo_zip:
                return response.Response(
                    {'error': 'arquivo_zip é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Busca e validação da empresa
            empresa = Empresa.objects.get(pk=empresa_id)

            if empresa.sistema != 3:
                return response.Response(
                    {'error': 'Empresa não autorizada para processamento em lote'},
                    status=status.HTTP_403_FORBIDDEN
                )

            verificaEmpresa = utils.verificaRestricaoAdministrativa(empresa.id, 3)
            if not verificaEmpresa:
                raise PermissionDenied(
                    detail="A empresa vinculada à sua conta está desativada, contate um administrador."
                )

            # Pegar o último NSU
            historyNsu = HistoricoNSU.objects.filter(empresa=empresa).order_by('-id').first()
            nsu_inicial = historyNsu.nsu if historyNsu else 0

            # Processar o arquivo ZIP
            resultados = NFeLoteProcessor(empresa, nsu_inicial, arquivo_zip).processar_zip()

            return response.Response({
                'mensagem': 'Processamento concluído com sucesso',
                'resultados': resultados
            }, status=status.HTTP_201_CREATED)

        except Empresa.DoesNotExist:
            return response.Response(
                {'error': f'Empresa com ID {empresa_id} não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return response.Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return response.Response(
                {'error': 'Erro interno no processamento do lote'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF"],
        operation_id='03_gerar_danfe',
        summary='03 Gerar DANFE',
        description="""
        Gera o Documento Auxiliar da Nota Fiscal Eletrônica (DANFE) em formato PDF a partir do XML da NFe.

        ## Funcionalidades
        - Gera PDF da DANFE a partir do XML da nota fiscal
        - Verifica se o PDF já foi gerado anteriormente (evita reprocessamento)
        - Valida se a nota fiscal pertence à empresa do usuário logado
        - Salva o PDF gerado no sistema de arquivos
        - Atualiza o registro da nota fiscal com o caminho do PDF

        ## Fluxo de Processamento
        1. Busca a nota fiscal pelo ID
        2. Valida se a nota pertence à empresa do usuário logado
        3. Verifica se o XML existe
        4. Checa se o PDF já foi gerado anteriormente
        5. Gera o PDF usando a biblioteca Danfe
        6. Salva o caminho do PDF no registro da nota
        7. Retorna a URL para download do PDF

        ## Requisitos
        - O XML da nota fiscal deve estar salvo no sistema
        - A nota fiscal deve pertencer à empresa do usuário logado
        - A biblioteca Danfe deve estar instalada e configurada
        """,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='DANFE gerado com sucesso ou já existente',
                examples=[
                    OpenApiExample(
                        'DANFE gerado com sucesso',
                        value={
                            'message': 'DANFE gerado com sucesso!',
                            'pdf_path': 'https://exemplo.com/media/danfe/NFe123456789.pdf'
                        }
                    ),
                    OpenApiExample(
                        'DANFE já existente',
                        value={
                            'message': 'DANFE já gerado anteriormente.',
                            'pdf_path': 'https://exemplo.com/media/danfe/NFe123456789.pdf'
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Erro na requisição',
                examples=[
                    OpenApiExample(
                        'XML não encontrado',
                        value={'error': 'Arquivo XML não encontrado.'}
                    ),
                    OpenApiExample(
                        'Arquivo XML não encontrado no sistema',
                        value={'error': 'Arquivo XML não encontrado no caminho: /media/xml/NFe123456789.xml'}
                    )
                ]
            ),
            403: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Acesso não autorizado',
                examples=[
                    OpenApiExample(
                        'Nota não pertence à empresa do usuário',
                        value={'error': 'Você não tem permissão para acessar esta nota fiscal.'}
                    )
                ]
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Nota fiscal não encontrada',
                examples=[
                    OpenApiExample(
                        'Nota não encontrada',
                        value={'detail': 'Não encontrado.'}
                    )
                ]
            ),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Erro interno no processamento',
                examples=[
                    OpenApiExample(
                        'Erro na geração do PDF',
                        value={'error': 'Erro durante a geração do DANFE: [detalhes do erro]'}
                    )
                ]
            )
        }
    )
)
class GerarDanfeAPIView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    queryset = models.NotaFiscal.objects.all()

    def get(self, request, *args, **kwargs):
        """
        Endpoint para gerar ou recuperar o DANFE de uma nota fiscal.

        Parâmetros:
        - pk (int): ID da nota fiscal no sistema

        Retorna:
        - URL do PDF gerado ou existente
        - Mensagem de status do processamento
        """
        nota_fiscal = self.get_object()

        verificaEmpresa = utils.verificaRestricaoAdministrativa(nota_fiscal.empresa, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        # Valida se a nota fiscal pertence à empresa do usuário logado
        if not self._validar_empresa_usuario(nota_fiscal, request.user):
            return response.Response(
                {'error': 'Você não tem permissão para acessar esta nota fiscal.'},
                status=status.HTTP_403_FORBIDDEN
            )

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
                {'error': f'Erro durante a geração do DANFE: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validar_empresa_usuario(self, nota_fiscal, usuario):
        """
        Valida se a nota fiscal pertence à empresa do usuário logado.

        Baseado nos modelos:
        - NotaFiscal tem campo 'empresa' (ForeignKey para Empresa)
        - Empresa tem campo 'usuario' (ForeignKey para User)
        - Funcionario relaciona User com Empresa (N:N através do model Funcionario)

        Args:
            nota_fiscal (NotaFiscal): Instância da nota fiscal
            usuario (User): Usuário logado

        Returns:
            bool: True se a nota pertence à empresa do usuário, False caso contrário
        """
        try:
            # Verifica se o usuário é dono direto da empresa da nota fiscal
            if nota_fiscal.empresa.usuario == usuario:
                return True

            # Verifica se o usuário é funcionário da empresa da nota fiscal
            funcionario_exists = Funcionario.objects.filter(
                user=usuario,
                empresa=nota_fiscal.empresa,
                status='1'  # Ativo
            ).exists()

            if funcionario_exists:
                return True

            # Verifica se o usuário é superusuário/staff (acesso total)
            if usuario.is_superuser or usuario.is_staff:
                return True

            return False

        except (AttributeError, Empresa.DoesNotExist, Funcionario.DoesNotExist):
            return False

    @staticmethod
    def _gerar_danfe_pdf(xml_file_path, pasta_saida='media/danfe'):
        """
        Gera e salva o PDF da DANFE a partir do XML.

        Args:
            xml_file_path (str): Caminho completo para o arquivo XML
            pasta_saida (str): Pasta onde o PDF será salvo (relativo a MEDIA_ROOT)

        Returns:
            str: Caminho completo do PDF gerado

        Raises:
            FileNotFoundError: Se o arquivo XML não for encontrado
            Exception: Em caso de erro na geração do PDF
        """
        if not os.path.exists(pasta_saida):
            os.makedirs(pasta_saida)

        with open(xml_file_path, "r", encoding="utf8") as file:
            xml_content = file.read()

        nome_base = os.path.splitext(os.path.basename(xml_file_path))[0]
        caminho_pdf = os.path.join(pasta_saida, f'{nome_base}.pdf')

        danfe = Danfe(xml=xml_content)
        danfe.output(caminho_pdf)

        return caminho_pdf


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF"],
        operation_id="04_listar_notas_fiscais_matriz",
        summary="04 Listar notas fiscais da matriz",
        description="""
        Retorna todas as notas fiscais da matriz do usuário autenticado.
        
        **Características:**
        - Lista apenas notas da matriz (empresa principal)
        - Não requer parâmetros na URL
        - Aplica filtros e paginação
        - Retorna apenas notas não deletadas
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        
        **Filtros disponíveis:**
        - `ide_cUF`: Código da UF do emitente
        - `emitente_nome`: Nome do emitente  
        - `chave`: Chave da nota fiscal
        - `dhEmi`: Data de emissão (range: dhEmi_after & dhEmi_before)
        - `emitente_CNPJ`: CNPJ do emitente
        - `emitente_xNome`: Razão social do emitente
        - `q`: Pesquisa geral (CNPJ, nome ou chave)
        """,
        parameters=[
            OpenApiParameter(
                name='ide_cUF',
                type=OpenApiTypes.STR,
                description='Filtrar por código UF do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_nome',
                type=OpenApiTypes.STR,
                description='Filtrar por nome do emitente',
                required=False
            ),
            OpenApiParameter(
                name='chave',
                type=OpenApiTypes.STR,
                description='Filtrar por chave da nota fiscal',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_after',
                type=OpenApiTypes.DATE,
                description='Data de emissão inicial (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_before',
                type=OpenApiTypes.DATE,
                description='Data de emissão final (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='emitente_CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do emitente',
                required=False
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, nome, chave ou data)',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: NfeModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Listar notas da matriz',
                description='Requisição para listar notas da matriz',
                value={
                    "count": 85,
                    "next": "http://api.example.com/api/v1/nfes/matriz/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "chave": "35210507564634000135550010000012341000012345",
                            "dhEmi": "2023-10-15T14:30:00Z",
                            "emitente": {
                                "xNome": "Matriz Principal Ltda",
                                "CNPJ": "07.564.634/0001-35"
                            },
                            "valor": 2500.00
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class NfeListMatrizAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = NfeModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotaFiscalFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.NotaFiscal.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        nfe = models.NotaFiscal.objects.filter(
            empresa=matriz_id,
            deleted_at__isnull=True,
        )

        if nfe.exists():
            return nfe

        return models.NotaFiscal.objects.none()


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF"],
        operation_id="05_listar_notas_fiscais_filial",
        summary="05 Listar notas fiscais por filial",
        description="""
        Retorna notas fiscais de uma filial específica através do documento (CNPJ).
        
        **Características:**
        - Lista notas de uma filial específica
        - Requer o documento (CNPJ) da filial como parâmetro na URL
        - Valida se a filial pertence à matriz do usuário
        - Valida se a filial está ativa
        - Retorna apenas notas não deletadas
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        
        **Filtros disponíveis:**
        - `ide_cUF`: Código da UF do emitente
        - `emitente_nome`: Nome do emitente  
        - `chave`: Chave da nota fiscal
        - `dhEmi`: Data de emissão (range: dhEmi_after & dhEmi_before)
        - `emitente_CNPJ`: CNPJ do emitente
        - `emitente_xNome`: Razão social do emitente
        - `q`: Pesquisa geral (CNPJ, nome ou chave)
        """,
        parameters=[
            OpenApiParameter(
                name='documento',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Documento (CNPJ) da filial - obrigatório',
                required=True
            ),
            OpenApiParameter(
                name='ide_cUF',
                type=OpenApiTypes.STR,
                description='Filtrar por código UF do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_nome',
                type=OpenApiTypes.STR,
                description='Filtrar por nome do emitente',
                required=False
            ),
            OpenApiParameter(
                name='chave',
                type=OpenApiTypes.STR,
                description='Filtrar por chave da nota fiscal',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_after',
                type=OpenApiTypes.DATE,
                description='Data de emissão inicial (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='dhEmi_before',
                type=OpenApiTypes.DATE,
                description='Data de emissão final (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='emitente_CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do emitente',
                required=False
            ),
            OpenApiParameter(
                name='emitente_xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do emitente',
                required=False
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, nome, chave ou data)',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: NfeModelSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Listar notas da filial',
                description='Requisição para listar notas de uma filial específica',
                value={
                    "count": 23,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 45,
                            "chave": "35210507564634000135550010000056781000056789",
                            "dhEmi": "2023-10-16T10:15:00Z",
                            "emitente": {
                                "xNome": "Filial São Paulo Ltda",
                                "CNPJ": "07.564.634/0002-16"
                            },
                            "valor": 1800.50
                        }
                    ]
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Filial não encontrada',
                value={
                    "detail": "A filial não foi encontrada."
                },
                response_only=True,
                status_codes=['404']
            ),
            OpenApiExample(
                'Exemplo - Documento obrigatório',
                value={
                    "error": "Documento é obrigatório"
                },
                response_only=True,
                status_codes=['400']
            )
        ]
    )
)
class NfeListFilialAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = NfeModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotaFiscalFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.NotaFiscal.objects.none()

        user = self.request.user
        documento = self.kwargs.get('documento', None)
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not documento:
            raise ValidationError({'documento': 'Documento é obrigatório'})

        getFilial = Empresa.objects.filter(
            documento=documento,
            matriz_filial=matriz_id,
            status='1'
        ).first()

        if not getFilial:
            raise NotFound(
                detail="A filial não foi encontrada."
            )

        nfe = models.NotaFiscal.objects.filter(
            empresa=getFilial,
            deleted_at__isnull=True
        )

        if nfe.exists():
            return nfe

        return models.NotaFiscal.objects.none()


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF"],
        operation_id="06_obter_nota_fiscal",
        summary="06 Obter detalhes de uma nota fiscal",
        description="""
        Retorna os detalhes completos de uma nota fiscal específica.
        
        **Informações incluídas:**
        - Dados básicos da nota (chave, versão, datas)
        - Informações do emitente
        - Informações do destinatário  
        - Produtos e impostos
        - Totais e valores
        - Informações de transporte
        - Cobrança e pagamentos
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        - Permissão para visualizar a nota específica
        """,
        responses={
            200: NfeModelSerializer,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Detalhes da nota fiscal',
                value={
                    "id": 1,
                    "chave": "35210507564634000135550010000012341000012345",
                    "versao": "4.00",
                    "dhEmi": "2023-10-15T14:30:00Z",
                    "dhSaiEnt": "2023-10-15T15:00:00Z",
                    "tpAmb": 1,
                    "fileXml": "xml/notas/nota_1234.xml",
                    "deleted_at": None,
                    "emitente": {
                        "CNPJ": "07.564.634/0001-35",
                        "xNome": "Empresa Exemplo Ltda",
                        "xFant": "Empresa Exemplo",
                        "IE": "123.456.789.012",
                        "CRT": 1,
                        "xLgr": "Rua Exemplo",
                        "nro": "123",
                        "xBairro": "Centro",
                        "cMun": "3550308",
                        "xMun": "São Paulo",
                        "UF": "SP",
                        "CEP": "01234-567",
                        "cPais": "1058",
                        "xPais": "Brasil",
                        "fone": "1123456789"
                    },
                    "destinatario": {
                        "CNPJ": "12.345.678/0001-90",
                        "xNome": "Cliente Exemplo Ltda",
                        "IE": "987.654.321.098",
                        "indIEDest": 1,
                        "xLgr": "Avenida Cliente",
                        "nro": "456",
                        "xCpl": "Sala 101",
                        "xBairro": "Jardins",
                        "cMun": "3550308",
                        "xMun": "São Paulo",
                        "UF": "SP",
                        "CEP": "04567-890",
                        "cPais": "1058",
                        "xPais": "Brasil"
                    },
                    "produtos": [
                        {
                            "nItem": 1,
                            "cProd": "PROD001",
                            "cEAN": "7891234567890",
                            "xProd": "Produto Exemplo",
                            "NCM": "8471.60.90",
                            "CFOP": "5102",
                            "uCom": "UN",
                            "qCom": "10.0000",
                            "vUnCom": "150.0000",
                            "vProd": "1500.00",
                            "uTrib": "UN",
                            "qTrib": "10.0000",
                            "vUnTrib": "150.0000",
                            "indTot": 1
                        }
                    ],
                    "impostos": [
                        {
                            "vTotTrib": "350.25",
                            "orig": "0",
                            "CST": "00"
                        }
                    ],
                    "total": {
                        "vBC": "1500.00",
                        "vICMS": "270.00",
                        "vICMSDeson": "0.00",
                        "vFCP": "0.00",
                        "vBCST": "0.00",
                        "vST": "0.00",
                        "vFCPST": "0.00",
                        "vFCPSTRet": "0.00",
                        "vProd": "1500.00",
                        "vFrete": "0.00",
                        "vSeg": "0.00",
                        "vDesc": "0.00",
                        "vII": "0.00",
                        "vIPI": "0.00",
                        "vIPIDevol": "0.00",
                        "vPIS": "9.75",
                        "vCOFINS": "45.00",
                        "vOutro": "25.50",
                        "vNF": "1500.00",
                        "vTotTrib": "350.25"
                    }
                },
                response_only=True
            )
        ]
    ),
    put=extend_schema(
        exclude=True
    ),
    patch=extend_schema(
        exclude=True
    ),
    delete=extend_schema(
        exclude=True
    )
)
class NfeRetrieveUpdateDestroyAPIView(NFeBaseView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NfeModelSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Produto"],
        operation_id="01_listar_todos_produtos_notas_fiscais",
        summary="01 Listar todos os produtos das notas fiscais",
        description="""
        Retorna todos os produtos de todas as notas fiscais da matriz e suas filiais.
        
        **Características:**
        - Lista produtos de todas as notas fiscais (matriz + filiais)
        - Inclui informações de impostos de cada produto
        - Aplica filtros específicos para produtos
        - Retorna dados paginados
        
        **Escopo dos dados:**
        - Produtos da matriz do usuário
        - Produtos de todas as filiais da matriz
        - Apenas produtos de notas fiscais não deletadas
        
        **Estrutura do produto:**
        - Dados básicos do produto (código, descrição, NCM, etc.)
        - Quantidades e valores (comercial e tributário)
        - Informações de impostos (ICMS, IPI, PIS, COFINS)
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (descrição, código do produto ou EAN)',
                required=False
            ),
            OpenApiParameter(
                name='xProd',
                type=OpenApiTypes.STR,
                description='Filtrar por descrição do produto',
                required=False
            ),
            OpenApiParameter(
                name='cProd',
                type=OpenApiTypes.STR,
                description='Filtrar por código do produto',
                required=False
            ),
            OpenApiParameter(
                name='cEAN',
                type=OpenApiTypes.STR,
                description='Filtrar por código EAN',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: ProdutoModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Lista de produtos',
                value={
                    "count": 1250,
                    "next": "http://api.example.com/api/v1/nfes/produtos/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "nItem": 1,
                            "cProd": "PROD001",
                            "cEAN": "7891234567890",
                            "xProd": "Notebook Dell Inspiron 15",
                            "NCM": "8471.30.10",
                            "CFOP": "5102",
                            "uCom": "UN",
                            "qCom": "2.0000",
                            "vUnCom": "2500.0000",
                            "vProd": "5000.00",
                            "uTrib": "UN",
                            "qTrib": "2.0000",
                            "vUnTrib": "2500.0000",
                            "indTot": 1,
                            "nota_fiscal": 123,
                            "imposto": {
                                "vTotTrib": "1250.50",
                                "orig": "0",
                                "CST": "00",
                                "vIPI": "500.00",
                                "vPIS": "32.50",
                                "vCOFINS": "150.00"
                            }
                        },
                        {
                            "id": 2,
                            "nItem": 2,
                            "cProd": "PROD002",
                            "cEAN": "7891234567891",
                            "xProd": "Mouse Óptico USB",
                            "NCM": "8471.60.90",
                            "CFOP": "5102",
                            "uCom": "UN",
                            "qCom": "10.0000",
                            "vUnCom": "25.0000",
                            "vProd": "250.00",
                            "uTrib": "UN",
                            "qTrib": "10.0000",
                            "vUnTrib": "25.0000",
                            "indTot": 1,
                            "nota_fiscal": 123,
                            "imposto": {
                                "vTotTrib": "62.50",
                                "orig": "0",
                                "CST": "00",
                                "vIPI": "0.00",
                                "vPIS": "1.63",
                                "vCOFINS": "7.50"
                            }
                        }
                    ]
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Produto sem imposto',
                value={
                    "id": 3,
                    "nItem": 1,
                    "cProd": "PROD003",
                    "cEAN": "7891234567892",
                    "xProd": "Teclado Mecânico",
                    "NCM": "8471.60.90",
                    "CFOP": "5102",
                    "uCom": "UN",
                    "qCom": "5.0000",
                    "vUnCom": "150.0000",
                    "vProd": "750.00",
                    "uTrib": "UN",
                    "qTrib": "5.0000",
                    "vUnTrib": "150.0000",
                    "indTot": 1,
                    "nota_fiscal": 124,
                    "imposto": None
                },
                response_only=True
            )
        ]
    )
)
class NfeTodosProdutosListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = ProdutoModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProdutoFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Produto.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            return models.Produto.objects.none()

        # Primeiro filtra as notas fiscais permitidas
        notas_fiscais = models.NotaFiscal.objects.filter(
            Q(empresa=matriz_id) |
            Q(empresa__matriz_filial=matriz_id),
            deleted_at__isnull=True  # Garante que só pega notas não deletadas
        )

        # Pega apenas os IDs das notas fiscais
        nota_fiscal_ids = notas_fiscais.values_list('id', flat=True)

        # Retorna produtos dessas notas fiscais
        return models.Produto.objects.filter(
            nota_fiscal_id__in=nota_fiscal_ids
        )


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Produto"],
        operation_id="02_listar_produtos_matriz",
        summary="02 Listar produtos das notas fiscais da matriz",
        description="""
        Retorna todos os produtos das notas fiscais da matriz do usuário.
        
        **Características:**
        - Lista produtos apenas das notas fiscais da matriz
        - Inclui informações de impostos de cada produto
        - Aplica filtros específicos para produtos
        - Retorna dados paginados
        - Ordenado por data de emissão (mais recente primeiro) e número do item
        
        **Estrutura do produto:**
        - Dados básicos do produto (código, descrição, NCM, etc.)
        - Quantidades e valores (comercial e tributário)
        - Informações de impostos (ICMS, IPI, PIS, COFINS)
        - Dados relacionados da nota fiscal
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (descrição, código do produto ou EAN)',
                required=False
            ),
            OpenApiParameter(
                name='xProd',
                type=OpenApiTypes.STR,
                description='Filtrar por descrição do produto',
                required=False
            ),
            OpenApiParameter(
                name='cProd',
                type=OpenApiTypes.STR,
                description='Filtrar por código do produto',
                required=False
            ),
            OpenApiParameter(
                name='cEAN',
                type=OpenApiTypes.STR,
                description='Filtrar por código EAN',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: ProdutoModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Produtos da matriz',
                value={
                    "count": 450,
                    "next": "http://api.example.com/api/v1/nfes/produtos/matriz/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "nItem": 1,
                            "cProd": "MATRIZ001",
                            "cEAN": "7891234567890",
                            "xProd": "Serviço de Consultoria Técnica",
                            "NCM": "9985.19.00",
                            "CFOP": "5933",
                            "uCom": "UN",
                            "qCom": "1.0000",
                            "vUnCom": "5000.0000",
                            "vProd": "5000.00",
                            "uTrib": "UN",
                            "qTrib": "1.0000",
                            "vUnTrib": "5000.0000",
                            "indTot": 1,
                            "nota_fiscal": 100,
                            "imposto": {
                                "vTotTrib": "1350.00",
                                "orig": "0",
                                "CST": "00",
                                "vIPI": "0.00",
                                "vPIS": "32.50",
                                "vCOFINS": "150.00"
                            }
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class NfeProdutosMatrizListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = ProdutoModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProdutoFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Produto.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            return models.Produto.objects.none()

        # Cria o queryset base de Produtos
        produtos = models.Produto.objects.filter(
            nota_fiscal__empresa=matriz_id,
            nota_fiscal__deleted_at__isnull=True
        ).select_related(
            'nota_fiscal',
            'imposto',
            'nota_fiscal__ide',
            'nota_fiscal__emitente',
            'nota_fiscal__destinatario'
        )

        return produtos.order_by('-nota_fiscal__dhEmi', 'nItem')


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Produto"],
        operation_id="03_listar_produtos_filial",
        summary="03 Listar produtos das notas fiscais de uma filial",
        description="""
        Retorna todos os produtos das notas fiscais de uma filial específica.
        
        **Características:**
        - Lista produtos apenas das notas fiscais da filial especificada
        - Valida se a filial pertence à matriz do usuário
        - Valida se a filial está ativa
        - Inclui informações de impostos de cada produto
        - Aplica filtros específicos para produtos
        - Retorna dados paginados
        - Ordenado por data de emissão (mais recente primeiro) e número do item
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='documento',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Documento (CNPJ) da filial - obrigatório',
                required=True
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (descrição, código do produto ou EAN)',
                required=False
            ),
            OpenApiParameter(
                name='xProd',
                type=OpenApiTypes.STR,
                description='Filtrar por descrição do produto',
                required=False
            ),
            OpenApiParameter(
                name='cProd',
                type=OpenApiTypes.STR,
                description='Filtrar por código do produto',
                required=False
            ),
            OpenApiParameter(
                name='cEAN',
                type=OpenApiTypes.STR,
                description='Filtrar por código EAN',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: ProdutoModelSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Produtos da filial',
                value={
                    "count": 120,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 50,
                            "nItem": 1,
                            "cProd": "FILIAL001",
                            "cEAN": "7891234567900",
                            "xProd": "Produto de Varejo - Filial",
                            "NCM": "8517.12.10",
                            "CFOP": "5102",
                            "uCom": "UN",
                            "qCom": "50.0000",
                            "vUnCom": "89.9000",
                            "vProd": "4495.00",
                            "uTrib": "UN",
                            "qTrib": "50.0000",
                            "vUnTrib": "89.9000",
                            "indTot": 1,
                            "nota_fiscal": 200,
                            "imposto": {
                                "vTotTrib": "1123.75",
                                "orig": "0",
                                "CST": "00",
                                "vIPI": "0.00",
                                "vPIS": "29.22",
                                "vCOFINS": "134.85"
                            }
                        }
                    ]
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Documento obrigatório',
                value={
                    "documento": ["Documento é obrigatório"]
                },
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Exemplo - Filial não encontrada',
                value={
                    "detail": "A filial não foi encontrada."
                },
                response_only=True,
                status_codes=['404']
            )
        ]
    )
)
class NfeProdutosFilialListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = ProdutoModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProdutoFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Produto.objects.none()

        user = self.request.user
        documento = self.kwargs.get('documento', None)
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not documento:
            raise ValidationError({'documento': 'Documento é obrigatório'})

        if not matriz_id:
            return models.Produto.objects.none()

        # Verifica se a filial existe e pertence à matriz
        filial = Empresa.objects.filter(
            documento=documento,
            matriz_filial=matriz_id,
            status='1'
        ).first()

        if not filial:
            raise NotFound(detail="A filial não foi encontrada.")

        # Cria o queryset base de Produtos
        produtos = models.Produto.objects.filter(
            nota_fiscal__empresa=filial,  # Usa o ID da filial encontrada
            nota_fiscal__deleted_at__isnull=True
        ).select_related(
            'nota_fiscal',
            'imposto',
            'nota_fiscal__ide',
            'nota_fiscal__emitente',
            'nota_fiscal__destinatario'
        )

        return produtos.order_by('-nota_fiscal__dhEmi', 'nItem')


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Produto"],
        operation_id="04_obter_detalhes_produto",
        summary="04 Obter detalhes completos de um produto",
        description="""
        Retorna os detalhes completos de um produto específico incluindo todas as informações relacionadas.
        
        **Informações incluídas:**
        - **Dados do produto**: código, descrição, NCM, CFOP, quantidades, valores
        - **Impostos do produto**: ICMS, IPI, PIS, COFINS, totais tributários
        - **Nota fiscal completa**: dados da nota, IDE, emitente, destinatário
        - **Totais da nota**: valores de ICMS, PIS, COFINS, frete, seguros, etc.
        - **Transporte**: modalidade de frete, quantidades de volumes
        - **Cobrança e pagamentos**: informações financeiras da nota
        
        **Escopo de acesso:**
        - Produto deve pertencer à matriz do usuário OU a uma de suas filiais
        - Apenas produtos de notas fiscais não deletadas
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        - Permissão para visualizar o produto específico
        """,
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID do produto - obrigatório',
                required=True
            )
        ],
        responses={
            200: ProdutoModelSerializer,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Detalhes completos do produto',
                value={
                    "id": 123,
                    "nItem": 1,
                    "cProd": "PROD001",
                    "cEAN": "7891234567890",
                    "xProd": "Notebook Dell Inspiron 15 i7 16GB 512GB SSD",
                    "NCM": "8471.30.10",
                    "CFOP": "5102",
                    "uCom": "UN",
                    "qCom": "1.0000",
                    "vUnCom": "4500.0000",
                    "vProd": "4500.00",
                    "uTrib": "UN",
                    "qTrib": "1.0000",
                    "vUnTrib": "4500.0000",
                    "indTot": 1,
                    "nota_fiscal": 100,
                    "imposto": {
                        "vTotTrib": "1125.00",
                        "orig": "0",
                        "CST": "00",
                        "vIPI": "0.00",
                        "vPIS": "29.25",
                        "vCOFINS": "135.00"
                    },
                    "nota_fiscal_detalhes": {
                        "ide": {
                            "cUF": "35",
                            "natOp": "Venda de mercadoria",
                            "mod": "55",
                            "serie": "1",
                            "nNF": "12345",
                            "tpNF": "1",
                            "dhEmi": "2023-10-15T14:30:00Z",
                            "dhSaiEnt": "2023-10-15T15:00:00Z"
                        },
                        "emitente": {
                            "CNPJ": "07.564.634/0001-35",
                            "xNome": "Empresa Matriz Ltda",
                            "xFant": "Matriz Principal",
                            "IE": "123.456.789.012",
                            "xLgr": "Rua das Flores",
                            "nro": "123",
                            "xBairro": "Centro",
                            "xMun": "São Paulo",
                            "UF": "SP"
                        },
                        "destinatario": {
                            "CNPJ": "12.345.678/0001-90",
                            "xNome": "Cliente Exemplo Ltda",
                            "IE": "987.654.321.098",
                            "xLgr": "Avenida Principal",
                            "nro": "456",
                            "xMun": "Rio de Janeiro",
                            "UF": "RJ"
                        },
                        "total": {
                            "vBC": "4500.00",
                            "vICMS": "810.00",
                            "vProd": "4500.00",
                            "vFrete": "50.00",
                            "vSeg": "25.00",
                            "vDesc": "100.00",
                            "vPIS": "29.25",
                            "vCOFINS": "135.00",
                            "vNF": "4475.00",
                            "vTotTrib": "1125.00"
                        },
                        "transporte": {
                            "modFrete": 0,
                            "qVol": 1
                        },
                        "cobranca": {
                            "nFat": "FAT001",
                            "vOrig": "4475.00",
                            "vDesc": "0.00",
                            "vLiq": "4475.00",
                            "pagamentos": [
                                {
                                    "tPag": "01",
                                    "vPag": "4475.00"
                                }
                            ]
                        }
                    }
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Produto não encontrado',
                value={
                    "detail": "Não encontrado."
                },
                response_only=True,
                status_codes=['404']
            ),
            OpenApiExample(
                'Exemplo - Acesso negado',
                value={
                    "detail": "Você não tem permissão para acessar este produto."
                },
                response_only=True,
                status_codes=['403']
            )
        ]
    )
)
class NfeProdutoRetrieveAPIView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = ProdutoModelSerializer
    lookup_field = 'pk'  # Já é o padrão, mas explícito é melhor

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Produto.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            # Retorna queryset vazio se não encontrar empresa
            return models.Produto.objects.none()

        # Filtra produtos pela empresa da matriz ou suas filiais
        return models.Produto.objects.filter(
            Q(nota_fiscal__empresa=matriz_id) |
            Q(nota_fiscal__empresa__matriz_filial=matriz_id),
            nota_fiscal__deleted_at__isnull=True  # Garante apenas notas não deletadas
        ).select_related(
            'nota_fiscal',
            'imposto',
            'nota_fiscal__ide',
            'nota_fiscal__emitente',
            'nota_fiscal__destinatario',
            'nota_fiscal__total',
            'nota_fiscal__transporte',
            'nota_fiscal__cobranca'
        ).prefetch_related(
            'nota_fiscal__cobranca__pagamentos'
        )


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Fornecedores"],
        operation_id="01_listar_todos_fornecedores",
        summary="01 Listar todos os fornecedores",
        description="""
        Retorna todos os fornecedores (emitentes) das notas fiscais da matriz e suas filiais.
        
        **Características:**
        - Lista todos os emitentes das notas fiscais da matriz e filiais
        - Fornecedores únicos baseados nas notas fiscais
        - Aplica filtros específicos para fornecedores
        - Retorna dados paginados
        
        **Escopo dos dados:**
        - Emitentes das notas fiscais da matriz do usuário
        - Emitentes das notas fiscais de todas as filiais da matriz
        - Apenas emitentes de notas fiscais não deletadas
        
        **Informações do emitente:**
        - Dados cadastrais (CNPJ, razão social, nome fantasia)
        - Inscrição estadual (IE) e regime tributário (CRT)
        - Endereço completo (logradouro, número, bairro, cidade, UF, CEP)
        - Contato (telefone)
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, razão social ou telefone)',
                required=False
            ),
            OpenApiParameter(
                name='CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='fone',
                type=OpenApiTypes.STR,
                description='Filtrar por telefone do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: EmitenteModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Lista de fornecedores',
                value={
                    "count": 85,
                    "next": "http://api.example.com/api/v1/nfes/fornecedores/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "CNPJ": "07564634000135",
                            "xNome": "Fornecedor Principal Ltda",
                            "xFant": "Fornecedor Principal",
                            "IE": "123456789012",
                            "CRT": 1,
                            "xLgr": "Avenida das Indústrias",
                            "nro": "1000",
                            "xBairro": "Centro Industrial",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "01234567",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1133334444",
                            "nota_fiscal": 123
                        },
                        {
                            "id": 2,
                            "CNPJ": "11222333000144",
                            "xNome": "Distribuidora de Materiais Ltda",
                            "xFant": "Distribuidora Materiais",
                            "IE": "987654321098",
                            "CRT": 2,
                            "xLgr": "Rua do Comércio",
                            "nro": "500",
                            "xBairro": "Comercial",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "02345678",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1122223333",
                            "nota_fiscal": 124
                        }
                    ]
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Fornecedor com dados mínimos',
                value={
                    "id": 3,
                    "CNPJ": "99888777000166",
                    "xNome": "Serviços Gerais ME",
                    "xFant": None,
                    "IE": "456789123456",
                    "CRT": 3,
                    "xLgr": "Rua Pequena",
                    "nro": "25",
                    "xBairro": "Vila Nova",
                    "cMun": "3550308",
                    "xMun": "São Paulo",
                    "UF": "SP",
                    "CEP": "03456789",
                    "cPais": "1058",
                    "xPais": "Brasil",
                    "fone": "1199998888",
                    "nota_fiscal": 125
                },
                response_only=True
            )
        ]
    )
)
class NfeTodosFornecedorListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = EmitenteModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = FornecedorFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Emitente.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            return models.Emitente.objects.none()

        # Primeiro filtra as notas fiscais permitidas
        notas_fiscais = models.NotaFiscal.objects.filter(
            Q(empresa=matriz_id) |
            Q(empresa__matriz_filial=matriz_id),
            deleted_at__isnull=True  # Garante apenas notas não deletadas
        )

        # Pega apenas os IDs das notas fiscais
        nota_fiscal_ids = notas_fiscais.values_list('id', flat=True)

        # Retorna emitentes dessas notas fiscais
        return models.Emitente.objects.filter(
            nota_fiscal_id__in=nota_fiscal_ids
        ).distinct()


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Fornecedores"],
        operation_id="02_listar_fornecedores_matriz",
        summary="02 Listar fornecedores/emitentes da matriz",
        description="""
        Retorna todos os fornecedores (emitentes) das notas fiscais da matriz.
        
        **Características:**
        - Lista apenas fornecedores das notas fiscais da matriz
        - Inclui dados relacionados das notas fiscais
        - Aplica filtros específicos para fornecedores
        - Retorna dados paginados
        - Ordenado por data de emissão (mais recente primeiro) e nome do fornecedor
        
        **Informações do emitente:**
        - Dados cadastrais (CNPJ, razão social, nome fantasia)
        - Inscrição estadual (IE) e regime tributário (CRT)
        - Endereço completo (logradouro, número, bairro, cidade, UF, CEP)
        - Contato (telefone)
        - Dados relacionados da nota fiscal
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, razão social ou telefone)',
                required=False
            ),
            OpenApiParameter(
                name='CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='fone',
                type=OpenApiTypes.STR,
                description='Filtrar por telefone do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: EmitenteModelSerializer(many=True),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Fornecedores da matriz',
                value={
                    "count": 45,
                    "next": "http://api.example.com/api/v1/nfes/fornecedores/matriz/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "CNPJ": "07564634000135",
                            "xNome": "Fornecedor Exclusivo Matriz Ltda",
                            "xFant": "Fornecedor Matriz",
                            "IE": "123456789012",
                            "CRT": 1,
                            "xLgr": "Avenida Principal",
                            "nro": "1000",
                            "xBairro": "Centro",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "01234567",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1133334444",
                            "nota_fiscal": 100
                        },
                        {
                            "id": 2,
                            "CNPJ": "99887766000144",
                            "xNome": "Distribuidora Central Ltda",
                            "xFant": "Distribuidora Central",
                            "IE": "987654321098",
                            "CRT": 2,
                            "xLgr": "Rua das Indústrias",
                            "nro": "500",
                            "xBairro": "Industrial",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "02345678",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1122223333",
                            "nota_fiscal": 101
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
)
class NfeFornecedorMatrizListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = EmitenteModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = FornecedorFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Emitente.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            # Retorna queryset vazio se não encontrar empresa
            return models.Emitente.objects.none()

        # Cria o queryset base de Emitentes
        emitentes = models.Emitente.objects.filter(
            nota_fiscal__empresa=matriz_id,
            nota_fiscal__deleted_at__isnull=True
        ).select_related(
            'nota_fiscal',
            'nota_fiscal__ide',
            'nota_fiscal__emitente',
            'nota_fiscal__destinatario'
        )

        return emitentes.order_by('-nota_fiscal__dhEmi', 'xNome')


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Fornecedores"],
        operation_id="03_listar_fornecedores_filial",
        summary="03 Listar fornecedores/emitentes de uma filial",
        description="""
        Retorna todos os fornecedores (emitentes) das notas fiscais de uma filial específica.
        
        **Características:**
        - Lista apenas fornecedores das notas fiscais da filial especificada
        - Valida se a filial pertence à matriz do usuário
        - Valida se a filial está ativa
        - Inclui dados relacionados das notas fiscais
        - Aplica filtros específicos para fornecedores
        - Retorna dados paginados
        - Ordenado por data de emissão (mais recente primeiro) e nome do fornecedor
        
        **Validações:**
        - Documento (CNPJ) da filial é obrigatório
        - Filial deve pertencer à matriz do usuário
        - Filial deve estar com status ativo
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        """,
        parameters=[
            OpenApiParameter(
                name='documento',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Documento (CNPJ) da filial - obrigatório',
                required=True
            ),
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                description='Pesquisa geral (CNPJ, razão social ou telefone)',
                required=False
            ),
            OpenApiParameter(
                name='CNPJ',
                type=OpenApiTypes.STR,
                description='Filtrar por CNPJ do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='xNome',
                type=OpenApiTypes.STR,
                description='Filtrar por razão social do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='fone',
                type=OpenApiTypes.STR,
                description='Filtrar por telefone do fornecedor',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                description='Número da página',
                required=False
            ),
            OpenApiParameter(
                name='pageSize',
                type=OpenApiTypes.INT,
                description='Tamanho da página (máx: 100)',
                required=False
            )
        ],
        responses={
            200: EmitenteModelSerializer(many=True),
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Fornecedores da filial',
                value={
                    "count": 25,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 50,
                            "CNPJ": "11223344000155",
                            "xNome": "Fornecedor Local Filial Ltda",
                            "xFant": "Fornecedor Local",
                            "IE": "456789123456",
                            "CRT": 1,
                            "xLgr": "Rua da Filial",
                            "nro": "200",
                            "xBairro": "Centro",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "03456789",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1199998888",
                            "nota_fiscal": 200
                        },
                        {
                            "id": 51,
                            "CNPJ": "55443322000166",
                            "xNome": "Distribuidora Regional ME",
                            "xFant": "Distribuidora Regional",
                            "IE": "321654987321",
                            "CRT": 3,
                            "xLgr": "Avenida Regional",
                            "nro": "150",
                            "xBairro": "Zona Norte",
                            "cMun": "3550308",
                            "xMun": "São Paulo",
                            "UF": "SP",
                            "CEP": "04567890",
                            "cPais": "1058",
                            "xPais": "Brasil",
                            "fone": "1188887777",
                            "nota_fiscal": 201
                        }
                    ]
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Documento obrigatório',
                value={
                    "documento": ["Documento é obrigatório"]
                },
                response_only=True,
                status_codes=['400']
            ),
            OpenApiExample(
                'Exemplo - Filial não encontrada',
                value={
                    "detail": "A filial não foi encontrada."
                },
                response_only=True,
                status_codes=['404']
            )
        ]
    )
)
class NfeFornecedorFilialListAPIView(generics.ListAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = EmitenteModelSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = FornecedorFilter
    pagination_class = utils.CustomPageSizePagination

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Emitente.objects.none()

        user = self.request.user
        documento = self.kwargs.get('documento', None)
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not documento:
            raise ValidationError({'documento': 'Documento é obrigatório'})

        if not matriz_id:
            # Retorna queryset vazio se não encontrar empresa
            return models.Emitente.objects.none()

        # Verifica se a filial existe e pertence à matriz
        filial = Empresa.objects.filter(
            documento=documento,
            matriz_filial=matriz_id,
            status='1'
        ).first()

        if not filial:
            raise NotFound(detail="A filial não foi encontrada.")

        # Cria o queryset base de Emitentes
        emitentes = models.Emitente.objects.filter(
            nota_fiscal__empresa=filial,  # Usa o ID da filial encontrada
            nota_fiscal__deleted_at__isnull=True
        ).select_related(
            'nota_fiscal',
            'nota_fiscal__ide',
            'nota_fiscal__emitente',
            'nota_fiscal__destinatario'
        )

        return emitentes.order_by('-nota_fiscal__dhEmi', 'xNome')


@extend_schema_view(
    get=extend_schema(
        tags=["[Allnube] NF Fornecedores"],
        operation_id="04_obter_detalhes_fornecedor",
        summary="04 Obter detalhes completos de um fornecedor",
        description="""
        Retorna os detalhes completos de um fornecedor/emitente específico.
        
        **Informações incluídas:**
        - **Dados cadastrais**: CNPJ, razão social, nome fantasia
        - **Dados fiscais**: Inscrição Estadual (IE), Código de Regime Tributário (CRT)
        - **Endereço completo**: logradouro, número, complemento, bairro, município, UF, CEP
        - **Dados de localização**: código do município, código do país
        - **Contato**: telefone
        - **Relacionamento**: ID da nota fiscal associada
        
        **Escopo de acesso:**
        - Fornecedor deve pertencer à matriz do usuário OU a uma de suas filiais
        - Apenas fornecedores de notas fiscais não deletadas
        
        **Casos de uso típicos:**
        - Visualizar informações completas de um fornecedor específico
        - Obter dados para cadastro em sistema de terceiros
        - Consultar informações fiscais para validação
        - Recuperar dados de contato e endereço
        
        **Permissões requeridas:**
        - Usuário autenticado
        - Acesso via funcionário ativo ou proprietário da empresa
        - Permissão para visualizar o fornecedor específico
        """,
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID do fornecedor/emitente - obrigatório',
                required=True
            )
        ],
        responses={
            200: EmitenteModelSerializer,
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Exemplo - Fornecedor pessoa jurídica',
                value={
                    "id": 123,
                    "CNPJ": "07564634000135",
                    "xNome": "Fornecedor Exemplo Ltda",
                    "xFant": "Fornecedor Exemplo",
                    "IE": "123456789012",
                    "CRT": 1,
                    "xLgr": "Avenida das Indústrias",
                    "nro": "1000",
                    "xBairro": "Centro Industrial",
                    "cMun": "3550308",
                    "xMun": "São Paulo",
                    "UF": "SP",
                    "CEP": "01234567",
                    "cPais": "1058",
                    "xPais": "Brasil",
                    "fone": "1133334444",
                    "nota_fiscal": 100
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Fornecedor sem nome fantasia',
                value={
                    "id": 124,
                    "CNPJ": "11223344000155",
                    "xNome": "Comércio e Distribuição Ltda",
                    "xFant": None,
                    "IE": "987654321098",
                    "CRT": 2,
                    "xLgr": "Rua do Comércio",
                    "nro": "500",
                    "xBairro": "Centro",
                    "cMun": "3550308",
                    "xMun": "São Paulo",
                    "UF": "SP",
                    "CEP": "02345678",
                    "cPais": "1058",
                    "xPais": "Brasil",
                    "fone": "1122223333",
                    "nota_fiscal": 101
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Fornecedor MEI',
                value={
                    "id": 125,
                    "CNPJ": "99887766000144",
                    "xNome": "José Silva MEI",
                    "xFant": "Serviços Silva",
                    "IE": "456789123456",
                    "CRT": 3,
                    "xLgr": "Rua Pequena",
                    "nro": "25",
                    "xBairro": "Vila Nova",
                    "cMun": "3550308",
                    "xMun": "São Paulo",
                    "UF": "SP",
                    "CEP": "03456789",
                    "cPais": "1058",
                    "xPais": "Brasil",
                    "fone": "1199998888",
                    "nota_fiscal": 102
                },
                response_only=True
            ),
            OpenApiExample(
                'Exemplo - Fornecedor não encontrado',
                value={
                    "detail": "Não encontrado."
                },
                response_only=True,
                status_codes=['404']
            ),
            OpenApiExample(
                'Exemplo - Acesso negado',
                value={
                    "detail": "Você não tem permissão para acessar este fornecedor."
                },
                response_only=True,
                status_codes=['403']
            )
        ]
    )
)
class NfeFornecedorRetrieveAPIView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated, PodeAcessarRotasFuncionario)
    serializer_class = EmitenteModelSerializer
    lookup_field = 'pk'  # Já é o padrão, mas explícito é melhor

    def get_queryset(self):
        # Evita erro na geração da documentação Swagger
        if getattr(self, 'swagger_fake_view', False):
            return models.Emitente.objects.none()

        user = self.request.user
        matriz_id = utils.obter_matriz_funcionario(user)

        verificaEmpresa = utils.verificaRestricaoAdministrativa(matriz_id, 3)
        if not verificaEmpresa:
            raise PermissionDenied(
                detail="A empresa vinculada à sua conta está desativada, contate um administrador."
            )

        if not matriz_id:
            return models.Emitente.objects.none()

        # Filtra emitentes pela empresa da matriz ou suas filiais
        return models.Emitente.objects.filter(
            Q(nota_fiscal__empresa=matriz_id) |
            Q(nota_fiscal__empresa__matriz_filial=matriz_id),
            nota_fiscal__deleted_at__isnull=True  # Garante apenas notas não deletadas
        )


###################################################
### Compoem display especificos da home allnube ###
###################################################
class NfeFaturamentoAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

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
        empresa_id = request.user.id

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
        empresa_id = request.user.id

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
