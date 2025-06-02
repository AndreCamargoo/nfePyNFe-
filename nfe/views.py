import re
from rest_framework import generics, status, response
from rest_framework.permissions import IsAuthenticated

from empresa.models import Empresa
from . import models
from app.permissions import GlobalDefaultPermission
from nfe.serializer import NfeSerializer, NfeModelSerializer
from nfe.processor.nfe_processor import NFeProcessor


class NfeListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = models.NotaFiscal.objects.all()

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
