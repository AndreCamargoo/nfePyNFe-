from rest_framework import serializers
from sistema.models import Sistema, EmpresaSistema, RotaSistema, GrupoRotaSistema


class SistemaSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Sistema.

    Utilizado para operações CRUD básicas do cadastro de sistemas.
    """
    class Meta:
        model = Sistema
        fields = '__all__'


class EmpresaSistemaModelSerializer(serializers.ModelSerializer):
    """
    Serializer especializado para CREATE e LIST de relações Empresa-Sistema.

    Este serializer é utilizado especificamente na view que cria e lista
    relações entre empresas e sistemas através da URL:
    GET/POST /sistemas/{empresa_id}/empresa/

    Características:
    - Inclui campo computado com o nome do sistema
    - Valida duplicidade na criação
    - Define automaticamente o empresa_id vindo da URL
    """

    # Campo computado que mostra o nome do sistema relacionado
    sistema_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EmpresaSistema
        fields = ['id', 'sistema', 'sistema_nome', 'ativo']
        read_only_fields = ['id', 'sistema_nome']

    def get_sistema_nome(self, obj):
        """
        Método para obter o nome do sistema relacionado.

        Este método é automaticamente chamado pelo SerializerMethodField
        quando o objeto é serializado para resposta.

        Parâmetros:
            obj: Instância do modelo EmpresaSistema sendo serializada

        Retorno:
            str: Nome do sistema relacionado

        Exemplo:
            >>> empresa_sistema = EmpresaSistema.objects.get(id=1)
            >>> serializer = EmpresaSistemaModelSerializer(empresa_sistema)
            >>> serializer.data['sistema_nome']
            'Sistema ERP'
        """
        return obj.sistema.nome

    def validate_sistema(self, value):
        """
        Validação específica para o campo 'sistema' durante a criação.

        Impede a criação de relações duplicadas entre a mesma empresa e sistema.

        Parâmetros:
            value: Instância do modelo Sistema que está sendo validada

        Retorno:
            Sistema: A instância do sistema se a validação passar

        Lança:
            ValidationError: Se já existir uma relação para esta empresa e sistema

        Nota:
            Esta validação só é aplicada em operações de CREATE.
            Para UPDATE, use a validação no nível do objeto no EmpresaSistemaSerializer.
        """
        # Obtém o ID da empresa a partir dos parâmetros da URL
        empresa_id = self.context['view'].kwargs['empresa_id']

        # Verifica se já existe uma relação ativa para esta combinação
        if EmpresaSistema.objects.filter(empresa_id=empresa_id, sistema=value).exists():
            raise serializers.ValidationError(
                "Este sistema já está vinculado à empresa. "
                "Não é permitido criar relações duplicadas."
            )

        return value

    def create(self, validated_data):
        """
        Cria uma nova relação Empresa-Sistema.

        Sobrescreve o método padrão de criação para incluir automaticamente
        o empresa_id obtido da URL, evitando que o usuário precise enviá-lo.

        Parâmetros:
            validated_data: Dados validados para criação do objeto

        Retorno:
            EmpresaSistema: Nova instância criada

        Exemplo de uso:
            POST /sistemas/1/empresa/
            Body: {"sistema": 2, "ativo": true}
            Resultado: Cria relação entre empresa_id=1 e sistema_id=2
        """
        empresa_id = self.context['view'].kwargs['empresa_id']
        return EmpresaSistema.objects.create(empresa_id=empresa_id, **validated_data)


class EmpresaSistemaSerializer(serializers.ModelSerializer):
    """
    Serializer completo para o modelo EmpresaSistema.

    Utilizado para operações de RETRIEVE, UPDATE e DELETE em relações
    específicas através da URL:
    GET/PUT/DELETE /empresa-sistema/{pk}/

    Inclui campos computados para melhor experiência do usuário e
    validações robustas que funcionam tanto para CREATE quanto UPDATE.
    """

    # Campos computados para enriquecer a resposta
    sistema_nome = serializers.CharField(source='sistema.nome', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)

    class Meta:
        model = EmpresaSistema
        fields = ['id', 'sistema', 'sistema_nome', 'empresa', 'empresa_nome', 'ativo', 'max_funcionarios_registros', 'criar_banco']
        read_only_fields = ['id', 'sistema_nome', 'empresa', 'empresa_nome']

    def validate(self, attrs):
        """
        Validação em nível de objeto (cross-field validation).

        Executada após as validações individuais de cada campo.
        Verifica consistência entre múltiplos campos e aplica regras
        de negócio que envolvem mais de um campo.

        Parâmetros:
            attrs: Dicionário com todos os campos validados

        Retorno:
            dict: Atributos validados (potencialmente modificados)

        Lança:
            ValidationError: Se alguma regra de negócio for violada

        Comportamento:
            - Em CREATE: Verifica se não existe relação duplicada
            - Em UPDATE: Verifica duplicidade excluindo a instância atual
        """
        # Obtém a instância atual (None se for criação)
        instance = getattr(self, 'instance', None)

        # --- VALIDAÇÃO PARA OPERAÇÃO DE CRIAÇÃO ---
        if not instance and 'view' in self.context and 'empresa_id' in self.context['view'].kwargs:
            # Contexto de criação via URL com empresa_id
            empresa_id = self.context['view'].kwargs['empresa_id']
            sistema = attrs.get('sistema')

            # Verifica se já existe relação para esta empresa e sistema
            if EmpresaSistema.objects.filter(empresa_id=empresa_id, sistema=sistema).exists():
                raise serializers.ValidationError({
                    "sistema": "Este sistema já está vinculado à empresa. "
                    "Utilize a operação de update para modificar a relação existente."
                })

        # --- VALIDAÇÃO PARA OPERAÇÃO DE UPDATE ---
        elif instance and 'sistema' in attrs:
            # Contexto de update - verifica duplicidade excluindo o registro atual
            sistema = attrs['sistema']

            # Busca por relações duplicadas (mesma empresa e sistema, excluindo esta)
            duplicate_exists = EmpresaSistema.objects.filter(
                empresa_id=instance.empresa_id,  # Mantém a mesma empresa
                sistema=sistema                  # Novo sistema sendo atribuído
            ).exclude(id=instance.id).exists()   # Exclui o registro atual da verificação

            if duplicate_exists:
                raise serializers.ValidationError({
                    "sistema": "Não é possível alterar para este sistema pois "
                    "já existe outra relação para esta empresa. "
                    "ID da relação existente: {}".format(
                        EmpresaSistema.objects.filter(
                            empresa_id=instance.empresa_id,
                            sistema=sistema
                        ).first().id
                    )
                })

        return attrs

    def update(self, instance, validated_data):
        """
        Atualiza uma instância existente de EmpresaSistema.

        Parâmetros:
            instance: Instância existente a ser atualizada
            validated_data: Dados validados para a atualização

        Retorno:
            EmpresaSistema: Instância atualizada

        Nota:
            O método padrão do ModelSerializer já é suficiente para a maioria
            dos casos. Esta sobrescrita é opcional para lógicas customizadas.
        """
        # Exemplo de lógica customizada (descomente se necessário):
        # if 'ativo' in validated_data and not validated_data['ativo']:
        #     # Lógica adicional ao desativar uma relação
        #     logger.info(f"Relação {instance.id} desativada")

        return super().update(instance, validated_data)


class RotaSistemaModelSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo RotaSistema.

    Utilizado para operações CRUD básicas do cadastro de rotas dos sistemas.
    """
    class Meta:
        model = RotaSistema
        fields = '__all__'


