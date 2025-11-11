from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import EventoCadastroEmpresa, EventoContato
from .serializer import (EventoCadastroEmpresaModelSerializer, EventoContatoModelSerializer)

from app.utils import utils


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
