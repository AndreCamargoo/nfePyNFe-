import os
import re

from django.core.files.storage import default_storage

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from empresa.models import Empresa, CategoriaEmpresa, ConexaoBanco, Funcionario, RotasPermitidas, STATUS_CHOICES

from sistema.models import GrupoRotaSistema

from sistema.models import EmpresaSistema, Sistema
from sistema.serializer import GrupoRotaSistemaListSerializer

from django.db import transaction


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

    # Nome do campo diferente do nome do modelo para evitar conflitos
    usuario_especifico = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
        help_text="ID do usuário que será o dono da empresa (opcional, se não enviar usa o usuário logado)"
    )

    sistema = serializers.PrimaryKeyRelatedField(
        queryset=Sistema.objects.all(),
        required=True,
        allow_null=False
    )

    class Meta(EmpresaBaseSerializer.Meta):
        extra_kwargs = {
            'usuario': {'read_only': True},
            'senha': {'required': False},
            'status': {'read_only': True},
        }

    def validate(self, attrs):
        # Pega o usuário específico se enviado
        usuario_especifico = attrs.pop('usuario_especifico', None)

        # Salva no contexto para usar depois
        self.context['usuario_especifico'] = usuario_especifico

        request_user = self.context['request'].user

        # Define qual usuário será usado para validação
        if request_user.is_superuser:
            user = usuario_especifico if usuario_especifico else request_user
        else:
            user = request_user

        matriz_filial = attrs.get('matriz_filial', None)
        sistema = attrs.get('sistema', None)
        categoria = attrs.get('categoria')

        # Sistema é obrigatório
        if sistema is None:
            raise ValidationError({"sistema": "O campo sistema é obrigatório."})

        # Categoria é obrigatória
        if categoria is None:
            raise ValidationError({"categoria": "O campo categoria é obrigatório."})

        # Validação da categoria
        if not CategoriaEmpresa.objects.filter(pk=categoria.pk).exists():
            raise ValidationError({"categoria": "A categoria indicada não existe."})

        # Se for filial
        if matriz_filial is not None:
            if matriz_filial.usuario != user:
                raise ValidationError(
                    {"matriz_filial": "Você só pode cadastrar filiais vinculadas a empresas que pertencem a você."}
                )
            if matriz_filial.matriz_filial is not None:
                raise ValidationError(
                    {"matriz_filial": "Uma filial não pode ser vinculada a outra filial. Selecione uma matriz válida."}
                )
            if matriz_filial.sistema != sistema:
                raise ValidationError(
                    {"matriz_filial": "A matriz e a filial devem pertencer ao mesmo sistema."}
                )

        else:
            # Se não for filial (ou seja, é matriz)
            matriz_existente = Empresa.objects.filter(
                usuario=user,
                sistema=sistema,
                matriz_filial__isnull=True
            ).exists()
            if matriz_existente:
                raise ValidationError(
                    {"sistema": "Você já possui uma empresa matriz cadastrada neste sistema."}
                )

        return attrs

    def create(self, validated_data):
        request_user = self.context['request'].user

        # Pega o usuário específico do contexto (se foi enviado)
        usuario_especifico = self.context.get('usuario_especifico')

        # Define o usuário final
        if request_user.is_superuser:
            if usuario_especifico is not None:
                validated_data['usuario'] = usuario_especifico
            else:
                validated_data['usuario'] = request_user

        return super().create(validated_data)


class EmpresaUpdateSerializer(EmpresaBaseSerializer):
    """Serializer específico para atualização"""

    nfe_hora_inicio = serializers.IntegerField(required=False, min_value=0, max_value=23)
    nfe_hora_fim = serializers.IntegerField(required=False, min_value=0, max_value=23)

    class Meta(EmpresaBaseSerializer.Meta):
        extra_kwargs = {
            **EmpresaBaseSerializer.Meta.extra_kwargs,
            'usuario': {'read_only': True},  # Read only em updates
            'documento': {'required': False},  # Mantém como não obrigatório em updates
            'senha': {'required': False, 'write_only': True},  # Senha não obrigatória em updates, write_only recurso, não será retornado nas respostas
        }

    def update(self, instance, validated_data):
        # Se o campo "sistema" vier explicitamente como None, ignora a alteração
        if 'sistema' in validated_data and validated_data['sistema'] is None:
            validated_data.pop('sistema')  # removido

        return super().update(instance, validated_data)


