from django.db import connections
from django.conf import settings
from empresa.models import ConexaoBanco


class DatabaseManager:
    """Gerenciar conexões com bancos de empresas"""

    @staticmethod
    def configurar_conexao_empresa(empresa_id):
        """
        Configura a conexão com o banco da empresa e retorna o alias
        """
        try:
            # VERIFICAÇÃO SEGURA - primeiro verifica se existe
            if not DatabaseManager.empresa_tem_banco_proprio(empresa_id):
                print(f"Empresa {empresa_id} não tem banco próprio configurado")
                return None

            conexao = ConexaoBanco.objects.get(empresa_id=empresa_id)
            db_alias = f'empresa_{empresa_id}'

            # Verifica se já existe para evitar reconfiguração
            if db_alias in settings.DATABASES:
                return db_alias

            db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': conexao.get_database(),
                'USER': conexao.get_usuario(),
                'PASSWORD': conexao.get_senha(),
                'HOST': conexao.get_host(),
                'PORT': conexao.get_porta(),
                'OPTIONS': {
                    'options': '-c search_path=public'
                },
                'TIME_ZONE': None,
                'CONN_MAX_AGE': 60,
                'CONN_HEALTH_CHECKS': False,
                'ATOMIC_REQUESTS': False,
                'AUTOCOMMIT': True,
            }

            # Adiciona conexão
            settings.DATABASES[db_alias] = db_config
            connections.databases[db_alias] = db_config

            # Testa a conexão
            try:
                with connections[db_alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
                print(f"Conexão com banco da empresa {empresa_id} configurada com sucesso")
                return db_alias
            except Exception as conn_error:
                print(f"Erro ao conectar no banco da empresa {empresa_id}: {conn_error}")
                # Remove a conexão problemática
                if db_alias in settings.DATABASES:
                    del settings.DATABASES[db_alias]
                if db_alias in connections.databases:
                    del connections.databases[db_alias]
                return None

        except ConexaoBanco.DoesNotExist:
            print(f"Empresa {empresa_id} não tem banco próprio configurado")
            return None
        except Exception as e:
            print(f"Erro ao configurar banco da empresa {empresa_id}: {e}")
            return None

    @staticmethod
    def empresa_tem_banco_proprio(empresa_id):
        """
        Verifica se a empresa tem banco próprio configurado
        """
        try:
            # VERIFICAÇÃO SEGURA - sem usar campo 'status'
            return ConexaoBanco.objects.filter(empresa_id=empresa_id, status=True).exists()
        except Exception as e:
            print(f"Erro ao verificar banco próprio da empresa {empresa_id}: {e}")
            return False

    @staticmethod
    def usar_banco_empresa(empresa_id):
        """
        Define qual banco usar para as próximas queries dos modelos flat
        """
        try:
            db_alias = DatabaseManager.configurar_conexao_empresa(empresa_id)
            if db_alias:
                settings.EMPRESA_DATABASE_ALIAS = db_alias
                return True
            return False
        except Exception as e:
            print(f"Erro ao usar banco empresa: {e}")
            return False

    @staticmethod
    def limpar_conexao_empresa():
        """
        Limpa a configuração do banco da empresa
        """
        if hasattr(settings, 'EMPRESA_DATABASE_ALIAS'):
            delattr(settings, 'EMPRESA_DATABASE_ALIAS')
