from rest_framework import generics, status
from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated

from app.permissions import GlobalDefaultPermission

from empresa.models import Empresa
from nfe_evento.models import EventoNFe

from nfe_evento.processor.evento_processor import EventoNFeProcessor
from nfe_evento.serializers import EventoNFeSerializer


class EventoNFeProcessAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    serializer_class = EventoNFeSerializer

    def get_queryset(self):
        return EventoNFe.objects.filter(empresa__usuario=self.request.user, deleted_at__isnull=True)

    def post(self, request, *args, **kwargs):
        try:
            empresa_id = request.data.get('empresa_id')
            nsu = request.data.get('nsu')
            file_xml = request.data.get('fileXml')
            tipo = request.data.get('tipo')

            if not all([empresa_id, nsu, file_xml, tipo]):
                return Response({'error': 'Todos os campos são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

            if tipo != 'outro_nsu':
                return Response({'error': 'Tipo de documento não suportado'}, status=status.HTTP_400_BAD_REQUEST)

            empresa = Empresa.objects.get(pk=empresa_id)
            processor = EventoNFeProcessor(empresa, nsu, file_xml)
            evento = processor.processar()

            serializer = self.get_serializer(evento)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventoNFeRetriveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = EventoNFeSerializer

    def get_queryset(self):
        return EventoNFe.objects.filter(empresa__usuario=self.request.user, deleted_at__isnull=True)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
