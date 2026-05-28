from rest_framework import serializers
from django.db import transaction
from empresa.models import Empresa, Funcionario, STATUS_CHOICES
from .models import Segmento, Subpasta, Arquivo, Circularizacao


# ==================== SERIALIZERS PARA SEGMENTO ====================
class SegmentoListSerializer(serializers.ModelSerializer):
    empresa_auditoria_nome = serializers.CharField(source='empresa_auditoria.razao_social', read_only=True)
    clientes_count = serializers.SerializerMethodField()
    subpastas_count = serializers.SerializerMethodField()
    responsaveis_nomes = serializers.SerializerMethodField()
    clientes_detalhes = serializers.SerializerMethodField()

    class Meta:
        model = Segmento
        fields = [
            'id', 'nome', 'ano', 'validade', 'is_circ',
            'empresa_auditoria', 'empresa_auditoria_nome',
            'clientes_count', 'subpastas_count', 'responsaveis_nomes',
            'clientes_detalhes',  # ← campo adicionado
            'criado_em', 'atualizado_em'
        ]

    def get_clientes_count(self, obj):
        return obj.clientes.count()

    def get_subpastas_count(self, obj):
        return obj.subpastas.count()

    def get_responsaveis_nomes(self, obj):
        return [f"{r.user.first_name} {r.user.last_name}" for r in obj.responsaveis.all()]

    def get_clientes_detalhes(self, obj):
        from empresa.serializer import EmpresaListSerializer
        return EmpresaListSerializer(obj.clientes.all(), many=True).data


