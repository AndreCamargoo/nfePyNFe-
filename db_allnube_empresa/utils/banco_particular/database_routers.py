from django.conf import settings


class EmpresaDatabaseRouter:
    """
    Router para separar tabelas compartilhadas e específicas por empresa
    """

    # Apps que usam modelos flat nos bancos das empresas
    APPS_EMPRESA_FLAT = ['db_allnube_empresa']

    # Apps que usam modelos normais no banco default
    APPS_DEFAULT = [
        'nfe', 'nfe_evento', 'nfe_resumo',
        'empresa', 'sistema', 'authentication', 'auth',
        'django.contrib.contenttypes', 'django.contrib.sessions'
    ]

    def db_for_read(self, model, **hints):
        # Modelos do app db_allnube_empresa vão para o banco da empresa
        if model._meta.app_label in self.APPS_EMPRESA_FLAT:
            if hasattr(settings, 'EMPRESA_DATABASE_ALIAS'):
                return getattr(settings, 'EMPRESA_DATABASE_ALIAS')

        # Todos os outros apps vão para o default
        return 'default'

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permite relações apenas entre objetos do mesmo banco
        """
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Controla onde as migrações são aplicadas
        """
        # Apps flat só migram em bancos de empresa
        if app_label in self.APPS_EMPRESA_FLAT:
            return db.startswith('empresa_')

        # Apps normais só migram no default
        if app_label in self.APPS_DEFAULT:
            return db == 'default'

        # Outros apps (admin, etc) só no default
        return db == 'default'