class GrupoRotaSistemaListSerializer(serializers.ModelSerializer):
    """
    Serializer para LIST de GrupoRotaSistema com informações detalhadas.
    """
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)
    sistema_nome = serializers.CharField(source='sistema.nome', read_only=True)
    rotas_count = serializers.SerializerMethodField()
    rotas_detalhes = RotaSistemaModelSerializer(source='rotas', many=True, read_only=True)

    class Meta:
        model = GrupoRotaSistema
        fields = [
            'id', 'usuario', 'usuario_nome', 'sistema', 'sistema_nome',
            'nome', 'descricao', 'rotas_count', 'rotas_detalhes'
        ]
        read_only_fields = fields

    def get_rotas_count(self, obj):
        """Retorna a quantidade de rotas no grupo."""
        return obj.rotas.count()


class GrupoRotaSistemaCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREATE de GrupoRotaSistema que define automaticamente
    o usuário baseado no token logado.
    """

    # Campos read-only para mostrar informações úteis na resposta
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)
    sistema_nome = serializers.CharField(source='sistema.nome', read_only=True)

    class Meta:
        model = GrupoRotaSistema
        fields = ['id', 'usuario', 'usuario_nome', 'sistema', 'sistema_nome', 'nome', 'descricao', 'rotas']
        read_only_fields = ['id', 'usuario', 'usuario_nome', 'sistema_nome']

    def validate(self, attrs):
        """
        Validação customizada que define o usuário automaticamente.
        """
        # Define o usuário automaticamente baseado no request
        attrs['usuario'] = self.context['request'].user

        # Valida se o sistema pertence à mesma empresa do usuário (opcional)
        sistema = attrs.get('sistema')
        if sistema and hasattr(self.context['request'].user, 'empresa'):
            # Aqui você pode adicionar validações específicas se necessário
            # Por exemplo, verificar se o sistema está disponível para a empresa do usuário
            pass

        return attrs

    def create(self, validated_data):
        """
        Cria um novo GrupoRotaSistema garantindo que o usuário seja o logado.
        """
        # Extrai as rotas do validated_data (se existirem)
        rotas_data = validated_data.pop('rotas', [])

        # Cria o grupo
        grupo = GrupoRotaSistema.objects.create(**validated_data)

        # Adiciona as rotas se foram fornecidas
        if rotas_data:
            grupo.rotas.set(rotas_data)

        return grupo
