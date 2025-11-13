from rest_framework import serializers
from .models import EventoCadastroEmpresa, EventoContato


class EventoContatoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoContato
        fields = ['id', 'nome', 'cargo', 'email', 'telefone', 'origem_lead', 'status']


class EventoCadastroEmpresaModelSerializer(serializers.ModelSerializer):
    # Expande o relacionamento FK — inclui os dados do contato completo
    contato = EventoContatoModelSerializer(read_only=True)

    class Meta:
        model = EventoCadastroEmpresa
        fields = '__all__'
