from rest_framework import serializers

from nfe_evento.models import EventoNFe, SignatureEvento, RetornoEvento


class SignatureEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignatureEvento
        fields = '__all__'


class RetornoEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetornoEvento
        fields = '__all__'


class EventoNFeSerializer(serializers.ModelSerializer):
    signature = SignatureEventoSerializer(read_only=True)
    retorno = RetornoEventoSerializer(read_only=True)

    class Meta:
        model = EventoNFe
        fields = '__all__'