class EmpresaListSerializer(EmpresaBaseSerializer):
    """Serializer para listagem (pode incluir campos calculados ou relacionados)"""
    pass


class EmpresaModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = Empresa
        fields = '__all__'


class EmpresaAllModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = Empresa
        fields = ['id', 'razao_social', 'documento', 'status']


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
        empresa = self.context.get('empresa')

        if not empresa:
            raise ValidationError('Empresa não encontrada no contexto.')

        # Verifica se empresa tem permissão para criar banco
        tem_permissao = EmpresaSistema.objects.filter(
            empresa=empresa,
            ativo=True,
            criar_banco=True
        ).exists()

        if not tem_permissao:
            raise ValidationError(
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
        conexao_banco = ConexaoBanco.objects.filter(empresa=empresa, status=True).first()

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
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'empresa_nome', 'role', 'status']

    def get_status(self, obj):
        return dict(STATUS_CHOICES).get(obj.status, 'Desconhecido')


class FuncionarioSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    empresa_id = serializers.IntegerField(write_only=True, required=False)
    first_name = serializers.CharField(write_only=True, required=False)
    last_name = serializers.CharField(write_only=True, required=False)
    sistema = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Funcionario
        fields = ['empresa_id', 'username', 'email', 'password', 'role', 'status', 'first_name', 'last_name', 'sistema']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        user = self.context['request'].user
        empresa_id = attrs.get('empresa_id', instance.empresa_id if instance else None)
        username = attrs.get('username', instance.user.username if instance else None)

        try:
            funcionario_atual = Funcionario.objects.get(user=user, empresa_id=empresa_id)
            if funcionario_atual.role != Funcionario.ADMIN:
                raise ValidationError('Apenas administradores podem criar ou atualizar funcionários.')
        except Funcionario.DoesNotExist:
            raise ValidationError('Você não está vinculado a essa empresa.')

        if User.objects.filter(username=username).exists():
            user_existente = User.objects.get(username=username)
            funcionario_existente = Funcionario.objects.filter(user=user_existente, empresa_id=empresa_id).first()
            if funcionario_existente and (not instance or funcionario_existente.id != instance.id):
                raise ValidationError('Este usuário já está vinculado a essa empresa.')

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
                raise ValidationError({
                    "limite": f'Limite de funcionários atingido. Máximo permitido: {max_funcionarios}'
                })

        except Empresa.DoesNotExist:
            raise ValidationError({'empresa': 'Empresa não encontrada.'})

    def create(self, validated_data):
        empresa_id = validated_data.pop('empresa_id')
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        role = validated_data.get('role', Funcionario.FUNCIONARIO)
        sistema = validated_data.get('sistema')

        if sistema == 'centralLeads':
            if User.objects.filter(Q(username=username) | Q(email=email)).exists():
                raise ValidationError({
                    "usuario": "Este usuário já existe no sistema (username ou email)."
                })

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )

        if created:
            user.set_password(password)
            user.save()
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
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

        # Atualiza campos do User vinculado
        user = instance.user
        changed = False
        for field in ('first_name', 'last_name', 'email'):
            val = validated_data.get(field)
            if val is not None and getattr(user, field) != val:
                setattr(user, field, val)
                changed = True

        password = validated_data.get('password', '')
        if password:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        return instance


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class FuncionarioAllModelSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    empresa = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = [
            'id',
            'role',
            'status',
            'criado_em',
            'atualizado_em',
            'user',
            'empresa'
        ]

    def get_empresa(self, obj):
        if hasattr(obj, 'empresa') and obj.empresa:
            return EmpresaListSerializer(obj.empresa).data
        return None


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
            raise ValidationError("Campos 'funcionario' e 'rota' são obrigatórios.")

        # Verifica duplicidade (funcionário + rota)
        qs = RotasPermitidas.objects.filter(funcionario=funcionario, rota=rota)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                f"O funcionário '{funcionario.user.username}' já possui essa rota atribuída."
            )

        # Verifica se o funcionário pertence à empresa que usa o mesmo sistema da rota
        if rota.sistema not in [es.sistema for es in funcionario.empresa.sistemas.all()]:
            raise ValidationError(
                f"A rota pertence ao sistema '{rota.sistema.nome}', "
                f"mas a empresa '{funcionario.empresa.razao_social}' não possui este sistema vinculado."
            )

        # Valida status
        if status not in dict(STATUS_CHOICES):
            raise ValidationError("Status inválido.")

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


