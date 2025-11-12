from rest_framework import serializers
from .models import CircularizacaoCliente, CircularizacaoAcesso, CircularizacaoArquivoRecebido


class CircularizacaoClienteModelSerializer(serializers.ModelSerializer):
    # Campo para escrita apenas (não é retornado na leitura)
    senha = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CircularizacaoCliente
        fields = ['id', 'usuario', 'uri', 'senha', 'ano_vigente', 'status', 'criado_em', 'atualizado_em']
        read_only_fields = ['uri', 'criado_em', 'atualizado_em']

    def create(self, validated_data):
        senha_plana = validated_data.pop('senha', None)
        cliente = CircularizacaoCliente.objects.create(**validated_data)

        if senha_plana:
            cliente.set_senha(senha_plana)
            cliente.save()
        else:
            raise serializers.ValidationError({"senha": "Este campo é obrigatório."})

        return cliente

    def update(self, instance, validated_data):
        senha = validated_data.pop('senha', None)

        # Atualiza outros campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Atualiza senha se fornecida
        if senha:
            instance.set_senha(senha)

        instance.save()
        return instance


class CircularizacaoAcessoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircularizacaoAcesso
        fields = ['id', 'cliente', 'tipo', 'codigo', 'ordem', 'destinatario_nome', 'criado_em', 'atualizado_em', 'deletado_em']
        read_only_fields = ['criado_em', 'atualizado_em', 'deletado_em']


class CircularizacaoArquivoRecebidoModelSerializer(serializers.ModelSerializer):
    senha = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CircularizacaoArquivoRecebido
        fields = ['id', 'acesso', 'senha', 'nome_arquivo_original', 'extensao_arquivo', 'arquivo', 'criado_em']
        read_only_fields = ['nome_arquivo_original', 'extensao_arquivo', 'criado_em']

    def validate(self, attrs):
        acesso = attrs.get('acesso')
        senha_fornecida = attrs.get('senha')

        if not acesso or not senha_fornecida:
            raise serializers.ValidationError({
                "erro": "Acesso e senha são obrigatórios"
            })

        cliente = acesso.cliente

        try:
            senha_correta = cliente.get_senha()

            print(senha_correta, senha_fornecida)

            if senha_fornecida != senha_correta:
                raise serializers.ValidationError({
                    "senha": "Senha incorreta"
                })
        except serializers.ValidationError:
            # Repassa direto esse erro (sem alterar)
            raise
        except ValueError:
            raise serializers.ValidationError({
                "senha": "Erro ao descriptografar senha. Contate o administrador."
            })
        except Exception as e:
            raise serializers.ValidationError({
                "senha": f"Erro inesperado: {str(e)}"
            })

        attrs.pop('senha')
        return attrs

    def create(self, validated_data):
        # A senha já foi validada e removida do validated_data no validate()
        arquivo = validated_data.get('arquivo')

        # Cria a instância
        instance = CircularizacaoArquivoRecebido.objects.create(**validated_data)

        # Se nome_arquivo_original não foi fornecido, usa o nome do arquivo
        if arquivo and not instance.nome_arquivo_original:
            instance.nome_arquivo_original = arquivo.name

        # Se extensao_arquivo não foi fornecido, extrai do nome do arquivo
        if arquivo and not instance.extensao_arquivo:
            import os
            nome, extensao = os.path.splitext(arquivo.name)
            instance.extensao_arquivo = extensao.lower().replace('.', '')

        instance.save()
        return instance

    def update(self, instance, validated_data):
        # Remove a senha se estiver presente (não usada no update)
        validated_data.pop('senha', None)

        arquivo = validated_data.get('arquivo')

        # Atualiza os campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Se um novo arquivo foi enviado, atualiza nome e extensão
        if arquivo:
            if not instance.nome_arquivo_original:
                instance.nome_arquivo_original = arquivo.name

            import os
            nome, extensao = os.path.splitext(arquivo.name)
            instance.extensao_arquivo = extensao.lower().replace('.', '')

        instance.save()
        return instance
