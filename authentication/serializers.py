from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from empresa.models import Empresa, Funcionario
from sistema.models import EmpresaSistema


class CustomTokenObtainSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(
                request=self.context.get('request'),
                username=username, password=password
            )

            if not user:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = 'Must include "username" and "password".'
            raise serializers.ValidationError(msg, code='authorization')

        # ==============================================
        # VALIDAÇÕES ADICIONAIS DE VÍNCULO EMPRESARIAL
        # ==============================================

        # Verificar se o usuário tem alguma empresa ativa (como dono)
        empresas_como_dono = Empresa.objects.filter(
            usuario=user,
            status='1'
        )

        # Verificar se o usuário é funcionário ativo de alguma empresa
        funcionarios_ativos = Funcionario.objects.filter(
            user=user,
            status='1'
        ).select_related('empresa')

        # Filtrar apenas empresas ativas
        funcionarios_ativos = [f for f in funcionarios_ativos if f.empresa.status == '1']

        # Verificar se o usuário tem acesso a pelo menos um sistema ativo
        tem_acesso_sistema = False
        sistemas_acesso = []

        # Verificar nas empresas onde é dono
        for empresa in empresas_como_dono:
            # Verificar se a empresa tem sistemas ativos
            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            if sistemas_ativos.exists():
                tem_acesso_sistema = True
                for sistema in sistemas_ativos:
                    sistemas_acesso.append({
                        'empresa_id': empresa.id,
                        'empresa_nome': empresa.razao_social,
                        'sistema_id': sistema.sistema.id,
                        'sistema_nome': sistema.sistema.nome,
                        'role': 'admin'
                    })

        # Verificar nos vínculos de funcionário
        for funcionario in funcionarios_ativos:
            empresa = funcionario.empresa
            # Verificar se a empresa tem sistemas ativos
            sistemas_ativos = EmpresaSistema.objects.filter(
                empresa=empresa,
                ativo=True
            ).select_related('sistema')

            if sistemas_ativos.exists():
                tem_acesso_sistema = True
                for sistema in sistemas_ativos:
                    sistemas_acesso.append({
                        'empresa_id': empresa.id,
                        'empresa_nome': empresa.razao_social,
                        'sistema_id': sistema.sistema.id,
                        'sistema_nome': sistema.sistema.nome,
                        'role': funcionario.role
                    })

        # Se não tem acesso a nenhum sistema, bloquear login
        if not tem_acesso_sistema:
            raise serializers.ValidationError({
                'detail': 'Seu usuário não possui acesso a nenhum sistema ativo. '
                'Entre em contato com o administrador para contratar o serviço.',
                'code': 'no_active_system'
            })

        # Guardar informações no validated_data para uso posterior
        attrs['user'] = user
        attrs['sistemas_acesso'] = sistemas_acesso

        return attrs
