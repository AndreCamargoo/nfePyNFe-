import csv
import json
import io
import re
import ast
import logging
from leads_api.models import Lead, Company, Product, Contact
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)


class ImportService:
    @staticmethod
    def process_csv(file, duplicate=True):
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
            "errors": []
        }

        with transaction.atomic():
            for index, row in enumerate(reader, start=2):
                try:
                    # Limpa os cabeçalhos
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
            lambda s: json.loads(re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s.replace("'", '"'))),
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

        # Tenta encontrar padrões de contatos
        # Ex: nome: JOAO, email: joao@teste.com
        contact_patterns = [
            r'nome["\']?\s*:\s*["\']?([^"\'{},]+)["\']?',
            r'email["\']?\s*:\s*["\']?([^"\'{},]+)["\']?',
            r'email_extra["\']?\s*:\s*["\']?([^"\'{},]+)["\']?',
            r'celular["\']?\s*:\s*["\']?([^"\'{},]+)["\']?',
            r'setor["\']?\s*:\s*["\']?([^"\'{},]+)["\']?',
        ]

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

        # Atualiza campos do Lead
        lead.empresa = empresa_nome
        lead.apelido = row.get('Apelido', '').upper() or lead.apelido
        lead.cnes = row.get('CNES', '') or lead.cnes
        lead.telefone = row.get('Telefone', '') or lead.telefone
        lead.cnpj = row.get('CNPJ', '') or lead.cnpj
        lead.cidade = row.get('Cidade', '').upper() or lead.cidade
        lead.estado = row.get('Estado', '').upper() or lead.estado
        lead.segmento = row.get('Segmento', '').upper() or lead.segmento
        lead.classificacao = row.get('Classificação', '') or lead.classificacao
        lead.origem = row.get('Origem', '') or lead.origem
        lead.cod_nat_jur = row.get('Código Natureza Jurídica', '') or lead.cod_nat_jur
        lead.natureza_juridica = row.get('Natureza Jurídica', '').upper() or lead.natureza_juridica

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

        # Processa Contatos (JSON) - AGORA COM PARSING INTELIGENTE
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
        """Cria ou atualiza um contato"""
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
            # Cria novo
            Contact.objects.create(
                lead=lead,
                nome=nome,
                email=email,
                email_extra=email_extra,
                celular=celular,
                setor=setor
            )
            logger.info(f"Contato criado: {nome} para lead {lead.empresa}")
