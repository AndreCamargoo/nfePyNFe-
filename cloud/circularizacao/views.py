from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from app.permissions import PodeAcessarRotasFuncionario

from .models import (
    CircularizacaoAcesso, CircularizacaoCliente, CircularizacaoArquivoRecebido
)
from .serializer import (
    CircularizacaoClienteModelSerializer, CircularizacaoAcessoModelSerializer, CircularizacaoArquivoRecebidoModelSerializer
)


class CircularizacaoClienteListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoCliente.objects.all()
    serializer_class = CircularizacaoClienteModelSerializer


class CircularizacaoClienteRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoCliente.objects.all()
    serializer_class = CircularizacaoClienteModelSerializer


class CircularizacaoAcessoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoAcesso.objects.all()
    serializer_class = CircularizacaoAcessoModelSerializer


class CircularizacaoAcessoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoAcesso.objects.all()
    serializer_class = CircularizacaoAcessoModelSerializer


class CircularizacaoArquivoRecebidoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoArquivoRecebido.objects.all()
    serializer_class = CircularizacaoArquivoRecebidoModelSerializer


class CircularizacaoArquivoRecebidoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, PodeAcessarRotasFuncionario]
    queryset = CircularizacaoArquivoRecebido.objects.all()
    serializer_class = CircularizacaoArquivoRecebidoModelSerializer