class EmpresaAdminDetailSerializer(serializers.ModelSerializer):
    """
    Serializer somente para leitura.
    Retorna tudo relacionado à empresa.
    """

    usuario = serializers.SerializerMethodField()
    funcionarios = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id',
            'razao_social',
            'documento',
            'uf',
            'ie',
            'status',
            'usuario',
            'categoria',
            'sistema',
            'funcionarios',
            'matriz_filial'
        ]

    def get_usuario(self, obj):
        """
        Usuário principal (admin ou primeiro funcionário)
        """
        funcionario = obj.funcionarios_empresa.select_related('user').first()
        if not funcionario:
            return None

        user = funcionario.user
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
        }

    def get_funcionarios(self, obj):
        """
        Lista todos os funcionários da empresa
        """
        return [
            {
                'id': f.id,
                'user_id': f.user.id,
                'username': f.user.username,
                'role': f.role,
                'status': f.status
            }
            for f in obj.funcionarios_empresa.select_related('user').all()
        ]


class CriacaoEmpresaFuncionarioSerializer(serializers.Serializer):
    """
    Usado para:
    - POST  → criação (empresa / filial / funcionário)
    - PUT   → atualização completa
    - PATCH → atualização parcial
    """

    # ==========================
    # CAMPOS DE USUÁRIO
    # ==========================

    username = serializers.CharField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)

    # ==========================
    # CONTROLE
    # ==========================
    is_admin = serializers.BooleanField(required=False)
    is_branch = serializers.BooleanField(required=False)
    empresa_id = serializers.IntegerField(required=False)

    # ==========================
    # EMPRESA
    # ==========================
    razao_social = serializers.CharField(required=False, allow_blank=True)
    documento = serializers.CharField(required=False, allow_blank=True)
    uf = serializers.CharField(required=False, allow_blank=True)
    ie = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    senha_certificado = serializers.CharField(required=False, allow_blank=True)
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=CategoriaEmpresa.objects.all(),
        required=False,
        allow_null=True
    )
    sistema = serializers.PrimaryKeyRelatedField(
        queryset=Sistema.objects.all(),
        required=False,
        allow_null=True
    )
    status = serializers.IntegerField(required=False)
    matriz_filial = serializers.IntegerField(required=False, allow_null=True)
    file = serializers.FileField(required=False)
    criar_banco = serializers.BooleanField(required=False)
    max_funcionarios_registros = serializers.IntegerField(required=False)

    # ======================================
    # VALIDAÇÃO
    # ======================================
    def validate(self, attrs):
        """
        Validação unificada para CREATE e UPDATE
        """
        is_update = self.instance is not None

        # ======================================
        # CASO 3: Apenas funcionário (já existe empresa)
        # ======================================
        if attrs.get('empresa_id') and not attrs.get('is_admin') and not attrs.get('is_branch'):
            # Valida se a empresa existe
            try:
                empresa = Empresa.objects.get(id=attrs['empresa_id'])
                attrs['empresa_existente'] = empresa
            except Empresa.DoesNotExist:
                raise serializers.ValidationError({
                    'message': 'Empresa não encontrada.'
                })

        # ======================================
        # CASO 1: Nova empresa com admin (matriz)
        # ======================================
        elif attrs.get('is_admin') and not attrs.get('is_branch'):
            # Valida campos obrigatórios para empresa
            campos_obrigatorios = ['razao_social', 'documento', 'uf', 'categoria', 'sistema']
            for campo in campos_obrigatorios:
                if not attrs.get(campo):
                    raise serializers.ValidationError({
                        'message': f'{campo}: Este campo é obrigatório para criação de empresa.'
                    })

            # Verifica se documento já existe
            if Empresa.objects.filter(documento=attrs['documento']).exists():
                raise serializers.ValidationError({
                    'message': 'Já existe uma empresa com este documento.'
                })

        # ======================================
        # CASO 2: Filial (pode ter admin ou funcionário comum)
        # ======================================
        elif attrs.get('is_branch'):
            # Valida campos obrigatórios para filial
            campos_obrigatorios = ['razao_social', 'documento', 'uf', 'categoria', 'sistema', 'matriz_filial']
            for campo in campos_obrigatorios:
                if not attrs.get(campo):
                    raise serializers.ValidationError({
                        'message': f'{campo}: Este campo é obrigatório para criação de filial.'
                    })

            # Verifica se matriz existe
            try:
                matriz = Empresa.objects.get(id=attrs['matriz_filial'])
                attrs['matriz'] = matriz
            except Empresa.DoesNotExist:
                raise serializers.ValidationError({
                    'message': 'Empresa matriz não encontrada.'
                })

        # ======================================
        # CASO INVÁLIDO: Não especificou o que criar
        # ======================================
        else:
            raise serializers.ValidationError({
                'message': 'Selecione uma opção válida: criar empresa (is_admin), filial (is_branch) ou funcionário (empresa_id).'
            })

        # ==========================
        # VALIDAÇÃO DE USERNAME / EMAIL
        # (ignora o próprio usuário no UPDATE)
        # ==========================
        user_qs = User.objects.all()

        if is_update:
            funcionario = Funcionario.objects.filter(empresa=self.instance).select_related('user').first()
            if funcionario:
                user_qs = user_qs.exclude(id=funcionario.user.id)

        if 'username' in attrs and user_qs.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({'message': 'Username já existe'})

        if 'email' in attrs and user_qs.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({'message': 'Email já existe'})

        return attrs

    # ======================================
    # CRIAÇÃO
    # ======================================
    def create(self, validated_data):
        # Extrai dados do usuário (comuns a todos os casos)
        user_data = {
            'username': validated_data['username'],
            'email': validated_data['email'],
            'password': validated_data['password'],
            'first_name': validated_data.get('first_name', ''),
            'last_name': validated_data.get('last_name', ''),
            'is_staff': validated_data.get('is_staff', False),
            'is_active': validated_data.get('is_active', True),
        }

        with transaction.atomic():
            # 1. SEMPRE cria o usuário do Django
            user = User.objects.create_user(**user_data)

            # Dicionário para resposta
            response_data = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
            }

            # 2. Decide qual objeto criar baseado no caso

            # ======================================
            # CASO 3: Apenas funcionário (já existe empresa)
            # ======================================
            if 'empresa_existente' in validated_data:
                empresa = validated_data['empresa_existente']

                funcionario = Funcionario.objects.create(
                    user=user,
                    empresa=empresa,
                    role=Funcionario.FUNCIONARIO,  # Funcionário comum
                    status=str(validated_data.get('status', 1))
                )

                response_data.update({
                    'tipo': 'funcionario',
                    'empresa_id': empresa.id,
                    'funcionario_id': funcionario.id,
                    'role': funcionario.role,
                    'message': 'Funcionário criado com sucesso!'
                })

            # ======================================
            # CASO 1: Nova empresa matriz com admin
            # ======================================
            elif validated_data.get('is_admin') and not validated_data.get('is_branch'):
                empresa = Empresa.objects.create(
                    usuario=user,
                    razao_social=validated_data['razao_social'],
                    documento=validated_data['documento'],
                    uf=validated_data['uf'],
                    ie=validated_data.get('ie'),
                    senha=validated_data.get('senha_certificado', ''),
                    categoria=validated_data['categoria'],
                    sistema=validated_data['sistema'],
                    matriz_filial=None,  # É matriz
                    status=str(validated_data.get('status', 1))
                )

                # O funcionário admin já é criado automaticamente pelo save() da Empresa
                # Mas podemos buscá-lo para a resposta
                funcionario = Funcionario.objects.get(user=user, empresa=empresa)

                # Se houver arquivo, processa
                if validated_data.get('file'):
                    empresa.file = validated_data['file']
                    empresa.save()

                response_data.update({
                    'tipo': 'empresa_matriz',
                    'empresa_id': empresa.id,
                    'empresa_razao_social': empresa.razao_social,
                    'funcionario_id': funcionario.id,
                    'role': funcionario.role,
                    'message': 'Empresa matriz e administrador criados com sucesso!'
                })

            # ======================================
            # CASO 2: Nova filial (pode ser admin ou funcionário)
            # ======================================
            elif validated_data.get('is_branch'):
                matriz = validated_data['matriz']
                role = Funcionario.ADMIN if validated_data.get('is_admin') else Funcionario.FUNCIONARIO

                empresa = Empresa.objects.create(
                    usuario=user,
                    razao_social=validated_data['razao_social'],
                    documento=validated_data['documento'],
                    uf=validated_data['uf'],
                    ie=validated_data.get('ie'),
                    senha=validated_data.get('senha_certificado', ''),
                    categoria=validated_data['categoria'],
                    sistema=validated_data['sistema'],
                    matriz_filial=matriz,  # Aponta para a matriz
                    status=str(validated_data.get('status', 1))
                )

                # Cria funcionário com role apropriado
                funcionario = Funcionario.objects.create(
                    user=user,
                    empresa=empresa,
                    role=role,
                    status=str(validated_data.get('status', 1))
                )

                if validated_data.get('file'):
                    empresa.file = validated_data['file']
                    empresa.save()

                tipo_msg = 'admin_filial' if role == Funcionario.ADMIN else 'funcionario_filial'
                mensagem = 'Filial e administrador criados com sucesso!' if role == Funcionario.ADMIN else 'Filial e funcionário criados com sucesso!'
                sistema = validated_data.get('sistema')

                # Criar EmpresaSistema para a filial
                if sistema:
                    EmpresaSistema.objects.create(
                        empresa=empresa,
                        sistema=sistema,
                        ativo=True,
                        criar_banco=validated_data.get('criar_banco', True),
                        max_funcionarios_registros=validated_data.get('max_funcionarios_registros', 1)
                    )

                response_data.update({
                    'tipo': tipo_msg,
                    'empresa_id': empresa.id,
                    'empresa_razao_social': empresa.razao_social,
                    'matriz_id': matriz.id,
                    'funcionario_id': funcionario.id,
                    'role': funcionario.role,
                    'message': mensagem
                })

            return response_data

    # ==========================
    # Atualiza usuário
    # ==========================
    def update(self, instance, validated_data):
        """
        Atualiza tudo partindo do FUNCIONÁRIO
        """
        # ==========================
        # FUNCIONÁRIO → USER
        # ==========================
        try:
            funcionario = Funcionario.objects.select_related('user').get(empresa=instance)
        except Funcionario.DoesNotExist:
            raise serializers.ValidationError({'message': 'Funcionário não encontrado'})

        user = funcionario.user

        # ==========================
        # USER
        # ==========================
        for campo in ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']:
            if campo in validated_data:
                setattr(user, campo, validated_data[campo])

        if validated_data.get('password'):
            user.set_password(validated_data['password'])

        user.save()

        # ==========================
        # FUNCIONÁRIO
        # ==========================
        if 'status' in validated_data:
            funcionario.status = str(validated_data['status'])

        if 'is_admin' in validated_data:
            funcionario.role = Funcionario.ADMIN if validated_data['is_admin'] else Funcionario.FUNCIONARIO

        funcionario.save()

        # ==========================
        # EMPRESA
        # ==========================
        empresa_fields = [
            'razao_social', 'documento', 'uf', 'ie',
            'categoria', 'sistema', 'status'
        ]

        for campo in empresa_fields:
            if campo in validated_data:
                # Para status, converta para string se necessário
                if campo == 'status':
                    setattr(instance, campo, str(validated_data[campo]))
                else:
                    setattr(instance, campo, validated_data[campo])

        if 'matriz_filial' in validated_data:
            try:
                matriz = Empresa.objects.get(id=validated_data['matriz_filial'])
                instance.matriz_filial = matriz
            except Empresa.DoesNotExist:
                raise serializers.ValidationError({'message': 'Empresa matriz não encontrada'})

        if validated_data.get('file'):
            instance.file = validated_data['file']

        if validated_data.get('senha_certificado'):
            instance.senha = validated_data['senha_certificado']

        instance.save()

        return {
            'empresa_id': instance.id,
            'funcionario_id': funcionario.id,
            'user_id': user.id,
            'message': 'Dados atualizados com sucesso'
        }


class EmpresaDetalhesVinculadasSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    razao_social = serializers.CharField()
    documento = serializers.CharField()
    ie = serializers.CharField(allow_null=True)
    uf = serializers.CharField()
    status = serializers.CharField()
    tipo = serializers.CharField()
    categoria = serializers.DictField(allow_null=True)
    sistemas = serializers.ListField()  # Mudado de 'sistema' para 'sistemas'
    sistemas_ids = serializers.ListField()  # Adicionado
    matriz = serializers.DictField(allow_null=True)
    filiais = serializers.ListField()
    conexao_banco = serializers.DictField(allow_null=True)
    funcionarios = serializers.ListField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class EmpresaAdminSerializer(serializers.Serializer):
    """
    Serializer para criação/atualização de empresa via admin
    """
    # Dados do usuário admin
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    # Usuário existente (obrigatório para criação)
    usuario_id = serializers.IntegerField(required=False, allow_null=True)

    # Controle da operação
    empresa_id = serializers.IntegerField(required=False, allow_null=True)
    tipo = serializers.CharField(required=False, default="MATRIZ")

    # Dados da empresa
    razao_social = serializers.CharField(required=False, allow_blank=True)
    documento = serializers.CharField(required=False, allow_blank=True)
    uf = serializers.CharField(required=False, allow_blank=True)
    ie = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, default="1")
    categoria_id = serializers.IntegerField(required=False, allow_null=True)
    matriz_filial_id = serializers.IntegerField(required=False, allow_null=True)

    # Sistemas
    sistemas_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )

    # Configurações
    criar_banco = serializers.BooleanField(default=False)
    max_funcionarios = serializers.IntegerField(default=1)
    senha_certificado = serializers.CharField(required=False, allow_blank=True)

    # Arquivo de certificado
    certificado_file = serializers.FileField(required=False, allow_null=True)

    # Conexão banco de dados
    conexao_banco = serializers.DictField(required=False, allow_null=True)

    # Funcionários adicionais
    funcionarios = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    def _limpar_documento(self, valor):
        """Remove caracteres especiais do documento, deixando apenas números"""
        if not valor:
            return valor
        return re.sub(r'[^0-9]', '', str(valor))

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        # Verifica se é superuser
        if not user.is_superuser:
            raise serializers.ValidationError({'error': 'Apenas superusuários podem acessar esta funcionalidade.'})

        # Limpa o documento se presente
        if attrs.get('documento'):
            attrs['documento'] = self._limpar_documento(attrs['documento'])

        # Caso 1: Atualização de empresa existente
        if attrs.get('empresa_id'):
            try:
                empresa = Empresa.objects.get(id=attrs['empresa_id'])
                attrs['empresa_instance'] = empresa
            except Empresa.DoesNotExist:
                raise serializers.ValidationError({'error': 'Empresa não encontrada.'})

        # Caso 2: Criação de nova empresa
        else:
            # Verifica campos obrigatórios para nova empresa
            campos_obrigatorios = ['razao_social', 'documento', 'uf', 'categoria_id']
            for campo in campos_obrigatorios:
                if not attrs.get(campo):
                    raise serializers.ValidationError({campo: 'Este campo é obrigatório para criação de empresa.'})

            # Verifica se documento já existe
            if Empresa.objects.filter(documento=attrs['documento']).exists():
                raise serializers.ValidationError({'documento': 'Já existe uma empresa com este CNPJ.'})

            # Verifica categoria
            if not CategoriaEmpresa.objects.filter(id=attrs['categoria_id']).exists():
                raise serializers.ValidationError({'categoria_id': 'Categoria não encontrada.'})

            # Verifica se usuario_id foi enviado (para criação)
            if not attrs.get('usuario_id'):
                raise serializers.ValidationError({'usuario_id': 'usuario_id é obrigatório para criar uma nova empresa.'})

            # Verifica se o usuário existe
            try:
                admin_user = User.objects.get(id=attrs['usuario_id'])
                attrs['admin_user'] = admin_user
            except User.DoesNotExist:
                raise serializers.ValidationError({'usuario_id': 'Usuário não encontrado.'})

        return attrs

    def _vincular_sistemas(self, empresa, sistemas_ids, max_funcionarios, criar_banco):
        """Vincula múltiplos sistemas à empresa"""
        # Remove sistemas que não estão mais na lista
        EmpresaSistema.objects.filter(empresa=empresa).exclude(
            sistema_id__in=sistemas_ids
        ).delete()

        # Adiciona ou atualiza sistemas
        for sistema_id in sistemas_ids:
            try:
                sistema = Sistema.objects.get(id=sistema_id)
            except Sistema.DoesNotExist:
                continue

            obj, created = EmpresaSistema.objects.get_or_create(
                empresa=empresa,
                sistema=sistema,
                defaults={
                    'max_funcionarios_registros': max_funcionarios,
                    'criar_banco': criar_banco,
                    'ativo': True
                }
            )
            if not created:
                obj.max_funcionarios_registros = max_funcionarios
                obj.criar_banco = criar_banco
                obj.save()

            # Atualiza o campo 'sistema' da empresa para o primeiro sistema (compatibilidade)
            if empresa.sistema is None:
                empresa.sistema = sistema
                empresa.save()

    def _desativar_usuario(self, user):
        """Desativa um usuário (is_active=False)"""
        if user and user.is_active:
            user.is_active = False
            user.save()

    def _criar_ou_atualizar_funcionarios(self, empresa, funcionarios_list, usuario_admin):
        """Cria ou atualiza funcionários da empresa"""
        funcionarios_ids_atual = set()

        # SEMPRE mantém o administrador principal
        funcionarios_ids_atual.add(usuario_admin.id)

        for func_data in funcionarios_list:
            username = func_data.get('username')
            email = func_data.get('email')
            role = func_data.get('role', 'cliente')
            status = func_data.get('status', '1')
            password = func_data.get('password', '123456')

            # Se tem ID, atualiza existente
            if func_data.get('id'):
                try:
                    funcionario = Funcionario.objects.get(id=func_data['id'], empresa=empresa)
                    # Não permite remover o admin via ID
                    if funcionario.user.id == usuario_admin.id:
                        continue

                    funcionario.role = role
                    funcionario.status = str(status)
                    funcionario.save()
                    funcionarios_ids_atual.add(funcionario.user.id)

                    # Atualiza dados do usuário
                    user = funcionario.user
                    if username:
                        user.username = username
                    if email:
                        user.email = email
                    if password:
                        user.set_password(password)
                    # Reativa o usuário se necessário
                    if not user.is_active:
                        user.is_active = True
                    user.save()
                    continue
                except Funcionario.DoesNotExist:
                    pass

            # Cria novo funcionário (apenas se tiver username e email)
            if username and email:
                # Verifica se usuário já existe (inclusive desativado)
                user = None
                if User.objects.filter(username=username).exists():
                    user = User.objects.get(username=username)
                elif User.objects.filter(email=email).exists():
                    user = User.objects.get(email=email)

                if user:
                    # Reativa o usuário se estiver desativado
                    if not user.is_active:
                        user.is_active = True
                        user.save()
                else:
                    # Cria novo usuário
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=username,
                        last_name='',
                        is_active=True
                    )

                # Verifica se já não é funcionário desta empresa
                if not Funcionario.objects.filter(user=user, empresa=empresa).exists():
                    funcionario = Funcionario.objects.create(
                        user=user,
                        empresa=empresa,
                        role=role,
                        status=str(status)
                    )
                    funcionarios_ids_atual.add(user.id)

        # Remove funcionários que não estão mais na lista (exceto o admin)
        funcionarios_para_remover = Funcionario.objects.filter(
            empresa=empresa
        ).exclude(
            user_id__in=funcionarios_ids_atual
        )

        for func in funcionarios_para_remover:
            # Desativa o usuário, não deleta
            self._desativar_usuario(func.user)
            func.delete()

    def _criar_conexao_banco(self, empresa, conexao_data):
        """Cria ou atualiza conexão com banco de dados"""
        if not conexao_data:
            return

        conexao, created = ConexaoBanco.objects.get_or_create(empresa=empresa)

        if conexao_data.get('host'):
            conexao.set_host(conexao_data['host'])
        if conexao_data.get('porta'):
            conexao.set_porta(conexao_data['porta'])
        if conexao_data.get('database'):
            conexao.set_database(conexao_data['database'])
        if conexao_data.get('usuario'):
            conexao.set_usuario(conexao_data['usuario'])
        if conexao_data.get('senha'):
            conexao.set_senha(conexao_data['senha'])

        conexao.status = True
        conexao.save()

    def create(self, validated_data):
        """Cria nova empresa com usuário existente"""
        with transaction.atomic():
            # 1. Pega o usuário admin existente
            admin_user = validated_data['admin_user']

            # 2. Cria empresa
            categoria = CategoriaEmpresa.objects.get(id=validated_data['categoria_id'])

            empresa = Empresa.objects.create(
                usuario=admin_user,
                razao_social=validated_data['razao_social'],
                documento=validated_data['documento'],
                uf=validated_data['uf'],
                ie=validated_data.get('ie', ''),
                senha=validated_data.get('senha_certificado', ''),
                categoria=categoria,
                status=validated_data.get('status', '1'),
            )

            # 3. Salva arquivo de certificado se enviado
            if validated_data.get('certificado_file'):
                empresa.file = validated_data['certificado_file']
                empresa.save()

            # 4. Vincula sistemas
            sistemas_ids = validated_data.get('sistemas_ids', [])
            max_funcionarios = validated_data.get('max_funcionarios', 1)
            criar_banco = validated_data.get('criar_banco', False)
            self._vincular_sistemas(empresa, sistemas_ids, max_funcionarios, criar_banco)

            # 5. Cria conexão banco (se solicitado)
            if criar_banco and validated_data.get('conexao_banco'):
                self._criar_conexao_banco(empresa, validated_data['conexao_banco'])

            # 6. Cria funcionários adicionais
            funcionarios_list = validated_data.get('funcionarios', [])
            self._criar_ou_atualizar_funcionarios(empresa, funcionarios_list, admin_user)

            return {
                'success': True,
                'message': 'Empresa criada com sucesso!',
                'empresa_id': empresa.id,
                'razao_social': empresa.razao_social,
                'usuario_id': admin_user.id,
                'username': admin_user.username
            }

    def update(self, instance, validated_data):
        """Atualiza empresa existente"""
        empresa = validated_data.get('empresa_instance', instance)

        with transaction.atomic():
            # 1. Atualiza dados da empresa
            if validated_data.get('razao_social'):
                empresa.razao_social = validated_data['razao_social']
            if validated_data.get('documento'):
                empresa.documento = validated_data['documento']
            if validated_data.get('uf'):
                empresa.uf = validated_data['uf']
            if validated_data.get('ie') is not None:
                empresa.ie = validated_data['ie']
            if validated_data.get('status'):
                empresa.status = validated_data['status']
            if validated_data.get('categoria_id'):
                empresa.categoria = CategoriaEmpresa.objects.get(id=validated_data['categoria_id'])
            if validated_data.get('senha_certificado'):
                empresa.senha = validated_data['senha_certificado']

            # 2. Gerencia o arquivo de certificado
            novo_arquivo = validated_data.get('certificado_file')

            if novo_arquivo:
                # Deleta o arquivo anterior se existir
                if empresa.file and empresa.file.name:
                    try:
                        # Caminho completo do arquivo
                        file_path = empresa.file.path

                        # Verifica se o arquivo existe antes de tentar deletar
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            # print(f"Arquivo anterior removido: {file_path}")
                        else:
                            # print(f"Arquivo anterior não encontrado: {file_path}")
                            pass
                    except Exception:
                        # print(f"Erro ao remover arquivo anterior: {e}")
                        pass

                # Salva o novo arquivo
                empresa.file = novo_arquivo
                # print(f"Novo arquivo salvo: {empresa.file.name}")

            empresa.save()

            # 3. Atualiza sistemas
            sistemas_ids = validated_data.get('sistemas_ids', [])
            max_funcionarios = validated_data.get('max_funcionarios', 1)
            criar_banco = validated_data.get('criar_banco', False)
            self._vincular_sistemas(empresa, sistemas_ids, max_funcionarios, criar_banco)

            # 4. Atualiza conexão banco
            if criar_banco and validated_data.get('conexao_banco'):
                self._criar_conexao_banco(empresa, validated_data['conexao_banco'])
            elif not criar_banco:
                # Se não quer mais criar banco, desativa a conexão
                ConexaoBanco.objects.filter(empresa=empresa).update(status=False)

            # 5. Atualiza funcionários
            funcionarios_list = validated_data.get('funcionarios', [])
            admin_user = empresa.usuario
            self._criar_ou_atualizar_funcionarios(empresa, funcionarios_list, admin_user)

            return {
                'success': True,
                'message': 'Empresa atualizada com sucesso!',
                'empresa_id': empresa.id,
                'razao_social': empresa.razao_social
            }


class EmpresaDeleteSerializer(serializers.Serializer):
    """
    Serializer para deletar empresa e desativar vínculos
    """
    empresa_id = serializers.IntegerField()

    def validate_empresa_id(self, value):
        try:
            empresa = Empresa.objects.get(id=value)
            return empresa
        except Empresa.DoesNotExist:
            raise serializers.ValidationError("Empresa não encontrada.")

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        # Verifica se é superuser
        if not user.is_superuser:
            raise serializers.ValidationError({'error': 'Apenas superusuários podem deletar empresas.'})

        return attrs


# Alias para manter compatibilidade se necessário
EmpresaModelSerializer = EmpresaBaseSerializer