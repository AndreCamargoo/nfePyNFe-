from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Segmento
from .serializer import SegmentoModelSerializer


class SegmentoListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Segmento.objects.all()
    serializer_class = SegmentoModelSerializer


class SegmengoRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Segmento.objects.all()
    serializer_class = SegmentoModelSerializer
