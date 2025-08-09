from django.db import connection

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import response, status
from app.permissions import GlobalDefaultPermission

from apexcharts.serializers import (
    CustoMedioFornecedorSerializer, ParticipacaoFornecedoresSerializer, ConcentracaoProdutosSerializer,
    FrequenciaComprasQuerySerializer, FrequenciaComprasSerializer
)

from datetime import datetime


class CustoMedioFornecedorAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        ano_inicio = request.query_params.get("ano_inicio") or None
        ano_fim = request.query_params.get("ano_fim") or None

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_custo_medio_fornecedor(%s, %s, %s)",
                [empresa_id, ano_inicio, ano_fim]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()  # Usando fetchall para pegar todas as linhas

        if not rows:
            return response.Response([], status=204)  # Nenhum dado

        # Converte todas as linhas em um dicionário
        data_list = [dict(zip(columns, row)) for row in rows]

        # Serializa a lista de dicionários
        serializer = CustoMedioFornecedorSerializer(data_list, many=True)

        return response.Response(serializer.data)


class ParticipacaoFornecedoresAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        ano_inicio = request.query_params.get("ano_inicio") or None
        ano_fim = request.query_params.get("ano_fim") or None

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_participacao_fornecedores(%s, %s, %s)",
                [empresa_id, ano_inicio, ano_fim]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()  # Usando fetchall para pegar todas as linhas

        if not rows:
            return response.Response([], status=204)  # Nenhum dado

        # Converte todas as linhas em um dicionário
        data_list = [dict(zip(columns, row)) for row in rows]

        # Serializa a lista de dicionários
        serializer = ParticipacaoFornecedoresSerializer(data_list, many=True)

        return response.Response(serializer.data)


class ConcentracaoProdutosAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        percentual_alvo = int(request.query_params.get("percentual_alvo", 80))
        ano_inicio = request.query_params.get("ano_inicio") or None
        ano_fim = request.query_params.get("ano_fim") or None

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_concentracao_produtos(%s, %s, %s, %s)",
                [empresa_id, percentual_alvo, ano_inicio, ano_fim]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()  # Usando fetchall para pegar todas as linhas

        if not rows:
            return response.Response([], status=204)  # Nenhum dado

        # Converte todas as linhas em um dicionário
        data_list = [dict(zip(columns, row)) for row in rows]

        # Serializa a lista de dicionários
        serializer = ConcentracaoProdutosSerializer(data_list, many=True)

        return response.Response(serializer.data)


class FrequenciaComprasAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        query_serializer = FrequenciaComprasQuerySerializer(data=request.query_params)

        if not query_serializer.is_valid():
            # Checar se o erro é de 'mes_ou_semana'
            if 'mes_ou_semana' in query_serializer.errors:
                return response.Response(
                    {"detail": "O parâmetro 'mes_ou_semana' deve ser 'mensal' ou 'semanal'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Caso seja outro erro, retorna o padrão
            return response.Response(query_serializer.errors, status=400)

        validated = query_serializer.validated_data

        empresa_id = request.user.id
        mes_ou_semana = validated["mes_ou_semana"]
        ano_inicio = validated.get("ano_inicio")
        ano_fim = validated.get("ano_fim")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_frequencia_compras(%s, %s, %s, %s)",
                [empresa_id, mes_ou_semana, ano_inicio, ano_fim]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        if not rows:
            return response.Response([], status=204)

        data_list = [dict(zip(columns, row)) for row in rows]
        serializer = FrequenciaComprasSerializer(data_list, many=True)

        return response.Response(serializer.data)
