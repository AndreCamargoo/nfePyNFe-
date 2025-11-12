from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Pasta, Arquivo, Cliente, AdministradorPasta
from .serializer import PastaModelSerializer, ArquivoModelSerializer, ClienteModelSerializer, AdministradorPastaModelSerializer


class PastaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Pasta.objects.all()
    serializer_class = PastaModelSerializer


class PastaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Pasta.objects.all()
    serializer_class = PastaModelSerializer


class ArquivoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Arquivo.objects.all()
    serializer_class = ArquivoModelSerializer
    parser_classes = [MultiPartParser, FormParser]  # Importante para upload de arquivos

    def get_queryset(self):
        """Filtra arquivos por empresa do usuário logado"""
        queryset = super().get_queryset()

        # Filtra por empresa do usuário (se o usuário tem empresa)
        if hasattr(self.request.user, 'empresa'):
            queryset = queryset.filter(empresa=self.request.user.empresa)

        # Filtros opcionais via query params
        pasta_id = self.request.query_params.get('pasta_id')
        if pasta_id:
            queryset = queryset.filter(pasta_id=pasta_id)

        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        return queryset

    def perform_create(self, serializer):
        """Garante que o arquivo seja criado com o usuário logado"""
        serializer.save(criado_por=self.request.user)


class ArquivoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Arquivo.objects.all()
    serializer_class = ArquivoModelSerializer
    parser_classes = [MultiPartParser, FormParser]


class ClienteListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    serializer_class = ClienteModelSerializer


class ClienteRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    serializer_class = ClienteModelSerializer


class AdministradorPastaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = AdministradorPasta.objects.all()
    serializer_class = AdministradorPastaModelSerializer


class AdministradorPastaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = AdministradorPasta.objects.all()
    serializer_class = AdministradorPastaModelSerializer