class SegmentoCreateUpdateSerializer(serializers.ModelSerializer):
    clientes = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        many=True,
        required=False
    )
    responsaveis = serializers.PrimaryKeyRelatedField(
        queryset=Funcionario.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = Segmento
        fields = [
            'id', 'nome', 'ano', 'validade',
            'is_circ', 'clientes', 'responsaveis'
        ]

    def validate(self, attrs):
        # Validação de duplicata precisa da empresa_auditoria
        # Como não temos no payload, vamos validar na view
        return attrs


class SegmentoDetailSerializer(serializers.ModelSerializer):
    """Serializer para detalhamento de segmento com relações completas"""
    empresa_auditoria_nome = serializers.CharField(source='empresa_auditoria.razao_social', read_only=True)
    clientes_detalhes = serializers.SerializerMethodField()
    responsaveis_detalhes = serializers.SerializerMethodField()
    subpastas_detalhes = serializers.SerializerMethodField()

    class Meta:
        model = Segmento
        fields = [
            'id', 'nome', 'ano', 'validade', 'is_circ',
            'empresa_auditoria', 'empresa_auditoria_nome',
            'clientes_detalhes', 'responsaveis_detalhes',
            'subpastas_detalhes', 'criado_em', 'atualizado_em'
        ]

    def get_clientes_detalhes(self, obj):
        from empresa.serializer import EmpresaListSerializer
        return EmpresaListSerializer(obj.clientes.all(), many=True).data

    def get_responsaveis_detalhes(self, obj):
        from empresa.serializer import FuncionarioListSerializer
        return FuncionarioListSerializer(obj.responsaveis.all(), many=True).data

    def get_subpastas_detalhes(self, obj):
        return SubpastaSerializer(obj.subpastas.all(), many=True).data


# ==================== SERIALIZERS PARA SUBPASTA ====================

class SubpastaSerializer(serializers.ModelSerializer):
    """Serializer para Subpasta"""
    segmento_nome = serializers.CharField(source='segmento.nome', read_only=True)
    arquivos_count = serializers.SerializerMethodField()

    class Meta:
        model = Subpasta
        fields = [
            'id', 'segmento', 'segmento_nome', 'nome',
            'categoria_circ', 'arquivos_count', 'criado_em'
        ]

    def get_arquivos_count(self, obj):
        return obj.arquivos.count()


class SubpastaCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para criação/atualização de subpasta"""
    class Meta:
        model = Subpasta
        fields = ['id', 'segmento', 'nome', 'categoria_circ']


# ==================== SERIALIZERS PERMISSÃO DE FUNCIONARIOS EM SEGMENTOS "PASTAS" ====================
class FuncionarioListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)
    status = serializers.SerializerMethodField()
    is_linked = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = ['id', 'username', 'email', 'empresa_nome', 'role', 'status', 'is_linked']

    def get_status(self, obj):
        return dict(STATUS_CHOICES).get(obj.status, 'Desconhecido')

    def get_is_linked(self, obj):
        segmento_id = self.context.get('segmento_id')
        if segmento_id:
            # Verifica se o funcionário está na lista de responsáveis do segmento
            return obj.segmentos_responsaveis.filter(id=segmento_id).exists()
        return False


# ==================== SERIALIZERS EMPRESAS RELACIONADAS ====================
class EmpresaListSerializer(serializers.ModelSerializer):
    is_linked = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ['id', 'razao_social', 'documento', 'uf', 'status', 'is_linked']

    def get_is_linked(self, obj):
        segmento_id = self.context.get('segmento_id')
        if segmento_id:
            return obj.segmentos_vinculados.filter(id=segmento_id).exists()
        return False


# ==================== SERIALIZERS PARA ARQUIVO ====================

class ArquivoSerializer(serializers.ModelSerializer):
    """Serializer para Arquivo"""
    cliente_nome = serializers.CharField(source='cliente.razao_social', read_only=True)
    enviado_por_nome = serializers.SerializerMethodField()
    subpasta_nome = serializers.CharField(source='subpasta.nome', read_only=True)

    class Meta:
        model = Arquivo
        fields = [
            'id', 'subpasta', 'subpasta_nome', 'cliente', 'cliente_nome',
            'enviado_por', 'enviado_por_nome', 'nome_remetente',
            'nome_arquivo', 'arquivo', 'criado_em'
        ]
        read_only_fields = ['criado_em']

    def get_enviado_por_nome(self, obj):
        if obj.enviado_por:
            return f"{obj.enviado_por.first_name} {obj.enviado_por.last_name}".strip() or obj.enviado_por.username
        return obj.nome_remetente


class ArquivoCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de arquivo"""
    class Meta:
        model = Arquivo
        fields = ['subpasta', 'cliente', 'nome_arquivo', 'arquivo']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['enviado_por'] = request.user
            validated_data['nome_remetente'] = request.user.get_full_name() or request.user.username
        return super().create(validated_data)


# ==================== SERIALIZERS PARA CIRCULARIZAÇÃO ====================

class CircularizacaoListSerializer(serializers.ModelSerializer):
    """Serializer para listagem de circularizações"""
    cliente_nome = serializers.CharField(source='cliente.razao_social', read_only=True)
    responsavel_nome = serializers.SerializerMethodField()
    segmento_id = serializers.IntegerField(source='segmento.id', read_only=True)
    segmento_nome = serializers.CharField(source='segmento.nome', read_only=True)

    class Meta:
        model = Circularizacao
        fields = [
            'id', 'id_uuid', 'cliente', 'cliente_nome', 'responsavel',
            'responsavel_nome', 'ano', 'senha', 'status', 'segmento_id',
            'segmento_nome', 'criado_em'
        ]

    def get_responsavel_nome(self, obj):
        if obj.responsavel:
            return f"{obj.responsavel.user.first_name} {obj.responsavel.user.last_name}".strip() or obj.responsavel.user.username
        return None


class CircularizacaoCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de circularização (gera automático o segmento)"""
    class Meta:
        model = Circularizacao
        fields = ['cliente', 'responsavel', 'ano', 'senha']

    def validate(self, attrs):
        cliente = attrs.get('cliente')
        ano = attrs.get('ano')

        # Verifica se já existe circularização para este cliente no mesmo ano
        if Circularizacao.objects.filter(cliente=cliente, ano=ano).exists():
            raise serializers.ValidationError(
                f"Já existe uma circularização ativa para o cliente '{cliente.razao_social}' no ano {ano}."
            )

        return attrs

    def create(self, validated_data):
        from django.utils.crypto import get_random_string

        request = self.context.get('request')
        empresa_auditoria = None

        # Busca a empresa de auditoria do usuário logado
        if request and request.user.is_authenticated:
            funcionario = Funcionario.objects.filter(user=request.user).first()
            if funcionario:
                empresa_auditoria = funcionario.empresa

        if not empresa_auditoria:
            raise serializers.ValidationError("Não foi possível identificar a empresa de auditoria.")

        cliente = validated_data['cliente']
        ano = validated_data['ano']
        responsavel = validated_data.get('responsavel')

        # Gera nome do segmento
        nome_segmento = f"Circularização {ano} - {cliente.razao_social}"

        with transaction.atomic():
            # Cria o segmento associado
            segmento = Segmento.objects.create(
                empresa_auditoria=empresa_auditoria,
                nome=nome_segmento,
                ano=ano,
                validade='1_ano',
                is_circ=True
            )

            # Adiciona o cliente ao segmento
            segmento.clientes.add(cliente)

            # Adiciona o responsável se informado
            if responsavel:
                segmento.responsaveis.add(responsavel)

            # Cria as subpastas padrão para circularização
            categorias = ['CCF', 'CCA', 'CCB', 'CCC', 'CCS']
            for categoria in categorias:
                Subpasta.objects.create(
                    segmento=segmento,
                    nome=f"{categoria} - Documentos",
                    categoria_circ=categoria
                )

            # Cria a circularização
            circularizacao = Circularizacao.objects.create(
                segmento=segmento,
                cliente=cliente,
                responsavel=responsavel,
                ano=ano,
                senha=validated_data.get('senha', get_random_string(6).upper()),
                status='ativo'
            )

            return circularizacao


class CircularizacaoUpdateSerializer(serializers.ModelSerializer):
    """Serializer para atualização de circularização"""
    class Meta:
        model = Circularizacao
        fields = ['responsavel', 'ano', 'senha', 'status']

    def validate(self, attrs):
        if 'ano' in attrs and self.instance:
            # Verifica se já existe outra circularização para este cliente no novo ano
            exists = Circularizacao.objects.filter(
                cliente=self.instance.cliente,
                ano=attrs['ano']
            ).exclude(id=self.instance.id).exists()

            if exists:
                raise serializers.ValidationError(
                    f"Já existe outra circularização para este cliente no ano {attrs['ano']}."
                )
        return attrs

    def update(self, instance, validated_data):
        # Atualiza também o segmento se o ano mudar
        if 'ano' in validated_data and validated_data['ano'] != instance.ano:
            novo_nome = f"Circularização {validated_data['ano']} - {instance.cliente.razao_social}"
            instance.segmento.nome = novo_nome
            instance.segmento.ano = validated_data['ano']
            instance.segmento.save()

        return super().update(instance, validated_data)


class CircularizacaoDetailSerializer(serializers.ModelSerializer):
    """Serializer para detalhamento de circularização"""
    cliente_detalhes = serializers.SerializerMethodField()
    responsavel_detalhes = serializers.SerializerMethodField()
    segmento_detalhes = SegmentoDetailSerializer(source='segmento', read_only=True)

    class Meta:
        model = Circularizacao
        fields = [
            'id', 'id_uuid', 'cliente_detalhes', 'responsavel_detalhes',
            'ano', 'senha', 'status', 'segmento_detalhes', 'criado_em'
        ]

    def get_cliente_detalhes(self, obj):
        from empresa.serializer import EmpresaListSerializer
        return EmpresaListSerializer(obj.cliente).data

    def get_responsavel_detalhes(self, obj):
        from empresa.serializer import FuncionarioListSerializer
        if obj.responsavel:
            return FuncionarioListSerializer(obj.responsavel).data
        return None


# ==================== SERIALIZERS PARA NAVEGAÇÃO (DEEP LINKS) ====================

class ClienteComAcessoSerializer(serializers.Serializer):
    """Serializer para listar clientes com acesso a segmentos"""
    id = serializers.IntegerField()
    nome = serializers.CharField()
    segmentos_count = serializers.IntegerField()
    arquivos_count = serializers.IntegerField()


class NavegacaoSegmentoSerializer(serializers.Serializer):
    """Serializer para navegação hierárquica"""
    id = serializers.IntegerField()
    nome = serializers.CharField()
    tipo = serializers.CharField()  # 'segmento', 'subpasta', 'arquivo'
    progresso = serializers.FloatField()
    filhos = serializers.ListField(child=serializers.DictField(), required=False)
