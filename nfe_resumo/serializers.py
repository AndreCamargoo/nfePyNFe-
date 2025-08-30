from rest_framework import serializers
from .models import ResumoNFe


class ResumoNFeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ResumoNFe
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
