from django.db import connection

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import response
from app.permissions import GlobalDefaultPermission

from apexcharts.serializers import CustoMedioFornecedorSerializer

from datetime import datetime


class CustoMedioFornecedorAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        ano_inicio = str(request.query_params.get("ano_inicio", now.year))
        ano_fim = str(request.query_params.get("ano_fim", now.year))

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
        serializer = CustoMedioFornecedorSerializer(data_list, many=True)

        return response.Response(serializer.data)
