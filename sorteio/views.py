from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import EventoSorteio, ParticipanteSorteio
from .serializers import EventoSorteioSerializer, ParticipanteSorteioSerializer, GanhadorSerializer


# ── Eventos ─────────────────────────────────────────────────────────────────

class EventoSorteioListCreateView(generics.ListCreateAPIView):
    queryset = EventoSorteio.objects.all()
    serializer_class = EventoSorteioSerializer
    permission_classes = [IsAuthenticated]


class EventoSorteioDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EventoSorteio.objects.all()
    serializer_class = EventoSorteioSerializer
    permission_classes = [IsAuthenticated]


class EventoToggleView(APIView):
    """Ativa ou desativa o sorteio."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            evento = EventoSorteio.objects.get(pk=pk)
        except EventoSorteio.DoesNotExist:
            return Response({'detail': 'Evento não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        evento.ativo = not evento.ativo
        evento.save()
        return Response({'ativo': evento.ativo})


# ── Participantes ────────────────────────────────────────────────────────────

class ParticipanteSorteioCreateView(generics.CreateAPIView):
    """Inscrição pública na landing page."""
    queryset = ParticipanteSorteio.objects.all()
    serializer_class = ParticipanteSorteioSerializer
    permission_classes = [AllowAny]


class ParticipanteSorteioListView(generics.ListAPIView):
    serializer_class = ParticipanteSorteioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ParticipanteSorteio.objects.all()
        evento_id = self.request.query_params.get('evento')
        if evento_id:
            qs = qs.filter(evento_id=evento_id)
        return qs


# ── Sorteio ──────────────────────────────────────────────────────────────────

class SortearView(APIView):
    """Realiza o sorteio e retorna o vencedor."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            evento = EventoSorteio.objects.get(pk=pk)
        except EventoSorteio.DoesNotExist:
            return Response({'detail': 'Evento não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        participantes = ParticipanteSorteio.objects.filter(evento=evento, vencedor=False)
        if not participantes.exists():
            return Response(
                {'detail': 'Nenhum participante disponível para sortear.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        vencedor = participantes.order_by('?').first()
        vencedor.vencedor = True
        vencedor.sorteado_em = timezone.now()
        vencedor.save()

        return Response(GanhadorSerializer(vencedor).data)


# ── Ganhadores (público) ─────────────────────────────────────────────────────

class GanhadoresListView(generics.ListAPIView):
    """Lista pública de ganhadores para a landing page."""
    serializer_class = GanhadorSerializer
    permission_classes = [AllowAny]
    queryset = ParticipanteSorteio.objects.filter(vencedor=True).select_related('evento')


# ── Evento ativo (público) ───────────────────────────────────────────────────

class EventoAtivoView(APIView):
    """Retorna o evento ativo atual (para a landing page)."""
    permission_classes = [AllowAny]

    def get(self, request):
        evento = EventoSorteio.objects.filter(ativo=True).first()
        if not evento:
            return Response({'detail': 'Nenhum evento ativo no momento.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(EventoSorteioSerializer(evento).data)
