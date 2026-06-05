import re
from rest_framework import serializers
from .models import EventoSorteio, ParticipanteSorteio


def _clean_numeric(value):
    """Remove qualquer caractere não numérico (./-  espaços etc.)"""
    if not value:
        return ''
    return re.sub(r'[^0-9]', '', str(value))


class EventoSorteioSerializer(serializers.ModelSerializer):
    total_participantes = serializers.SerializerMethodField()

    class Meta:
        model = EventoSorteio
        fields = '__all__'

    def get_total_participantes(self, obj):
        return obj.participantes.count()


class ParticipanteSorteioSerializer(serializers.ModelSerializer):
    evento_nome = serializers.CharField(source='evento.nome', read_only=True)

    class Meta:
        model = ParticipanteSorteio
        fields = [
            'id', 'evento', 'evento_nome', 'empresa', 'cnes', 'cnpj',
            'cidade', 'estado', 'contato_nome', 'email', 'telefone',
            'cargo', 'codigo', 'vencedor', 'sorteado_em', 'created_at',
        ]
        read_only_fields = ['codigo', 'vencedor', 'sorteado_em']

    def validate_cnpj(self, value):
        return _clean_numeric(value)

    def validate_cnes(self, value):
        return _clean_numeric(value)

    def validate_telefone(self, value):
        return _clean_numeric(value)

    def validate_empresa(self, value):
        if not value:
            return value
        # Impede que um CNPJ/número seja salvo como nome da empresa
        cleaned = value.strip()
        if cleaned and re.match(r'^[\d.\-/\s]+$', cleaned):
            raise serializers.ValidationError(
                'O campo empresa não pode ser um CNPJ ou número. Informe o nome da instituição.'
            )
        return cleaned

    def validate(self, attrs):
        evento = attrs.get('evento')
        if evento and not evento.ativo:
            raise serializers.ValidationError(
                {'evento': 'Este sorteio não está ativo para inscrições.'}
            )
        return attrs


class GanhadorSerializer(serializers.ModelSerializer):
    evento_nome = serializers.CharField(source='evento.nome', read_only=True)
    evento_local = serializers.CharField(source='evento.local', read_only=True)
    evento_data = serializers.DateField(source='evento.data_evento', read_only=True)

    class Meta:
        model = ParticipanteSorteio
        fields = [
            'id', 'empresa', 'contato_nome', 'cidade', 'estado',
            'codigo', 'sorteado_em', 'evento_nome', 'evento_local', 'evento_data',
        ]
