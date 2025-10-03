# acesso/serializers.py
from rest_framework import serializers
from acesso.models import UsuarioEmpresa, UsuarioSistema, UsuarioPermissaoRota


class UsuarioEmpresaModelSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo UsuarioEmpresa.
    """

    class Meta:
        model = UsuarioEmpresa
        fields = [
            "id", "nome", "email", "username", "password",
            "empresa", "cargo", "ativo", "criado_em", "atualizado_em",
        ]
        extra_kwargs = {
            "password": {"write_only": True}
        }

    def validate_empresa(self, value):
        """Valida se a empresa pertence ao usuário logado."""
        user = self.context['request'].user
        empresas_do_usuario = user.empresas.all()

        if value not in empresas_do_usuario:
            raise serializers.ValidationError(
                "Você não tem permissão para cadastrar funcionários nesta empresa."
            )
        return value

    def create(self, validated_data):
        """Cria um novo funcionário com validações de segurança."""
        user = self.context['request'].user
        empresa = validated_data.get('empresa')

        # Validação dupla de segurança
        if empresa not in user.empresas.all():
            raise serializers.ValidationError("Permissão negada para esta empresa.")

        password = validated_data.pop("password", None)
        instance = UsuarioEmpresa(**validated_data)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Atualiza um funcionário com validações de segurança."""
        user = self.context['request'].user

        # Verifica se o funcionário pertence ao usuário
        if instance.empresa not in user.empresas.all():
            raise serializers.ValidationError("Permissão negada para editar este funcionário.")

        # Valida nova empresa se for alterada
        if 'empresa' in validated_data:
            nova_empresa = validated_data['empresa']
            if nova_empresa not in user.empresas.all():
                raise serializers.ValidationError("Permissão negada para mover funcionário.")

        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class UsuarioSistemaModelModelSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo UsuarioSistema.
    """

    class Meta:
        model = UsuarioSistema
        fields = ["id", "usuario_empresa", "sistema", "ativo"]

    def validate_usuario_empresa(self, value):
        """Valida se o funcionário pertence ao usuário logado."""
        request = self.context.get('request')
        if not request:
            return value

        user = request.user
        empresas_do_usuario = user.empresas.all()

        if value.empresa not in empresas_do_usuario:
            raise serializers.ValidationError(
                "Este funcionário não pertence a nenhuma das suas empresas."
            )
        return value

    def validate(self, attrs):
        """Validações globais que envolvem múltiplos campos."""
        usuario_empresa = attrs.get('usuario_empresa')
        sistema = attrs.get('sistema')

        # Verifica duplicidade apenas na criação
        if usuario_empresa and sistema and not self.instance:
            existe = UsuarioSistema.objects.filter(
                usuario_empresa=usuario_empresa,
                sistema=sistema
            ).exists()

            if existe:
                raise serializers.ValidationError({
                    "non_field_errors": "Este funcionário já tem acesso a este sistema."
                })

        return attrs

    def create(self, validated_data):
        """Cria um novo UsuarioSistema com validações de segurança."""
        request = self.context.get('request')
        usuario_empresa = validated_data.get('usuario_empresa')

        # Validação dupla de segurança
        if request and usuario_empresa:
            empresas_do_usuario = request.user.empresas.all()
            if usuario_empresa.empresa not in empresas_do_usuario:
                raise serializers.ValidationError("Permissão negada para este funcionário.")

        instance = UsuarioSistema(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Atualiza um UsuarioSistema com validações de segurança."""
        request = self.context.get('request')

        # Verifica permissão para o registro atual
        if request and instance.usuario_empresa.empresa not in request.user.empresas.all():
            raise serializers.ValidationError("Permissão negada para editar este registro.")

        # Valida novo funcionário se for alterado
        if 'usuario_empresa' in validated_data:
            novo_funcionario = validated_data['usuario_empresa']
            if request and novo_funcionario.empresa not in request.user.empresas.all():
                raise serializers.ValidationError("Permissão negada para este funcionário.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class UsuarioPermissaoRotaModelModelSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo UsuarioPermissaoRota.
    Agora suporta tanto rota específica quanto grupo de rotas.
    """

    class Meta:
        model = UsuarioPermissaoRota
        fields = ["id", "usuario_sistema", "rota", "grupo", "permitido"]

    def validate(self, attrs):
        """Validações globais que envolvem múltiplos campos."""
        usuario_sistema = attrs.get('usuario_sistema')
        rota = attrs.get('rota')
        grupo = attrs.get('grupo')

        # Valida que pelo menos rota ou grupo deve ser fornecido
        if not rota and not grupo:
            raise serializers.ValidationError({
                "non_field_errors": "Pelo menos uma rota ou um grupo deve ser fornecido."
            })

        # Valida que não pode ter ambos
        if rota and grupo:
            raise serializers.ValidationError({
                "non_field_errors": "Apenas uma rota ou um grupo pode ser fornecido, não ambos."
            })

        # Verifica se a rota pertence ao mesmo sistema do usuario_sistema
        if usuario_sistema and rota:
            if usuario_sistema.sistema != rota.sistema:
                raise serializers.ValidationError({
                    "rota": "A rota deve pertencer ao mesmo sistema do usuário."
                })

        # Verifica se o grupo pertence ao mesmo sistema do usuario_sistema
        if usuario_sistema and grupo:
            if usuario_sistema.sistema != grupo.sistema:
                raise serializers.ValidationError({
                    "grupo": "O grupo deve pertencer ao mesmo sistema do usuário."
                })

        # Verifica duplicidade apenas na criação
        if usuario_sistema and not self.instance:
            if rota:
                existe = UsuarioPermissaoRota.objects.filter(
                    usuario_sistema=usuario_sistema,
                    rota=rota
                ).exists()
                if existe:
                    raise serializers.ValidationError({
                        "non_field_errors": "Este usuário do sistema já tem esta permissão de rota."
                    })
            elif grupo:
                existe = UsuarioPermissaoRota.objects.filter(
                    usuario_sistema=usuario_sistema,
                    grupo=grupo
                ).exists()
                if existe:
                    raise serializers.ValidationError({
                        "non_field_errors": "Este usuário do sistema já tem esta permissão de grupo."
                    })

        return attrs

    def validate_usuario_sistema(self, value):
        """Valida se o UsuarioSistema pertence ao usuário logado."""
        request = self.context.get('request')
        if not request:
            return value

        user = request.user
        empresas_do_usuario = user.empresas.all()

        if value.usuario_empresa.empresa not in empresas_do_usuario:
            raise serializers.ValidationError(
                "Este usuário do sistema não pertence a nenhuma das suas empresas."
            )
        return value

    def validate_rota(self, value):
        """Valida se a rota pertence a um sistema acessível."""
        request = self.context.get('request')
        if not request:
            return value

        # Aqui você pode adicionar validações específicas para rotas se necessário
        return value

    def validate_grupo(self, value):
        """Valida se o grupo pertence a um sistema acessível."""
        request = self.context.get('request')
        if not request:
            return value

        # Aqui você pode adicionar validações específicas para grupos se necessário
        return value

    def create(self, validated_data):
        """Cria um novo UsuarioPermissaoRota com validações de segurança."""
        request = self.context.get('request')
        usuario_sistema = validated_data.get('usuario_sistema')

        # Validação dupla de segurança
        if request and usuario_sistema:
            empresas_do_usuario = request.user.empresas.all()
            if usuario_sistema.usuario_empresa.empresa not in empresas_do_usuario:
                raise serializers.ValidationError("Permissão negada para este usuário do sistema.")

        instance = UsuarioPermissaoRota(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Atualiza um UsuarioPermissaoRota com validações de segurança."""
        request = self.context.get('request')

        # Verifica permissão para o registro atual
        if request and instance.usuario_sistema.usuario_empresa.empresa not in request.user.empresas.all():
            raise serializers.ValidationError("Permissão negada para editar este registro.")

        # Valida novo usuario_sistema se for alterado
        if 'usuario_sistema' in validated_data:
            novo_usuario_sistema = validated_data['usuario_sistema']
            if request and novo_usuario_sistema.usuario_empresa.empresa not in request.user.empresas.all():
                raise serializers.ValidationError("Permissão negada para este usuário do sistema.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
