from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from leads_api.models import Company, Product, Event, Lead
from leads_api.serializer import (
    CompanySerializer,
    ProductSerializer,
    EventSerializer,
    LeadSerializer
)

from .services.gemini import GeminiService
from .services.duplication import DuplicationService

from app.utils import utils
from django_filters.rest_framework import DjangoFilterBackend
from .filters import LeadsFilter


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
    queryset = Lead.objects.all().order_by('-created_at')
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = LeadsFilter
    permission_classes = [IsAuthenticated]
    pagination_class = utils.CustomPageSizePagination


class LeadRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]


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

        leads_qs = Lead.objects.filter(id__in=ids)
        leads_count = leads_qs.count()

        leads_qs.delete()

        return Response({
            "status": "deleted",
            "requested_ids": ids,
            "leads_deleted": leads_count
        })


class LeadLastTimestampsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        last_lead = Lead.objects.order_by('-created_at').first()

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
