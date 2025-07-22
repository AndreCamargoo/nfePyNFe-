from rest_framework import serializers
from empresa.models import Empresa


class EmpresaModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = Empresa
        fields = '__all__'

        extra_kwargs = {
            'usuario': {'required': False},
            'matriz_filial': {'required': False},
            'razao_social': {'required': False},
            'documento': {'required': False},
            'ie': {'required': False},
            'uf': {'required': False},
            'senha': {'write_only': True},
            'file': {'required': False, 'allow_null': True},
            'status': {'required': False},
        }

    def validate_documento(self, value):
        import re
        return re.sub(r'[.\-\/]', '', value)
