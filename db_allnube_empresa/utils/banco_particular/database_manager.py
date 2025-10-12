from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
from django.core.management import call_command
from empresa.models import Empresa, ConexaoBanco


class Command(BaseCommand):
    help = 'Gerencia migrações para empresas com banco próprio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa_id',
            type=int,
            help='ID específico da empresa para migrar'
        )
        parser.add_argument(
            '--verificar',
            action='store_true',
            help='Apenas verificar migrações pendentes'
        )
        parser.add_argument(
            '--tudo',
            action='store_true',
            help='Criar e migrar TUDO (default + empresas)'
        )
        parser.add_argument(
            '--criar',
            action='store_true',
            help='Criar arquivos de migração'
        )
        parser.add_argument(
            '--default',
            action='store_true',
            help='Migrar apenas o banco DEFAULT'
        )
        parser.add_argument(
            '--cliente',
            action='store_true',
            help='Migrar apenas bancos dos CLIENTES (empresas)'
        )
        parser.add_argument(
            '--apps',
            type=str,
            help='Apps específicos para migrar (separados por vírgula)'
        )
        parser.add_argument(
            '--testar',
            action='store_true',
            help='Apenas testar conexões sem migrar'
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando gerenciamento de migrações...")

        if options['testar']:
            self.testar_conexoes()
            return

        if options['verificar']:
            self.verificar_migracoes()
            return

        if options['criar']:
            self.criar_migracoes()

        # Determina quais apps migrar
        apps = None
        if options['apps']:
            apps = [app.strip() for app in options['apps'].split(',')]

        if options['tudo']:
            self.migrar_tudo(apps)
            return

        if options['default']:
            self.migrar_banco_default(apps)
            return

        if options['cliente']:
            self.migrar_todas_empresas(apps)
            return

        empresa_id = options.get('empresa_id')
        if empresa_id:
            self.migrar_empresa_especifica(empresa_id, apps)
        else:
            self.stdout.write(self.style.WARNING(
                "Especifique o banco para migrar:\n"
                "--default      (banco principal)\n"
                "--cliente      (bancos dos clientes)\n"
                "--tudo         (todos os bancos)\n"
                "--empresa_id X (empresa específica)\n"
                "--testar       (testar conexões)"
            ))

    def configurar_banco_empresa(self, empresa_id):
        """Configura conexão com banco da empresa - VERSÃO SIMPLIFICADA"""
        try:
            conexao = ConexaoBanco.objects.get(empresa_id=empresa_id)
            db_alias = f'empresa_{empresa_id}'

            # CONFIGURAÇÃO COMPLETA - todas as chaves que o Django pode procurar
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
                'CONN_MAX_AGE': 0,
                'CONN_HEALTH_CHECKS': False,
                'ATOMIC_REQUESTS': False,
                'AUTOCOMMIT': True,
                'TEST': {
                    'NAME': None,
                }
            }

            # Adiciona conexão se não existir
            if db_alias not in settings.DATABASES:
                settings.DATABASES[db_alias] = db_config
                connections.databases[db_alias] = db_config

            # Testa a conexão
            try:
                with connections[db_alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
                self.stdout.write(f"Banco da empresa {empresa_id} configurado: {db_alias}")
                return db_alias
            except Exception as conn_error:
                self.stdout.write(self.style.ERROR(f"Erro ao conectar com banco {db_alias}: {conn_error}"))
                # Limpa a conexão problemática
                self.limpar_conexao_empresa(db_alias)
                return None

        except ConexaoBanco.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"Empresa {empresa_id} não tem banco próprio"))
            return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao configurar banco da empresa {empresa_id}: {e}"))
            return None

    def limpar_conexao_empresa(self, db_alias):
        """Remove configuração de conexão problemática"""
        if db_alias in settings.DATABASES:
            del settings.DATABASES[db_alias]
        if db_alias in connections.databases:
            del connections.databases[db_alias]
        if hasattr(settings, 'EMPRESA_DATABASE_ALIAS'):
            delattr(settings, 'EMPRESA_DATABASE_ALIAS')

    def testar_conexoes(self):
        """Apenas testa as conexões com os bancos"""
        self.stdout.write("Testando conexões com bancos...")

        # Testa banco default
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write("Banco DEFAULT: OK")
        except Exception as e:
            self.stdout.write(f"Banco DEFAULT: {e}")

        # Testa empresas
        try:
            empresas_com_banco = Empresa.objects.filter(conexao_banco__isnull=False)
            self.stdout.write(f"Encontradas {empresas_com_banco.count()} empresas com banco próprio")

            for empresa in empresas_com_banco:
                db_alias = self.configurar_banco_empresa(empresa.id)
                if db_alias:
                    self.stdout.write(f"Empresa {empresa.razao_social}: CONEXÃO OK")
                else:
                    self.stdout.write(f"Empresa {empresa.razao_social}: FALHA NA CONEXÃO")

        except Exception as e:
            self.stdout.write(f"Erro ao testar empresas: {e}")

    def criar_migracoes(self):
        """Cria arquivos de migração"""
        self.stdout.write("Criando arquivos de migração...")
        try:
            call_command('makemigrations', 'db_allnube_empresa', verbosity=1)
            self.stdout.write(self.style.SUCCESS("Migrações criadas para db_allnube_empresa"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao criar migrações: {e}"))

    def migrar_banco_default(self, apps=None):
        """Migra apenas o banco default"""
        self.stdout.write("Migrando banco DEFAULT...")
        try:
            call_command('migrate', verbosity=1)
            self.stdout.write(self.style.SUCCESS("Banco DEFAULT migrado com sucesso!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao migrar banco DEFAULT: {e}"))

    def migrar_empresa_especifica(self, empresa_id, apps=None):
        """Migra uma empresa específica"""
        self.stdout.write(f"Migrando empresa ID: {empresa_id}")

        # Configura e migra o banco da empresa
        db_alias = self.configurar_banco_empresa(empresa_id)

        if db_alias:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
                self.stdout.write(f"Migrando: {empresa.razao_social}")

                # Migra APENAS o app db_allnube_empresa no banco da empresa
                call_command('migrate', 'db_allnube_empresa', database=db_alias, verbosity=1)
                self.stdout.write(self.style.SUCCESS(f"Empresa {empresa.razao_social} migrada com sucesso!"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao migrar empresa {empresa_id}: {e}"))

    def migrar_todas_empresas(self, apps=None):
        """Migra todas as empresas com banco próprio"""
        self.stdout.write("Migrando TODAS as empresas...")

        try:
            empresas_com_banco = Empresa.objects.filter(conexao_banco__isnull=False)
            self.stdout.write(f"Encontradas {empresas_com_banco.count()} empresas com banco próprio")

            if not empresas_com_banco.exists():
                self.stdout.write(self.style.WARNING("Nenhuma empresa com banco próprio encontrada"))
                return

            for empresa in empresas_com_banco:
                self.migrar_empresa_especifica(empresa.id, apps)

            self.stdout.write(self.style.SUCCESS("Todas as empresas migradas com sucesso!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao migrar empresas: {e}"))

    def migrar_tudo(self, apps=None):
        """Fluxo completo de migração"""
        self.stdout.write("Iniciando migração COMPLETA...")

        # 1. Migrar banco default primeiro
        self.migrar_banco_default(apps)

        # 2. Migrar todas as empresas
        self.migrar_todas_empresas(apps)

        self.stdout.write(self.style.SUCCESS("TODAS as migrações concluídas!"))

    def verificar_migracoes(self):
        """Verifica migrações pendentes"""
        self.stdout.write("Verificando migrações pendentes...")
        try:
            call_command('showmigrations', verbosity=1)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao verificar migrações: {e}"))
