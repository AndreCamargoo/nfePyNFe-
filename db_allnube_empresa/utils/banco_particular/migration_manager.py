from django.core.management import call_command
from empresa.models import Empresa
from .database_manager import DatabaseManager


class MigrationManager:
    """Gerenciador de migrações para múltiplos bancos"""

    # Apps que serão migrados nos bancos das empresas
    APPS_MIGRACAO_EMPRESA = ['db_allnube_empresa']

    # Apps que ficam no banco default
    APPS_MIGRACAO_DEFAULT = ['nfe', 'nfe_evento', 'nfe_resumo']

    @staticmethod
    def criar_migracoes():
        """Cria arquivos de migração para todos os apps"""
        print("Criando arquivos de migração...")

        # Cria migrações para apps default
        for app in MigrationManager.APPS_MIGRACAO_DEFAULT:
            try:
                call_command('makemigrations', app, verbosity=1)
                print(f"Migração criada para app DEFAULT: {app}")
            except Exception as e:
                print(f"Erro ao criar migração para {app}: {e}")

        # Cria migrações para apps empresa
        for app in MigrationManager.APPS_MIGRACAO_EMPRESA:
            try:
                call_command('makemigrations', app, verbosity=1)
                print(f"Migração criada para app EMPRESA: {app}")
            except Exception as e:
                print(f"Erro ao criar migração para {app}: {e}")

        print("Arquivos de migração criados com sucesso!")

    @staticmethod
    def migrar_banco_default():
        """Executa migrações no banco default"""
        print("\nMigrando banco DEFAULT...")
        try:
            # Migra apenas os apps que devem ficar no default
            for app in MigrationManager.APPS_MIGRACAO_DEFAULT:
                call_command('migrate', app, verbosity=1)
            print("Banco DEFAULT migrado com sucesso!")
        except Exception as e:
            print(f"Erro ao migrar banco DEFAULT: {e}")

    @staticmethod
    def migrar_banco_empresa(empresa_id, apps=None):
        """
        Executa migrações para o banco de uma empresa específica
        Apenas migra os models flat do app db_allnube_empresa
        """
        try:
            # Configura a conexão da empresa
            db_alias = DatabaseManager.configurar_banco_empresa(empresa_id)

            if db_alias:
                empresa = Empresa.objects.get(id=empresa_id)
                print(f"\nMigrando empresa: {empresa.razao_social} (ID: {empresa_id}) - Banco: {db_alias}")

                # Define quais apps migrar
                apps_migrar = apps or MigrationManager.APPS_MIGRACAO_EMPRESA

                # Migra APENAS os models flat para o banco da empresa
                for app in apps_migrar:
                    print(f"Migrando app {app}...")
                    try:
                        call_command('migrate', app, database=db_alias, verbosity=1)
                        print(f"{app} migrado com sucesso")
                    except Exception as e:
                        print(f"Erro ao migrar {app}: {e}")

                print(f"Migrações concluídas para {empresa.razao_social}")
            else:
                print(f"Empresa {empresa_id} não tem banco próprio")

        except Empresa.DoesNotExist:
            print(f"Empresa {empresa_id} não encontrada")
        except Exception as e:
            print(f"Erro ao migrar banco da empresa {empresa_id}: {e}")

    @staticmethod
    def migrar_todas_empresas(apps=None):
        """
        Executa migrações para todas as empresas com banco próprio
        """
        empresas_com_banco = DatabaseManager.obter_empresas_com_banco()

        print(f"\nEncontradas {empresas_com_banco.count()} empresas com banco próprio")

        if not empresas_com_banco.exists():
            print("Nenhuma empresa com banco próprio encontrada")
            return

        for empresa in empresas_com_banco:
            MigrationManager.migrar_banco_empresa(empresa.id, apps)

        print("\nMigrações concluídas para todas as empresas!")

    @staticmethod
    def verificar_migracoes_pendentes():
        """Verifica migrações pendentes"""
        print("Verificando migrações pendentes no banco DEFAULT...")
        try:
            call_command('showmigrations', verbosity=1)
        except Exception as e:
            print(f"Erro ao verificar migrações: {e}")
