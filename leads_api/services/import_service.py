import csv
import json
import io
import re
import ast
import logging
from leads_api.models import Lead, Company, Product, Contact, Cnes
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)


class ImportService:
    @staticmethod
    def process_csv(file, duplicate=True):
        """
        Processa arquivo CSV de importação de leads
        """
        try:
            decoded_file = file.read().decode('utf-8')
        except UnicodeDecodeError:
            file.seek(0)
            decoded_file = file.read().decode('latin-1')

        io_string = io.StringIO(decoded_file)
        first_line = io_string.readline()
        io_string.seek(0)
        delimiter = ';' if ';' in first_line else ','

        reader = csv.DictReader(io_string, delimiter=delimiter)

        results = {
            "created": 0,
            "updated": 0,
            "errors": [],
            "cnes_encontrados": 0,
            "cnes_nao_encontrados": 0
        }

        with transaction.atomic():
            for index, row in enumerate(reader, start=2):
                try:
                    # Limpa os cabeçalhos (remove BOM e espaços)
                    clean_row = {}
                    for k, v in row.items():
                        if not k:
                            continue
                        clean_key = k.strip().replace('\ufeff', '').strip()
                        clean_row[clean_key] = v.strip() if v else ""

                    if not clean_row.get('Empresa'):
                        continue

                    ImportService._process_row(clean_row, results, duplicate)

                except Exception as e:
                    results['errors'].append(f"Linha {index}: {str(e)}")
                    logger.error(f"Erro na linha {index}: {str(e)}")

        return results

    @staticmethod
    def _enriquecer_com_cnes(row):
        """
        Busca dados na tabela CNES e enriquece a linha com os dados encontrados
        AGORA: Sobrescreve os campos com os dados do CNES (prioridade CNES)
        """
        cnes_valor = row.get('CNES', '').strip()
        if not cnes_valor:
            return row, False

        # Preserva zeros à esquerda - não converter para número
        cnes_limpo = cnes_valor.strip()

        if not cnes_limpo:
            return row, False

        # Busca na tabela CNES
        try:
            # Primeiro tenta busca exata
            cnes_record = Cnes.objects.filter(cnes=cnes_limpo).first()

            # Se não encontrar, tenta buscar ignorando zeros à esquerda
            if not cnes_record:
                cnes_sem_zeros = cnes_limpo.lstrip('0')
                if cnes_sem_zeros:
                    cnes_record = Cnes.objects.filter(cnes__icontains=cnes_sem_zeros).first()

            if cnes_record:
                logger.info(f"CNES {cnes_limpo} encontrado! SOBRESCREVENDO dados do CSV...")

                # SOBRESCREVE todos os campos com os dados do CNES
                # Empresa: usa razão social ou fantasia (SEMPRE sobrescreve)
                if cnes_record.razao_social or cnes_record.fantasia:
                    row['Empresa'] = cnes_record.razao_social or cnes_record.fantasia

                # Apelido: NÃO sobrescreve (conforme sua solicitação anterior)
                # Mantém o apelido do CSV se existir

                # Código Natureza Jurídica (SEMPRE sobrescreve)
                if cnes_record.cod_nat_jur:
                    row['Código Natureza Jurídica'] = cnes_record.cod_nat_jur

                # Natureza Jurídica (SEMPRE sobrescreve)
                if cnes_record.natureza_juridica:
                    row['Natureza Jurídica'] = cnes_record.natureza_juridica

                # CNPJ (SEMPRE sobrescreve)
                if cnes_record.cpf_cnpj:
                    row['CNPJ'] = cnes_record.cpf_cnpj

                # Telefone (SEMPRE sobrescreve)
                if cnes_record.telefone:
                    row['Telefone'] = cnes_record.telefone

                # Cidade (SEMPRE sobrescreve)
                if cnes_record.cidade:
                    row['Cidade'] = cnes_record.cidade.upper()

                # Estado (SEMPRE sobrescreve)
                if cnes_record.uf:
                    row['Estado'] = cnes_record.uf.upper()

                # Os campos abaixo NÃO são sobrescritos pelo CNES:
                # - Segmento (mantém do CSV)
                # - Classificação (mantém do CSV)
                # - Origem (mantém do CSV)
                # - Empresas do Grupo (mantém do CSV)
                # - Produtos (mantém do CSV)
                # - Contatos (mantém do CSV)

                return row, True
            else:
                logger.warning(f"CNES {cnes_limpo} não encontrado na base")
                return row, False

        except Exception as e:
            logger.error(f"Erro ao buscar CNES {cnes_limpo}: {str(e)}")
            return row, False

    @staticmethod
    def _parse_contacts_json(json_str):
        """
        Parseia JSON de contatos de forma inteligente, lidando com vários formatos
        """
        if not json_str or json_str == '[]':
            return []

        # Remove aspas externas se houver
        original = json_str
        if json_str.startswith('"') and json_str.endswith('"'):
            json_str = json_str[1:-1]

        # Corrige escapes comuns
        json_str = json_str.replace('\\"', '"')

        # Tenta diferentes estratégias de parsing
        strategies = [
            # Estratégia 1: JSON normal
            lambda s: json.loads(s),
            
            # Estratégia 2: Python literal (mais flexível)
            lambda s: ast.literal_eval(s),
            
            # Estratégia 3: Corrige chaves sem aspas
            lambda s: json.loads(re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)),
            
            # Estratégia 4: Remove aspas simples e tenta novamente
            lambda s: json.loads(s.replace("'", '"')),
            
            # Estratégia 5: Combina estratégias 3 e 4
            lambda s: json.loads(re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', 
                                         r'\1"\2":', s.replace("'", '"'))),
        ]

        for i, strategy in enumerate(strategies):
            try:
                result = strategy(json_str)
                if isinstance(result, list):
                    logger.info(f"JSON parsed successfully with strategy {i+1}")
                    return result
            except Exception as e:
                logger.debug(f"Strategy {i+1} failed: {str(e)}")
                continue

        # Se todas as estratégias falharem, tenta extrair manualmente
        logger.warning(f"All parsing strategies failed for: {original[:100]}")
        return ImportService._manual_extract_contacts(json_str)

    @staticmethod
    def _manual_extract_contacts(text):
        """
        Extração manual de contatos quando o JSON está muito mal formatado
        """
        contacts = []

        # Divide por chaves de objetos
        objects = re.findall(r'\{([^}]+)\}', text)
        
        for obj in objects:
            contact = {}
            
            # Extrai nome
            nome_match = re.search(r'nome["\']?\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if nome_match:
                contact['nome'] = nome_match.group(1).strip()
            
            # Extrai email
            email_match = re.search(r'email["\']?\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if email_match:
                contact['email'] = email_match.group(1).strip()
            
            # Extrai email_extra
            email_extra_match = re.search(r'email_extra["\']?\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if email_extra_match:
                contact['email_extra'] = email_extra_match.group(1).strip()
            
            # Extrai celular
            celular_match = re.search(r'celular["\']?\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if celular_match:
                contact['celular'] = celular_match.group(1).strip()
            
            # Extrai setor
            setor_match = re.search(r'setor["\']?\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if setor_match:
                contact['setor'] = setor_match.group(1).strip()

            if contact.get('nome'):
                contacts.append(contact)

        return contacts

    @staticmethod
    def _process_row(row, results, duplicate=False):
        """
        Processa uma linha do CSV e cria/atualiza um lead
        """
        # PRIMEIRO: Enriquece com dados do CNES se houver
        row_enriquecida, cnes_encontrado = ImportService._enriquecer_com_cnes(row)
        
        if cnes_encontrado:
            results['cnes_encontrados'] += 1
        elif row.get('CNES'):
            results['cnes_nao_encontrados'] += 1
        
        # Usa a linha enriquecida para o resto do processamento
        row = row_enriquecida
        
        empresa_nome = row.get('Empresa', '').upper()
        if not empresa_nome:
            return

        # Busca lead existente
        lead = None
        cnpj_raw = row.get('CNPJ', '')

        if not duplicate and cnpj_raw:
            cnpj_digits = re.sub(r'\D', '', cnpj_raw)
            if cnpj_digits:
                lead = Lead.objects.filter(
                    Q(cnpj=cnpj_raw) | Q(cnpj=cnpj_digits) | Q(cnpj__icontains=cnpj_digits)
                ).first()

        if not lead and not duplicate:
            lead = Lead.objects.filter(empresa__iexact=empresa_nome).first()

        is_new = False
        if not lead:
            lead = Lead(empresa=empresa_nome)
            is_new = True

        # Se estava deletado, reativa
        if lead.deleted_at:
            lead.deleted_at = None

        # Atualiza campos do Lead (prioriza dados do CSV, depois CNES)
        lead.empresa = empresa_nome
        
        # Apelido - NÃO vem do CNES, só do CSV
        if row.get('Apelido'):
            lead.apelido = row['Apelido'].upper()
        
        # CNES - PRESERVAR ZEROS À ESQUERDA (é string)
        if row.get('CNES'):
            lead.cnes = row['CNES'].strip()  # Não converte para número, mantém como string
        elif not lead.cnes and cnes_encontrado:
            # Se não tinha CNES e encontramos via enriquecimento
            lead.cnes = row.get('CNES', '').strip()
        
        # Telefone
        if row.get('Telefone'):
            lead.telefone = row['Telefone'].strip()
        
        # CNPJ
        if row.get('CNPJ'):
            lead.cnpj = row['CNPJ'].strip()
        
        # Cidade
        if row.get('Cidade'):
            lead.cidade = row['Cidade'].upper()
        
        # Estado
        if row.get('Estado'):
            lead.estado = row['Estado'].upper()
        
        # Código Natureza Jurídica
        if row.get('Código Natureza Jurídica'):
            lead.cod_nat_jur = row['Código Natureza Jurídica'].strip()
        
        # Natureza Jurídica
        if row.get('Natureza Jurídica'):
            lead.natureza_juridica = row['Natureza Jurídica'].upper()
        
        # Campos que só vêm do CSV
        if row.get('Segmento'):
            lead.segmento = row['Segmento'].upper()
        if row.get('Classificação'):
            lead.classificacao = row['Classificação']
        if row.get('Origem'):
            lead.origem = row['Origem']

        if is_new and not lead.classificacao:
            lead.classificacao = 'Não Cliente'

        lead.save()

        # Processa Empresas do Grupo
        grupos_str = row.get('Empresas do Grupo', '')
        if grupos_str:
            for nome in [g.strip().upper() for g in grupos_str.split(',') if g.strip()]:
                company, _ = Company.objects.get_or_create(nome=nome)
                lead.empresas_grupo.add(company)

        # Processa Produtos
        produtos_str = row.get('Produtos', '')
        if produtos_str:
            for nome in [p.strip() for p in produtos_str.split(',') if p.strip()]:
                product, _ = Product.objects.get_or_create(nome=nome)
                lead.produtos_interesse.add(product)

        # Processa Contatos (JSON)
        contatos_json = row.get('Contatos (JSON)', '')
        if contatos_json and contatos_json != '[]':
            contacts_data = ImportService._parse_contacts_json(contatos_json)
            
            if contacts_data:
                for c_data in contacts_data:
                    # Garante que todos os campos existam
                    contact_data = {
                        'nome': c_data.get('nome', '').upper().strip(),
                        'setor': c_data.get('setor', '').upper().strip(),
                        'email': c_data.get('email', '').lower().strip(),
                        'email_extra': c_data.get('email_extra', '').lower().strip(),
                        'celular': c_data.get('celular', '').strip()
                    }
                    
                    if contact_data['nome']:  # Só cria se tiver nome
                        ImportService._create_or_update_contact(lead, contact_data)
            else:
                results['errors'].append(f"Não foi possível parsear contatos para {empresa_nome}: {contatos_json[:100]}")

        if is_new:
            results['created'] += 1
        else:
            results['updated'] += 1

    @staticmethod
    def _create_or_update_contact(lead, data):
        """
        Cria ou atualiza um contato
        """
        nome = data.get('nome', '').upper().strip()
        if not nome:
            return

        email = data.get('email', '').lower().strip()
        email_extra = data.get('email_extra', '').lower().strip()
        celular = data.get('celular', '').strip()
        setor = data.get('setor', '').upper().strip()

        # Busca contato existente
        contact = Contact.objects.filter(lead=lead, nome__iexact=nome).first()

        if contact:
            # Atualiza apenas se os novos valores não estiverem vazios
            if email:
                contact.email = email
            if email_extra:
                contact.email_extra = email_extra
            if celular:
                contact.celular = celular
            if setor:
                contact.setor = setor
            contact.save()
            logger.info(f"Contato atualizado: {nome} para lead {lead.empresa}")
        else:
            # Cria novo contato
            Contact.objects.create(
                lead=lead,
                nome=nome,
                email=email,
                email_extra=email_extra,
                celular=celular,
                setor=setor
            )
            logger.info(f"Contato criado: {nome} para lead {lead.empresa}")
