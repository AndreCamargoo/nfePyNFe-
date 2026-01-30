import csv
import json
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from leads_api.models import Company, Product, Event, Lead
from leads_api.serializer import (
    CompanySerializer,
    ProductSerializer,
    EventSerializer,
    LeadSerializer,
    FileUploadSerializer
)

from .services.gemini import GeminiService
from .services.duplication import DuplicationService

from app.utils import utils
from django_filters.rest_framework import DjangoFilterBackend
from .filters import LeadsFilter

from .services.import_service import ImportService
from rest_framework.parsers import MultiPartParser, FormParser


class CompanyListCreateView(generics.ListCreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]


class CompanyRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]


class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]


class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]


class EventListCreateView(generics.ListCreateAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]


class EventRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]


class EventGenerateEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        event = generics.get_object_or_404(Event, pk=pk)
        result = GeminiService.generate_event_followup(
            event.nome,
            str(event.data)
        )

        if result:
            return Response(result)

        return Response(
            {"error": "Falha na geração de IA"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class LeadListCreateView(generics.ListCreateAPIView):
    # Filtra apenas os NÃO deletados
    queryset = Lead.objects.filter(deleted_at__isnull=True).order_by('-created_at')
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = LeadsFilter
    permission_classes = [IsAuthenticated]
    pagination_class = utils.CustomPageSizePagination


class LeadRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    # Garante que não acessa leads deletados via ID
    queryset = Lead.objects.filter(deleted_at__isnull=True)
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        # Soft Delete: Marca a data de exclusão em vez de remover do banco
        instance.deleted_at = timezone.now()
        instance.save()


class LeadExportView(generics.GenericAPIView):
    """
    Exportação COMPLETA (Dump) de todos os leads ativos.
    Sem paginação e sem filtros.
    """
    queryset = Lead.objects.filter(deleted_at__isnull=True).order_by('-created_at')
    # Removemos os filtros para garantir exportação total
    filter_backends = []
    permission_classes = [IsAuthenticated]
    # Removemos a paginação
    pagination_class = None

    def get(self, request, *args, **kwargs):
        # Pega o queryset base (todos não deletados)
        queryset = self.get_queryset()

        # Não aplicamos filtros nem paginação propositalmente
        leads_to_export = queryset

        # Configura a resposta como CSV
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="leads_full_export.csv"'},
        )

        # Configura o writer para usar ponto e vírgula (Excel PT-BR padrão)
        writer = csv.writer(response, delimiter=';')

        # Cabeçalho
        writer.writerow([
            'Empresa', 'Cnes', 'Telefone', 'CNPJ', 'Cidade', 'Estado',
            'Segmento', 'Classificação', 'Origem', 'Empresas do Grupo',
            'Produtos', 'Contatos (JSON)'
        ])

        # Linhas
        for lead in leads_to_export:
            grupos = ", ".join([company.nome for company in lead.empresas_grupo.all()])
            produtos = ", ".join([prod.nome for prod in lead.produtos_interesse.all()])

            contatos_list = []
            for c in lead.contatos.all():
                contatos_list.append({
                    "nome": c.nome,
                    "setor": c.setor,
                    "email": c.email,
                    "celular": c.celular
                })

            writer.writerow([
                lead.empresa,
                lead.cnes or "",
                lead.telefone or "",
                lead.cnpj or "",
                lead.cidade or "",
                lead.estado or "",
                lead.segmento or "",
                lead.classificacao or "",
                lead.origem or "",
                grupos,
                produtos,
                json.dumps(contatos_list, ensure_ascii=False)
            ])

        return response


class LeadCheckDuplicityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = DuplicationService.analyze(request.data)
        return Response(result)


class LeadGenerateStrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = GeminiService.generate_sales_strategy(request.data)
        if result:
            return Response(result)

        return Response(
            {"error": "Falha na geração de IA"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class LeadBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])

        if not ids:
            return Response(
                {"error": "No IDs provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtra apenas leads que ainda não foram deletados
        leads_qs = Lead.objects.filter(id__in=ids, deleted_at__isnull=True)
        leads_count = leads_qs.count()

        # Executa Soft Delete em massa
        leads_qs.update(deleted_at=timezone.now())

        return Response({
            "status": "deleted",
            "requested_ids": ids,
            "leads_deleted": leads_count
        })


class LeadLastTimestampsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        last_lead = Lead.objects.filter(deleted_at__isnull=True).order_by('-created_at').first()

        if not last_lead:
            return Response({
                "created_at": None,
                "updated_at": None
            })

        return Response({
            "id": last_lead.id,
            "created_at": last_lead.created_at,
            "updated_at": last_lead.updated_at
        })


class LeadImportView(APIView):
    permission_classes = [IsAuthenticated]
    # Permite upload de arquivos
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']
            try:
                # Chama o serviço para processar o arquivo
                result = ImportService.process_csv(file)
                return Response(result, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
