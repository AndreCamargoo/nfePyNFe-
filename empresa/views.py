from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from empresa.models import Empresa
from app.permissions import GlobalDefaultPermission
from empresa.serializer import EmpresaModelSerializer


class EmpresaListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = Empresa.objects.all()
    serializer_class = EmpresaModelSerializer


class EmpresaRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    queryset = Empresa.objects.all()
    serializer_class = EmpresaModelSerializer
