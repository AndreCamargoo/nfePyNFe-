"""
Comandos úteis:

# Migrar apenas o banco DEFAULT
python manage.py migrar_empresas --default

# Migrar apenas bancos dos CLIENTES
python manage.py migrar_empresas --cliente

# Migrar empresa específica
python manage.py migrar_empresas --empresa_id 1

# Migrar tudo (default + empresas)
python manage.py migrar_empresas --tudo

# Apenas verificar migrações pendentes
python manage.py migrar_empresas --verificar

# Criar arquivos de migração
python manage.py migrar_empresas --criar

# Testar conexões com bancos
python manage.py migrar_empresas --testar
"""

from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
from django.core.management import call_command
from empresa.models import Empresa, ConexaoBanco


class Command(BaseCommand):
    help = 'Gerencia migrações para empresas com banco próprio - VERSÃO SIMPLIFICADA'

    def add_arguments(self, parser):
        parser.add_argument('--empresa_id', type=int, help='ID específico da empresa para migrar')
        parser.add_argument('--verificar', action='store_true', help='Apenas verificar migrações pendentes')
        parser.add_argument('--tudo', action='store_true', help='Criar e migrar TUDO (default + empresas)')
        parser.add_argument('--criar', action='store_true', help='Criar arquivos de migração')
        parser.add_argument('--default', action='store_true', help='Migrar apenas o banco DEFAULT')
        parser.add_argument('--cliente', action='store_true', help='Migrar apenas bancos dos CLIENTES (empresas)')
        parser.add_argument('--testar', action='store_true', help='Apenas testar conexões sem migrar')

    def handle(self, *args, **options):
        if options['testar']:
            self.testar_conexoes()
            return

        if options['verificar']:
            self.verificar_migracoes()
            return

        if options['criar']:
            self.criar_migracoes()
            return

        if options['tudo']:
            self.migrar_banco_default()
            self.migrar_todas_empresas()
            return

        if options['default']:
            self.migrar_banco_default()
            return

        if options['cliente']:
            self.migrar_todas_empresas()
            return

        if options['empresa_id']:
            self.migrar_empresa_especifica(options['empresa_id'])
            return

        self.stdout.write(self.style.WARNING(
            "Especifique uma opção: --default, --cliente, --tudo, --empresa_id X, --verificar, --criar, --testar"
        ))

    # -------------------
    # Conexões e testes
    # -------------------
    def configurar_banco_empresa(self, empresa_id):
        try:
            conexao = ConexaoBanco.objects.get(empresa_id=empresa_id)
            db_alias = f'empresa_{empresa_id}'

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

            if db_alias not in settings.DATABASES:
                settings.DATABASES[db_alias] = db_config
                connections.databases[db_alias] = db_config

            settings.EMPRESA_DATABASE_ALIAS = db_alias
            return db_alias

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao configurar banco da empresa {empresa_id}: {e}"))
            return None

    def testar_conexoes(self):
        self.stdout.write("Testando conexões com bancos...")
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write("Banco DEFAULT: OK")
        except Exception as e:
            self.stdout.write(f"Banco DEFAULT: {e}")

        empresas = Empresa.objects.filter(conexao_banco__isnull=False)
        for empresa in empresas:
            db_alias = self.configurar_banco_empresa(empresa.id)
            if db_alias:
                self.stdout.write(f"Empresa {empresa.razao_social}: CONEXÃO OK")
            else:
                self.stdout.write(f"Empresa {empresa.razao_social}: FALHA NA CONEXÃO")

    # -------------------
    # Migrações
    # -------------------
    def criar_migracoes(self):
        self.stdout.write("Criando arquivos de migração...")
        # self.forcar_managed_true(['db_allnube_empresa'])
        try:
            call_command('makemigrations', 'db_allnube_empresa', verbosity=1)
            self.stdout.write(self.style.SUCCESS("Migrações criadas para db_allnube_empresa"))
        finally:
            # self.restaurar_managed_false(['db_allnube_empresa'])
            ...

    def migrar_banco_default(self):
        self.stdout.write("Migrando banco DEFAULT...")
        call_command('migrate', verbosity=1)
        self.stdout.write(self.style.SUCCESS("Banco DEFAULT migrado!"))

    def migrar_empresa_especifica(self, empresa_id):
        db_alias = self.configurar_banco_empresa(empresa_id)
        if not db_alias:
            return
        self.stdout.write(f"Migrando empresa {empresa_id} no banco {db_alias}...")
        # self.forcar_managed_true(['db_allnube_empresa'])
        try:
            call_command('migrate', 'db_allnube_empresa', database=db_alias, verbosity=1)
            self.stdout.write(self.style.SUCCESS(f"Empresa {empresa_id} migrada com sucesso!"))
        finally:
            # self.restaurar_managed_false(['db_allnube_empresa'])
            ...

    def migrar_todas_empresas(self):
        empresas = Empresa.objects.filter(conexao_banco__isnull=False)
        for empresa in empresas:
            self.migrar_empresa_especifica(empresa.id)

    def verificar_migracoes(self):
        self.stdout.write("Verificando migrações pendentes...")
        call_command('showmigrations', verbosity=1)

    # -------------------
    # Helpers para managed=False
    # -------------------
    def forcar_managed_true(self, apps_labels):
        from django.apps import apps
        if isinstance(apps_labels, str):
            apps_labels = [apps_labels]
        for app_label in apps_labels:
            for model in apps.get_app_config(app_label).get_models():
                if not model._meta.managed:
                    model._meta.original_managed = model._meta.managed
                    model._meta.managed = True
                    self.stdout.write(f"Temporariamente: {model._meta.model_name} -> managed=True")

    def restaurar_managed_false(self, apps_labels):
        from django.apps import apps
        if isinstance(apps_labels, str):
            apps_labels = [apps_labels]
        for app_label in apps_labels:
            for model in apps.get_app_config(app_label).get_models():
                if hasattr(model._meta, 'original_managed'):
                    model._meta.managed = model._meta.original_managed
                    delattr(model._meta, 'original_managed')
                    self.stdout.write(f"Restaurado: {model._meta.model_name} -> managed={model._meta.managed}")
