from rest_framework import serializers

from .models import Segmento


class SegmentoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segmento
        fields = '__all__'
