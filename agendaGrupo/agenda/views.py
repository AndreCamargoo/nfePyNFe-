from django.conf import settings
from datetime import datetime
from django.http import HttpResponse

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from rest_framework.response import Response

from .models import EventoCadastroEmpresa, EventoContato
from .serializer import (EventoCadastroEmpresaModelSerializer, EventoContatoModelSerializer)

from app.utils import utils

# Importações para PDF
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


class EventoCadastroListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = []
    serializer_class = EventoCadastroEmpresaModelSerializer
    queryset = EventoCadastroEmpresa.objects.all()
    pagination_class = utils.CustomPageSizePagination


class EventoCadastroRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = EventoCadastroEmpresaModelSerializer
    queryset = EventoCadastroEmpresa.objects.all()


class EventoContatoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = []
    serializer_class = EventoContatoModelSerializer
    queryset = EventoContato.objects.all()


class EventoContatoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = EventoContatoModelSerializer
    queryset = EventoContato.objects.all()


class EventoDownload(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = EventoCadastroEmpresaModelSerializer

    def post(self, request, *args, **kwargs):
        data_inicial = request.data.get('data_inicial')
        data_final = request.data.get('data_final')
        senha = request.data.get('senha')

        if not senha or senha != settings.DOWNLOAD_AGENDA:
            return Response(
                {"error": "Senha inválida ou não informada."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not data_inicial or not data_final:
            return Response(
                {"error": "Os campos 'data_inicial' e 'data_final' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            data_inicial = datetime.strptime(data_inicial, "%Y-%m-%d")
            data_final = datetime.strptime(data_final, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"error": "As datas devem estar no formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = EventoCadastroEmpresa.objects.filter(
            created_at__date__gte=data_inicial,
            created_at__date__lte=data_final
        ).prefetch_related('contatos')

        if not queryset.exists():
            return Response(
                {"message": "Nenhum registro encontrado para o período informado."},
                status=status.HTTP_204_NO_CONTENT
            )

        # Serializa e gera PDF
        serializer = self.get_serializer(queryset, many=True)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("<b>Relatório de Cadastros de Empresas</b>", styles['Title']))
        elements.append(Paragraph(f"Período: {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        for empresa in serializer.data:
            elements.append(Paragraph(f"<b>{empresa['nome_empresa']}</b> ({empresa['documento']})", styles['Heading3']))
            elements.append(Paragraph(f"Endereço: {empresa['endereco']}, {empresa['cidade']} - {empresa['uf']}", styles['Normal']))
            elements.append(Paragraph(f"Email: {empresa['email']} | Telefone: {empresa['telefone']}", styles['Normal']))
            elements.append(Paragraph(f"Status: {'Ativo' if empresa['status'] == '1' else 'Inativo'}", styles['Normal']))
            elements.append(Spacer(1, 10))

            contatos = empresa.get('contatos', [])
            if contatos:
                table_data = [['Nome', 'Cargo', 'Email', 'Telefone', 'Origem']]
                for c in contatos:
                    table_data.append([
                        c['nome'], c['cargo'], c['email'], c['telefone'], c['origem_lead']
                    ])
                table = Table(table_data, colWidths=[100, 80, 130, 80, 70])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 20))
            else:
                elements.append(Paragraph("<i>Sem contatos cadastrados.</i>", styles['Italic']))
                elements.append(Spacer(1, 20))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="relatorio_cadastros_{data_inicial.strftime("%Y%m%d")}_{data_final.strftime("%Y%m%d")}.pdf"'
        return response
