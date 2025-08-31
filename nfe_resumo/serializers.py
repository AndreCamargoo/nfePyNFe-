from rest_framework import serializers
from .models import ResumoNFe


class ResumoNFeSerializer(serializers.ModelSerializer):
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)

    class Meta:
        model = ResumoNFe
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
