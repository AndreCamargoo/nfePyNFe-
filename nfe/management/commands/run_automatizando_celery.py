from django.core.management.base import BaseCommand
from nfe.tasks import automatizar_nfe_task


class Command(BaseCommand):
    help = 'Dispara a task Celery de automação NFe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--async',
            action='store_true',
            help='Executar de forma assíncrona (via Celery)',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Executar de forma síncrona (para debug)',
        )

    def handle(self, *args, **options):
        if options['sync']:
            self.stdout.write("[INFO] Executando automação de forma SÍNCRONA...")
            result = automatizar_nfe_task.apply_async().get()
            self.stdout.write(f"[RESULT] {result}")
        elif options['async']:
            self.stdout.write("[INFO] Disparando automação de forma ASSÍNCRONA...")
            result = automatizar_nfe_task.delay()
            self.stdout.write(f"[TASK ID] {result.id}")
            self.stdout.write("[INFO] Use 'celery -A app inspect active' para ver o progresso")
        else:
            self.stdout.write("[INFO] Disparando automação...")
            result = automatizar_nfe_task.delay()
            self.stdout.write(f"[TASK ID] {result.id}")
