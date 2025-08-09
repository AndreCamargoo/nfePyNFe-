from django.db import connection

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import response
from app.permissions import GlobalDefaultPermission

from serializers import CustoMedioFornecedorSerializer

from datetime import datetime


class CustoMedioFornecedorAPIView(APIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def get(self, request, *args, **kwargs):
        # Empresa associada ao usuário
        empresa_id = request.user.id

        # Ano atual (ou via query param se desejar flexibilidade)
        now = datetime.now()
        ano_inicio = int(request.query_params.get("ano_inicio", now.year))
        ano_fim = int(request.query_params.get("ano_fim", now.year))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM analisar_custo_medio_fornecedor(%s, %s, %s)",
                [empresa_id, ano_inicio, ano_fim]
            )
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()

        if row is None:
            return response.Response({}, status=204)  # Nenhum dado

        data_dict = dict(zip(columns, row))
        serializer = CustoMedioFornecedorSerializer(data_dict)

        return response.Response(serializer.data)
