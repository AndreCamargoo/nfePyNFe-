import re

from django.db import models
from django.contrib.auth.models import User

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from empresa.models import Empresa, CategoriaEmpresa, ConexaoBanco, Funcionario, RotasPermitidas, STATUS_CHOICES
from sistema.models import GrupoRotaSistema

from sistema.models import EmpresaSistema
from sistema.serializer import GrupoRotaSistemaListSerializer


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

    def validate(self, attrs):
        """Valida se a empresa tem permissão para criar banco de dados"""
        empresa = self.context.get('empresa')

        if not empresa:
            raise serializers.ValidationError('Empresa não encontrada no contexto.')

        # Verificar se a empresa tem permissão para criar banco em algum sistema
        sistemas_empresa = EmpresaSistema.objects.filter(
            empresa=empresa,
            ativo=True,
            criar_banco=True  # Deve estar True em pelo menos um sistema
        )

        if not sistemas_empresa.exists():
            raise serializers.ValidationError(
                'Esta empresa não tem permissão para cadastrar banco de dados. '
                'Contate o administrador para liberar esta funcionalidade.'
            )

        return attrs

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


class FuncionarioListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = ['id', 'username', 'email', 'empresa_nome', 'role', 'status']

    def get_status(self, obj):
        return dict(STATUS_CHOICES).get(obj.status, 'Desconhecido')


class FuncionarioSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    empresa_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Funcionario
        fields = ['empresa_id', 'username', 'email', 'password', 'role', 'status']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        user = self.context['request'].user
        empresa_id = attrs.get('empresa_id', instance.empresa_id if instance else None)
        username = attrs.get('username', instance.user.username if instance else None)

        try:
            funcionario_atual = Funcionario.objects.get(user=user, empresa_id=empresa_id)
            if funcionario_atual.role != Funcionario.ADMIN:
                raise serializers.ValidationError('Apenas administradores podem criar ou atualizar funcionários.')
        except Funcionario.DoesNotExist:
            raise serializers.ValidationError('Você não está vinculado a essa empresa.')

        if User.objects.filter(username=username).exists():
            user_existente = User.objects.get(username=username)
            funcionario_existente = Funcionario.objects.filter(user=user_existente, empresa_id=empresa_id).first()
            if funcionario_existente and (not instance or funcionario_existente.id != instance.id):
                raise serializers.ValidationError('Este usuário já está vinculado a essa empresa.')

        # NOVA VALIDAÇÃO: Verificar limite de funcionários (apenas para criação)
        if not instance:  # Apenas na criação, não na atualização
            self._verificar_limite_funcionarios(empresa_id)

        return attrs

    def _verificar_limite_funcionarios(self, empresa_id):
        """Verifica se a empresa pode cadastrar mais funcionários"""
        try:
            empresa = Empresa.objects.get(id=empresa_id)

            # Buscar todos os sistemas ativos da empresa
            sistemas_empresa = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            )

            # Pegar o maior limite entre todos os sistemas (caso tenha múltiplos sistemas)
            max_funcionarios = sistemas_empresa.aggregate(
                max_limite=models.Max('max_funcionarios_registros')
            )['max_limite'] or 1

            # Contar funcionários ativos da empresa
            funcionarios_ativos = Funcionario.objects.filter(
                empresa=empresa,
                status='1'  # Ativo
            ).count()

            if funcionarios_ativos >= max_funcionarios:
                raise serializers.ValidationError(
                    f'Limite de funcionários atingido. Máximo permitido: {max_funcionarios}'
                )

        except Empresa.DoesNotExist:
            raise serializers.ValidationError('Empresa não encontrada.')

    def create(self, validated_data):
        empresa_id = validated_data.pop('empresa_id')
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        role = validated_data.get('role', Funcionario.FUNCIONARIO)

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        if created:
            user.set_password(password)
            user.save()

        empresa = Empresa.objects.get(id=empresa_id)

        funcionario = Funcionario.objects.create(
            user=user,
            empresa=empresa,
            role=role,
            status=validated_data.get('status', '1')
        )

        return funcionario

    def update(self, instance, validated_data):
        instance.role = validated_data.get('role', instance.role)
        instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance


class FuncionarioRotaModelSerializer(serializers.ModelSerializer):
    funcionario = serializers.PrimaryKeyRelatedField(queryset=Funcionario.objects.all())
    rota = serializers.PrimaryKeyRelatedField(queryset=GrupoRotaSistema.objects.all())
    status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RotasPermitidas
        fields = [
            'id', 'funcionario', 'rota', 'status', 'status_display',
            'criado_em', 'atualizado_em'
        ]

    # Campos de exibição legíveis (read-only)
    def get_status_display(self, obj):
        return dict(STATUS_CHOICES).get(obj.status, 'Desconhecido')

    # Validação geral
    def validate(self, attrs):
        funcionario = attrs.get('funcionario')
        rota = attrs.get('rota')
        status = attrs.get('status')

        # Verifica se rota e funcionário são válidos
        if funcionario is None or rota is None:
            raise serializers.ValidationError("Campos 'funcionario' e 'rota' são obrigatórios.")

        # Verifica duplicidade (funcionário + rota)
        qs = RotasPermitidas.objects.filter(funcionario=funcionario, rota=rota)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"O funcionário '{funcionario.user.username}' já possui essa rota atribuída."
            )

        # Verifica se o funcionário pertence à empresa que usa o mesmo sistema da rota
        if rota.sistema not in [es.sistema for es in funcionario.empresa.sistemas.all()]:
            raise serializers.ValidationError(
                f"A rota pertence ao sistema '{rota.sistema.nome}', "
                f"mas a empresa '{funcionario.empresa.razao_social}' não possui este sistema vinculado."
            )

        # Valida status
        if status not in dict(STATUS_CHOICES):
            raise serializers.ValidationError("Status inválido.")

        return attrs

    # Criação
    def create(self, validated_data):
        return RotasPermitidas.objects.create(**validated_data)

    # Atualização
    def update(self, instance, validated_data):
        instance.funcionario = validated_data.get('funcionario', instance.funcionario)
        instance.rota = validated_data.get('rota', instance.rota)
        instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance

    # Representação completa (para GET)
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['funcionario'] = FuncionarioListSerializer(instance.funcionario).data
        data['rota'] = GrupoRotaSistemaListSerializer(instance.rota).data
        return data


# Alias para manter compatibilidade se necessário
EmpresaModelSerializer = EmpresaBaseSerializer
