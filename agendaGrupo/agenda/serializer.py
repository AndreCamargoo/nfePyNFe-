from rest_framework import serializers
from .models import EventoCadastroEmpresa, EventoContato


class EventoCadastroEmpresaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoCadastroEmpresa
        fields = '__all__'


class EventoContatoModelSerializer(serializers.ModelSerializer):
    # Mostra todas as empresas relacionadas ao contato
    empresas = EventoCadastroEmpresaModelSerializer(many=True, read_only=True)

    class Meta:
        model = EventoContato
        fields = '__all__'
