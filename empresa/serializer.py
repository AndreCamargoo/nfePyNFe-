import re
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from empresa.models import Empresa, CategoriaEmpresa, ConexaoBanco


class EmpresaBaseSerializer(serializers.ModelSerializer):
    """Serializer base com validações comuns"""
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
        """Remove caracteres especiais e valida unicidade manualmente."""
        clean_value = re.sub(r'[.\-\/]', '', value)

        # Exclui a instância atual na validação de unicidade (para updates)
        queryset = Empresa.objects.filter(documento=clean_value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError("Já existe uma empresa cadastrada com este documento.")

        return clean_value


class EmpresaCreateSerializer(EmpresaBaseSerializer):
    """Serializer específico para criação"""

    def validate(self, attrs):
        user = self.context['request'].user
        matriz_filial = attrs.get('matriz_filial', None)

        # Verificando se a categoria foi enviada
        categoria = attrs.get('categoria', None)
        if categoria is None:
            raise ValidationError({"categoria": "O campo categoria é obrigatório."})

        # Validação da categoria vinculada
        if categoria is not None:
            # Garantir que a categoria exista
            if not CategoriaEmpresa.objects.filter(pk=categoria.pk).exists():
                raise ValidationError({"categoria": "A categoria indicada não existe."})

        # Se for filial
        if matriz_filial is not None:
            # Garante que a matriz indicada pertence ao usuário
            if matriz_filial.usuario != user:
                raise ValidationError(
                    {"matriz_filial": "Você só pode cadastrar filiais vinculadas a empresas que pertencem a você."}
                )

            # Garante que a matriz indicada não seja uma filial
            if matriz_filial.matriz_filial is not None:
                raise ValidationError(
                    {"matriz_filial": "Uma filial não pode ser vinculada a outra filial. Selecione uma empresa matriz."}
                )

            # Garante que o usuário já tenha ao menos uma matriz
            matriz_exists = Empresa.objects.filter(usuario=user, matriz_filial__isnull=True).exists()
            if not matriz_exists:
                raise ValidationError(
                    {"matriz_filial": "Você precisa ter uma empresa matriz cadastrada para poder criar filiais."}
                )

        return attrs

    def create(self, validated_data):
        """Força sempre o vínculo da empresa ao usuário autenticado."""
        validated_data['usuario'] = self.context['request'].user
        return super().create(validated_data)


class EmpresaUpdateSerializer(EmpresaBaseSerializer):
    """Serializer específico para atualização"""

    class Meta(EmpresaBaseSerializer.Meta):
        extra_kwargs = {
            **EmpresaBaseSerializer.Meta.extra_kwargs,
            'usuario': {'read_only': True},  # Read only em updates
            'documento': {'required': False},  # Mantém como não obrigatório em updates
            'senha': {'required': False, 'write_only': True},  # Senha não obrigatória em updates, write_only recurso, não será retornado nas respostas
        }


class EmpresaListSerializer(EmpresaBaseSerializer):
    """Serializer para listagem (pode incluir campos calculados ou relacionados)"""
    # Exemplo: se quiser adicionar campos calculados futuramente
    # nome_matriz = serializers.CharField(source='matriz_filial.razao_social', read_only=True)
    pass


class CategoriaEmpresaModelSerializer(serializers.ModelSerializer):
    """Serializer para CategoriaEmpresa"""
    class Meta:
        model = CategoriaEmpresa
        fields = '__all__'
        extra_kwargs = {
            'parent': {'required': False, 'allow_null': True},
            'descricao': {'required': False, 'allow_blank': True, 'allow_null': True},
        }


class ConexaoBancoModelSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    host = serializers.CharField(write_only=True, required=True)
    porta = serializers.IntegerField(write_only=True, required=True)
    usuario = serializers.CharField(write_only=True, required=True)
    database = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = ConexaoBanco
        fields = '__all__'
        extra_kwargs = {
            'empresa': {'read_only': True},  # Não vem do body
            'password': {'write_only': True, 'required': True},
            'host': {'write_only': True, 'required': True},
            'porta': {'write_only': True, 'required': True},
            'usuario': {'write_only': True, 'required': True},
            'database': {'write_only': True, 'required': True},
        }

    def create(self, validated_data):
        senha_plana = validated_data.pop('password')
        host = validated_data.pop('host')
        porta = validated_data.pop('porta')
        usuario = validated_data.pop('usuario')
        database = validated_data.pop('database')

        empresa = self.context['empresa']

        # Sempre sobrescreve a conexão, se já existir
        conexao_banco = ConexaoBanco.objects.filter(empresa=empresa).first()

        if conexao_banco:
            # Se já existir uma conexão, atualiza
            for key, value in validated_data.items():
                setattr(conexao_banco, key, value)
        else:
            # Se não existir, cria uma nova
            conexao_banco = ConexaoBanco(empresa=empresa, **validated_data)

        # Criptografa os campos adicionais
        conexao_banco.set_senha(senha_plana)
        conexao_banco.set_host(host)
        conexao_banco.set_porta(porta)
        conexao_banco.set_usuario(usuario)
        conexao_banco.set_database(database)

        conexao_banco.save()
        return conexao_banco

    def update(self, instance, validated_data):
        senha_plana = validated_data.pop('password', None)
        host = validated_data.pop('host', None)
        porta = validated_data.pop('porta', None)
        usuario = validated_data.pop('usuario', None)
        database = validated_data.pop('database', None)

        # Atualizando os campos criptografados
        if senha_plana:
            instance.set_senha(senha_plana)
        if host:
            instance.set_host(host)
        if porta:
            instance.set_porta(porta)
        if usuario:
            instance.set_usuario(usuario)
        if database:
            instance.set_database(database)

        # Atualizando os demais campos
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance


# Alias para manter compatibilidade se necessário
EmpresaModelSerializer = EmpresaBaseSerializer
