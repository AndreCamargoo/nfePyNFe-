from rest_framework import serializers
from empresa.models import Empresa


class EmpresaModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = Empresa
        fields = ['id', 'razao_social', 'documento', 'ie', 
                  'uf', 'file', 'status'
        ]
