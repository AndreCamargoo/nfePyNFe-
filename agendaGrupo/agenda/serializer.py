from rest_framework import serializers

from .models import EventoCadastroEmpresa, EventoContato


class EventoContatoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoContato
        fields = '__all__'


class EventoCadastroEmpresaModelSerializer(serializers.ModelSerializer):
    # Mostra todos os contatos relacionados
    contatos = EventoContatoModelSerializer(many=True, read_only=True)

    class Meta:
        model = EventoCadastroEmpresa
        fields = '__all__'  # ou liste manualmente os campos se quiser
