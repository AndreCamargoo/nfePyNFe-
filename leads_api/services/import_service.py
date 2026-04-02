# leads_api/services/import_service.py
import csv
import json
import io
import re
import ast
import logging
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from django.core.cache import cache
from leads_api.models import Lead, Company, Product, Contact, Cnes
import openpyxl
from openpyxl import load_workbook

logger = logging.getLogger(__name__)


class ImportService:
    @staticmethod
    def detect_file_type(file):
        """
        Detecta se o arquivo é CSV ou XLSX baseado na extensão e no conteúdo
        """
        filename = getattr(file, 'name', '')
        
        if filename.lower().endswith('.xlsx'):
            return 'xlsx'
        elif filename.lower().endswith('.xls'):
            return 'xls'
        elif filename.lower().endswith('.csv'):
            return 'csv'
        
        file.seek(0)
        header = file.read(4)
        file.seek(0)
        
        if header.startswith(b'PK'):
            return 'xlsx'
        elif header.startswith(b'\xD0\xCF\x11\xE0'):
            return 'xls'
        else:
            return 'csv'
    
    @staticmethod
    def read_xlsx_file(file):
        """
        Lê arquivo XLSX e retorna lista de dicionários
        """
        workbook = load_workbook(file, data_only=True)
        sheet = workbook.active
        
        headers = []
        for cell in sheet[1]:
            if cell.value:
                headers.append(str(cell.value).strip())
            else:
                headers.append('')
        
        rows = []
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            row_data = {}
            has_data = False
            for idx, value in enumerate(row):
                if idx < len(headers) and headers[idx]:
                    # Converte None para string vazia
                    cell_value = str(value).strip() if value is not None else ''
                    if cell_value:
                        has_data = True
                    row_data[headers[idx]] = cell_value
            if has_data:
                rows.append((row_idx, row_data))
        
        return rows
    
    @staticmethod
    def read_csv_file(file):
        """
        Lê arquivo CSV e retorna lista de dicionários
        """
        try:
            decoded_file = file.read().decode('utf-8')
        except UnicodeDecodeError:
            file.seek(0)
            decoded_file = file.read().decode('latin-1')
        
        if decoded_file.startswith('\ufeff'):
            decoded_file = decoded_file[1:]
        
        if decoded_file.startswith('ï»¿'):
            decoded_file = decoded_file[3:]
        
        io_string = io.StringIO(decoded_file)
        first_line = io_string.readline()
        io_string.seek(0)
        
        delimiter = ';' if ';' in first_line else ','
        reader = csv.DictReader(io_string, delimiter=delimiter)
        
        if not reader.fieldnames:
            raise Exception("Arquivo CSV vazio ou formato inválido")
        
        rows = []
        for idx, row in enumerate(reader, start=2):
            clean_row = {}
            has_data = False
            for key, value in row.items():
                if key and value:
                    clean_key = key.strip()
                    clean_value = value.strip() if value else ''
                    if clean_value:
                        has_data = True
                    clean_row[clean_key] = clean_value
            if has_data:
                rows.append((idx, clean_row))
        
        return rows
    
    @staticmethod
    def process_csv(file, duplicate=False, celery=True):
        """
        Processa arquivo de importação de leads (suporta CSV e XLSX)
        """
        if celery:
            from leads_api.tasks import import_leads_csv_task
            
            file.seek(0)
            file_content = file.read()
            file_type = ImportService.detect_file_type(file)
            
            task = import_leads_csv_task.delay(file_content, file.name, duplicate, file_type)
            
            return {
                "task_id": task.id,
                "status": "processing",
                "message": "Importação iniciada em background",
                "file_type": file_type
            }
        
        return ImportService._process_file_sync(file, duplicate)
    
    @staticmethod
    def _process_file_sync(file, duplicate=False):
        """
        Processamento síncrono do arquivo (CSV ou XLSX)
        """
        file_type = ImportService.detect_file_type(file)

        if file_type in ['xlsx', 'xls']:
            rows = ImportService.read_xlsx_file(file)
        else:
            rows = ImportService.read_csv_file(file)

        results = {
            "created": 0,
            "updated": 0,
            "errors": [],
            "cnes_encontrados": 0,
            "cnes_nao_encontrados": 0,
            "invalid_rows": [],
            "success_rows": [],
            "file_type": file_type,
            "total_rows": len(rows)
        }

        cnes_cache = {}

        # Processa cada linha individualmente - SEM transaction.atomic global
        for row_num, row in rows:
            try:
                # Limpa os dados da linha
                clean_row = {}
                for old_key, value in row.items():
                    if not old_key:
                        continue
                    clean_key = old_key.strip().replace('\ufeff', '').replace('ï»¿', '').strip()
                    clean_value = value.strip() if value else ""
                    clean_row[clean_key] = clean_value

                # Pula linhas de comentário
                if clean_row.get('Nome da conta', '').startswith('#'):
                    continue

                # VERIFICAÇÃO: Pelo menos Nome da conta ou CNPJ preenchido
                nome_conta = clean_row.get('Nome da conta', '')
                cnpj = clean_row.get('CNPJ', '')

                if not nome_conta and not cnpj:
                    results['invalid_rows'].append({
                        "linha": row_num,
                        "motivo": "Nome da conta ou CNPJ não preenchido",
                        "dados": clean_row
                    })
                    continue

                # Processa a linha em uma transação separada
                try:
                    with transaction.atomic():
                        created = ImportService._process_row(clean_row, results, duplicate, cnes_cache)
                        if created:
                            results['created'] += 1
                            results['success_rows'].append(row_num)
                        else:
                            results['updated'] += 1
                            results['success_rows'].append(row_num)
                except Exception as e:
                    error_msg = f"Linha {row_num}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg, exc_info=True)
                    # Não propaga o erro, continua com a próxima linha

            except Exception as e:
                error_msg = f"Linha {row_num}: Erro inesperado - {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)

        if results['invalid_rows']:
            report_path = ImportService._generate_error_report(results['invalid_rows'])
            results['error_report_path'] = report_path

        logger.info(f"Importação concluída: {results['created']} criados, {results['updated']} atualizados, {len(results['errors'])} erros")
        
        return results

    @staticmethod
    def _generate_error_report(invalid_rows):
        """
        Gera um relatório .txt com as linhas que não foram importadas
        """
        filename = f"importacao_erros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = f"reports/{filename}"
        
        import os
        os.makedirs('reports', exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RELATÓRIO DE LINHAS NÃO IMPORTADAS\n")
            f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for row in invalid_rows:
                f.write(f"Linha {row['linha']}: {row['motivo']}\n")
                f.write(f"Dados: {row['dados']}\n")
                f.write("-" * 80 + "\n\n")
        
        logger.info(f"Relatório de erros gerado: {filepath}")
        return filepath
    
    @staticmethod
    def _enriquecer_com_cnes(row, cnes_cache):
        """
        Busca dados na tabela CNES e enriquece a linha com os dados encontrados
        """
        cnes_valor = row.get('CNES', '').strip()
        if not cnes_valor:
            return row, False
        
        if cnes_valor in cnes_cache:
            return cnes_cache[cnes_valor]['row'], cnes_cache[cnes_valor]['found']
        
        try:
            cnes_record = Cnes.objects.filter(cnes=cnes_valor).first()
            
            if not cnes_record:
                cnes_sem_zeros = cnes_valor.lstrip('0')
                if cnes_sem_zeros:
                    cnes_record = Cnes.objects.filter(cnes__icontains=cnes_sem_zeros).first()
            
            if cnes_record:
                logger.info(f"CNES {cnes_valor} encontrado! Sobrescrevendo dados...")
                
                if cnes_record.razao_social or cnes_record.fantasia:
                    row['Nome da conta'] = (cnes_record.razao_social or cnes_record.fantasia)[:500]
                
                if cnes_record.cod_nat_jur:
                    row['Código Natureza Jurídica'] = cnes_record.cod_nat_jur[:50]
                
                if cnes_record.natureza_juridica:
                    row['Natureza Jurídica'] = cnes_record.natureza_juridica[:500]
                
                if cnes_record.cpf_cnpj:
                    row['CNPJ'] = cnes_record.cpf_cnpj[:50]
                
                if cnes_record.telefone:
                    row['Conta: Telefone'] = cnes_record.telefone[:100]
                
                if cnes_record.cidade:
                    row['Cidade de correspondência'] = cnes_record.cidade.upper()[:200]
                
                if cnes_record.uf:
                    row['Estado/Província de correspondência'] = cnes_record.uf.upper()
                
                cnes_cache[cnes_valor] = {'row': row, 'found': True}
                return row, True
            else:
                logger.warning(f"CNES {cnes_valor} não encontrado na base")
                cnes_cache[cnes_valor] = {'row': row, 'found': False}
                return row, False
        
        except Exception as e:
            logger.error(f"Erro ao buscar CNES {cnes_valor}: {str(e)}")
            return row, False
    
    @staticmethod
    def _parse_contacts_from_row(row):
        """
        Extrai contatos da linha baseado nas colunas
        """
        contacts = []
        
        # Tenta várias combinações de nomes de colunas
        primeiro_nome = row.get('Primeiro Nome', '') or row.get('Primeiro Nome', '') or ''
        sobrenome = row.get('Sobrenome', '') or row.get('Sobrenome', '') or ''
        cargo = row.get('Cargo', '') or row.get('Cargo', '') or ''
        email = row.get('Email', '') or row.get('Email', '') or ''
        celular = row.get('Celular', '') or row.get('Celular', '') or ''
        telefone_contato = row.get('Telefone', '') or row.get('Telefone', '') or ''
        email_extra = row.get('Email Secundário', '') or row.get('Email Secundário', '') or ''
        
        # Limpa os valores
        primeiro_nome = primeiro_nome.strip() if primeiro_nome else ''
        sobrenome = sobrenome.strip() if sobrenome else ''
        cargo = cargo.strip() if cargo else ''
        email = email.strip() if email else ''
        celular = celular.strip() if celular else ''
        telefone_contato = telefone_contato.strip() if telefone_contato else ''
        email_extra = email_extra.strip() if email_extra else ''
        
        if primeiro_nome or sobrenome or email or celular or telefone_contato:
            nome_completo = ""
            if primeiro_nome and sobrenome:
                nome_completo = f"{primeiro_nome} {sobrenome}".strip()
            elif primeiro_nome:
                nome_completo = primeiro_nome
            elif sobrenome:
                nome_completo = sobrenome

            if not nome_completo and email:
                nome_completo = email.split('@')[0]

            if nome_completo:
                # Limita tamanho dos campos
                contact = {
                    'nome': nome_completo.upper()[:500],
                    'setor': cargo.upper()[:300] if cargo else '',
                    'email': email.lower()[:500] if email else '',
                    'celular': celular[:100] if celular else '',
                    'telefone_contato': telefone_contato[:100] if telefone_contato else '',
                    'email_extra': email_extra.lower()[:500] if email_extra else ''
                }
                contacts.append(contact)

        return contacts

    @staticmethod
    def _process_row(row, results, duplicate, cnes_cache):
        """
        Processa uma linha do CSV/XLSX e cria/atualiza um lead
        Retorna True se criou, False se atualizou
        """
        # Enriquece com dados do CNES
        row_enriquecida, cnes_encontrado = ImportService._enriquecer_com_cnes(row, cnes_cache)
        
        if cnes_encontrado:
            results['cnes_encontrados'] += 1
        elif row.get('CNES'):
            results['cnes_nao_encontrados'] += 1
        
        row = row_enriquecida
        
        # Busca lead existente
        lead = None
        cnpj_raw = row.get('CNPJ', '')
        nome_conta = row.get('Nome da conta', '').upper().strip()
        
        if not duplicate and cnpj_raw:
            cnpj_digits = re.sub(r'\D', '', cnpj_raw)
            if cnpj_digits:
                lead = Lead.objects.filter(
                    Q(cnpj=cnpj_raw) | Q(cnpj=cnpj_digits) | Q(cnpj__icontains=cnpj_digits)
                ).first()
        
        if not lead and nome_conta and not duplicate:
            lead = Lead.objects.filter(empresa__iexact=nome_conta).first()
        
        is_new = False
        if not lead:
            if not nome_conta:
                raise Exception("Nome da conta não informado")
            lead = Lead(empresa=nome_conta)
            is_new = True
        
        if lead.deleted_at:
            lead.deleted_at = None
        
        # Atualiza campos do Lead com limitação de tamanho
        lead.empresa = nome_conta[:500]
        
        if row.get('Apelido'):
            lead.apelido = row['Apelido'].upper().strip()[:500]
        
        if row.get('CNES'):
            lead.cnes = row['CNES'].strip()[:50]
        elif not lead.cnes and cnes_encontrado:
            lead.cnes = row.get('CNES', '').strip()[:50]
        
        if row.get('Conta: Telefone'):
            lead.telefone = row['Conta: Telefone'].strip()[:100]
        
        if cnpj_raw:
            lead.cnpj = cnpj_raw.strip()[:50]
        
        if row.get('Cidade de correspondência'):
            lead.cidade = row['Cidade de correspondência'].upper().strip()[:200]
        
        if row.get('Estado/Província de correspondência'):
            lead.estado = row['Estado/Província de correspondência'].upper().strip()[:2]
        
        if row.get('Código Natureza Jurídica'):
            lead.cod_nat_jur = row['Código Natureza Jurídica'].strip()[:50]
        
        if row.get('Natureza Jurídica'):
            lead.natureza_juridica = row['Natureza Jurídica'].upper().strip()[:500]
        
        if row.get('Segmento'):
            lead.segmento = row['Segmento'].upper().strip()[:200]
        
        # CLASSIFICAÇÃO: True=Cliente, False=Não Cliente
        e_cliente = row.get('É Cliente?', '').strip()
        if e_cliente:
            lead.classificacao = 'Cliente' if e_cliente.upper() == 'TRUE' else 'Não Cliente'
        
        if row.get('Origem'):
            lead.origem = row['Origem'].strip()[:200]
        
        if is_new and not lead.classificacao:
            lead.classificacao = 'Não Cliente'
        
        lead.save()
        
        # Processa Empresas do Grupo
        grupos_str = row.get('Empresas do Grupo', '')
        if grupos_str:
            lead.empresas_grupo.clear()
            for nome in [g.strip().upper() for g in grupos_str.split(',') if g.strip()]:
                if nome:
                    company, _ = Company.objects.get_or_create(nome=nome[:255])
                    lead.empresas_grupo.add(company)
        
        # Processa Produtos
        produtos_str = row.get('Produtos', '')
        if produtos_str:
            lead.produtos_interesse.clear()
            for nome in [p.strip() for p in produtos_str.split(',') if p.strip()]:
                if nome:
                    product, _ = Product.objects.get_or_create(nome=nome[:255])
                    lead.produtos_interesse.add(product)
        
        # Processa Contatos
        contacts = ImportService._parse_contacts_from_row(row)
        
        if contacts:
            for contact_data in contacts:
                ImportService._create_or_update_contact(lead, contact_data)
        
        return is_new
    
    @staticmethod
    def _create_or_update_contact(lead, data):
        """
        Cria ou atualiza um contato baseado no email
        """
        nome = data.get('nome', '').upper().strip()
        if not nome:
            return
        
        email = data.get('email', '').lower().strip()
        email_extra = data.get('email_extra', '').lower().strip()
        celular = data.get('celular', '').strip()
        setor = data.get('setor', '').upper().strip()
        telefone_contato = data.get('telefone_contato', '').strip()
        
        # Busca contato existente pelo email (prioridade)
        contact = None
        if email:
            contact = Contact.objects.filter(lead=lead, email=email).first()
        
        if not contact and nome:
            contact = Contact.objects.filter(lead=lead, nome__iexact=nome).first()
        
        if contact:
            # Atualiza contato existente (apenas se tiver novos dados)
            updated = False
            if nome and contact.nome != nome:
                contact.nome = nome[:500]
                updated = True
            if email and contact.email != email:
                contact.email = email[:500]
                updated = True
            if email_extra and contact.email_extra != email_extra:
                contact.email_extra = email_extra[:500]
                updated = True
            if celular and contact.celular != celular:
                contact.celular = celular[:100]
                updated = True
            if setor and contact.setor != setor:
                contact.setor = setor[:300]
                updated = True
            if telefone_contato and contact.telefone_contato != telefone_contato:
                contact.telefone_contato = telefone_contato[:100]
                updated = True
            
            if updated:
                contact.save()
                logger.info(f"Contato atualizado: {nome} para lead {lead.empresa}")
        else:
            # Cria novo contato
            Contact.objects.create(
                lead=lead,
                nome=nome[:500],
                email=email[:500] if email else '',
                email_extra=email_extra[:500] if email_extra else '',
                celular=celular[:100] if celular else '',
                setor=setor[:300] if setor else '',
                telefone_contato=telefone_contato[:100] if telefone_contato else ''
            )
            logger.info(f"Contato criado: {nome} para lead {lead.empresa}")
