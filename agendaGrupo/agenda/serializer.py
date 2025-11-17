from rest_framework import serializers
from .models import EventoCadastroEmpresa, EventoContato


class EventoContatoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoContato
        fields = ['id', 'nome', 'cargo', 'email', 'telefone', 'origem_lead', 'status']


class EventoCadastroEmpresaModelSerializer(serializers.ModelSerializer):
    contato = serializers.PrimaryKeyRelatedField(
        queryset=EventoContato.objects.all()
    )

    class Meta:
        model = EventoCadastroEmpresa
        fields = '__all__'
