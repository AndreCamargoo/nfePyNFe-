# leads_api/tasks.py
import logging
import tempfile
import os

from celery import shared_task
from django.core.cache import cache
from .services.import_service import ImportService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='leads_api.tasks.import_leads_csv_task')
def import_leads_csv_task(self, file_content, filename, duplicate=False, file_type='csv'):
    """
    Task assíncrona para processar importação de leads (suporta CSV e XLSX)
    """
    task_id = self.request.id

    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 1, 'status': 'Iniciando processamento...'}
        )

        # Define a extensão correta baseada no tipo do arquivo
        extension = '.xlsx' if file_type == 'xlsx' else '.csv'
        
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(mode='wb', suffix=extension, delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 2, 'status': f'Processando arquivo {file_type.upper()}...'}
        )

        # Abre o arquivo para processamento
        with open(tmp_file_path, 'rb') as file:
            result = ImportService.process_csv(file, duplicate, celery=False)

        # Limpa arquivo temporário
        os.unlink(tmp_file_path)

        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 2, 'status': 'Finalizando...'}
        )

        # Salva resultado no cache
        cache.set(f'import_result_{task_id}', result, timeout=3600)

        return result

    except Exception as e:
        logger.error(f"Erro na task de importação: {str(e)}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={'exc': str(e), 'status': 'Erro no processamento'}
        )
        raise
