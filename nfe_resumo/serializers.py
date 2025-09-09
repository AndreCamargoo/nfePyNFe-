from rest_framework import serializers

from nfe_resumo.models import ResumoNFe
from nfe_evento.models import EventoNFe
from nfe.models import NotaFiscal
from nfe.serializer import NfeSerializer


class ResumoNFeSerializer(serializers.ModelSerializer):
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)
    evento_existe = serializers.SerializerMethodField()
    nfe_existe = serializers.SerializerMethodField()

    class Meta:
        model = ResumoNFe
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_evento_existe(self, obj):
        # Verifica se existe algum evento para a chave_nfe
        try:
            evento = EventoNFe.objects.filter(chave_nfe=obj.chave_nfe).first()
            if evento:
                return True
            else:
                return False
        except EventoNFe.DoesNotExist:
            return False

    def get_nfe_existe(self, obj):
        try:
            nfe = NotaFiscal.objects.filter(chave=obj.chave_nfe).first()
            if nfe:
                return NfeSerializer(nfe).data
            else:
                return False
        except NotaFiscal.DoesNotExist:
            return False
