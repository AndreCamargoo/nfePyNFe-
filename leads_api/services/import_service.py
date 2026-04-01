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

        # Remove BOM se existir
        if decoded_file.startswith('\ufeff'):
            decoded_file = decoded_file[1:]

        # Remove também o ï»¿ que pode aparecer
        if decoded_file.startswith('ï»¿'):
            decoded_file = decoded_file[3:]

        io_string = io.StringIO(decoded_file)
        first_line = io_string.readline()
        io_string.seek(0)

        # Detecta delimitador
        delimiter = ';' if ';' in first_line else ','

        # Lê o CSV
        reader = csv.DictReader(io_string, delimiter=delimiter)

        # Verifica se os cabeçalhos foram lidos corretamente
        if not reader.fieldnames:
            raise Exception("Arquivo CSV vazio ou formato inválido")

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
                    # Cria um novo dicionário com chaves limpas
                    clean_row = {}
                    for old_key, value in row.items():
                        if not old_key:
                            continue
                        # Limpa a chave (remove BOM, espaços, e caracteres estranhos)
                        clean_key = old_key.strip().replace('\ufeff', '').replace('ï»¿', '').strip()
                        # Limpa o valor
                        clean_value = value.strip() if value else ""
                        clean_row[clean_key] = clean_value

                    # Pula linhas de comentário (começam com #)
                    if clean_row.get('Empresa', '').startswith('#'):
                        continue

                    if not clean_row.get('Empresa'):
                        results['errors'].append(f"Linha {index}: Empresa não informada")
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
        Sobrescreve os campos com os dados do CNES (prioridade CNES)
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
                logger.info(f"CNES {cnes_limpo} encontrado! Sobrescrevendo dados do CSV...")

                # Sobrescreve todos os campos com os dados do CNES
                if cnes_record.razao_social or cnes_record.fantasia:
                    row['Empresa'] = cnes_record.razao_social or cnes_record.fantasia

                # Apelido NÃO é sobrescrito (mantém do CSV)

                if cnes_record.cod_nat_jur:
                    row['Código Natureza Jurídica'] = cnes_record.cod_nat_jur

                if cnes_record.natureza_juridica:
                    row['Natureza Jurídica'] = cnes_record.natureza_juridica

                if cnes_record.cpf_cnpj:
                    row['CNPJ'] = cnes_record.cpf_cnpj

                if cnes_record.telefone:
                    row['Telefone'] = cnes_record.telefone

                if cnes_record.cidade:
                    row['Cidade'] = cnes_record.cidade.upper()

                if cnes_record.uf:
                    row['Estado'] = cnes_record.uf.upper()

                return row, True
            else:
                logger.warning(f"CNES {cnes_limpo} não encontrado na base")
                return row, False

        except Exception as e:
            logger.error(f"Erro ao buscar CNES {cnes_limpo}: {str(e)}")
            return row, False

    @staticmethod
    def _parse_friendly_contacts(contact_str):
        """
        Parseia formato amigável de contatos:
        - Contatos separados por " || " (pipe duplo)
        - Campos separados por " | " (pipe)
        - Formato: campo: valor

        Exemplos:
        "nome: JOAO SILVA | setor: COMERCIAL | email: joao@teste.com | celular: 11999999999"
        "nome: JOAO | email: joao@teste.com || nome: MARIA | email: maria@teste.com"
        """
        if not contact_str or contact_str.strip() == '':
            return []

        contacts = []

        # Remove aspas externas que podem vir do CSV
        contact_str = contact_str.strip()
        if contact_str.startswith('"') and contact_str.endswith('"'):
            contact_str = contact_str[1:-1]

        # PASSO 1: Separa múltiplos contatos por "||"
        contact_items = re.split(r'\|\|', contact_str)

        for item in contact_items:
            item = item.strip()
            if not item:
                continue

            contact = {}

            # PASSO 2: Separa os campos por "|"
            fields = re.split(r'\|', item)

            for field in fields:
                field = field.strip()
                if ':' not in field:
                    continue

                # Divide campo e valor (apenas no primeiro :)
                key, value = field.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                if not value:
                    continue

                # Mapeia para os campos do contato
                if key in ['nome', 'name', 'nome_completo', 'nome_contato']:
                    contact['nome'] = value.upper()
                elif key in ['setor', 'cargo', 'department', 'departamento', 'area']:
                    contact['setor'] = value.upper()
                elif key in ['email', 'e-mail', 'mail', 'email_principal']:
                    contact['email'] = value.lower()
                elif key in ['email_extra', 'email2', 'email_secundario', 'email_alternativo', 'email_sec']:
                    contact['email_extra'] = value.lower()
                elif key in ['celular', 'telefone', 'phone', 'whatsapp', 'tel', 'contato', 'cel']:
                    # Limpa telefone (remove tudo que não é número)
                    contact['celular'] = re.sub(r'\D', '', value)

            # Só adiciona se tiver pelo menos nome
            if contact.get('nome'):
                contacts.append(contact)
            elif contact.get('email'):
                # Se não tem nome mas tem email, cria nome a partir do email
                contact['nome'] = contact['email'].split('@')[0].upper()
                contacts.append(contact)

        return contacts

    @staticmethod
    def _parse_contacts_json(json_str):
        """
        Parseia contatos aceitando múltiplos formatos:
        1. Formato amigável: "nome: JOAO | email: joao@teste.com || nome: MARIA"
        2. JSON padrão: [{"nome":"JOAO"}]
        3. JSON com escape: "[{\"nome\":\"JOAO\"}]"
        4. CSV com aspas duplicadas: "[{""nome"":""JOAO""}]"
        """
        if not json_str or json_str == '[]':
            return []

        original = json_str

        # TENTATIVA 1: Formato amigável (com : e | ou ||)
        if ':' in json_str and ('|' in json_str or '||' in json_str):
            logger.info("Detected friendly format with colons and pipes")
            contacts = ImportService._parse_friendly_contacts(json_str)
            if contacts:
                logger.info(f"Parsed {len(contacts)} contacts using friendly format")
                return contacts

        # TENTATIVA 2: Formato amigável com apenas um contato
        if ':' in json_str and any(key in json_str.lower() for key in ['nome:', 'email:', 'setor:', 'celular:']):
            logger.info("Detected single contact friendly format")
            contacts = ImportService._parse_friendly_contacts(json_str)
            if contacts:
                return contacts

        # Remove aspas externas se houver
        if json_str.startswith('"') and json_str.endswith('"'):
            json_str = json_str[1:-1]

        # Limpa aspas duplicadas malformadas
        json_str = json_str.replace('""', '"')
        json_str = json_str.replace('\\"', '"')

        # TENTATIVA 3: JSON normal
        strategies = [
            lambda s: json.loads(s),
            lambda s: ast.literal_eval(s),
            lambda s: json.loads(re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)),
            lambda s: json.loads(s.replace("'", '"')),
            lambda s: json.loads(re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s.replace("'", '"'))),
        ]

        for i, strategy in enumerate(strategies):
            try:
                result = strategy(json_str)
                if isinstance(result, list):
                    logger.info(f"JSON parsed successfully with strategy {i+1}")
                    return result
                elif isinstance(result, dict):
                    return [result]
            except Exception as e:
                logger.debug(f"Strategy {i+1} failed: {str(e)}")
                continue

        # TENTATIVA 4: Extração manual (fallback)
        logger.warning(f"All parsing strategies failed for: {original[:100]}")
        return ImportService._manual_extract_contacts(json_str)

    @staticmethod
    def _manual_extract_contacts(text):
        """
        Extração manual de contatos quando o JSON está muito mal formatado
        """
        contacts = []

        # Remove aspas duplicadas primeiro
        text = text.replace('""', '"')

        # Encontra padrões de objetos entre chaves
        objects = re.findall(r'\{([^}]+)\}', text)

        for obj in objects:
            contact = {}

            # Extrai nome
            nome_match = re.search(r'n["\']*\s*:\s*["\']+([^"\'{},]+)["\']+', obj, re.IGNORECASE)
            if nome_match:
                contact['nome'] = nome_match.group(1).strip()
            else:
                nome_match = re.search(r'n["\']*\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
                if nome_match:
                    contact['nome'] = nome_match.group(1).strip()

            # Extrai email
            email_match = re.search(r'email["\']*\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if email_match:
                contact['email'] = email_match.group(1).strip()

            # Extrai email_extra
            email_extra_match = re.search(r'email_extra["\']*\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if email_extra_match:
                contact['email_extra'] = email_extra_match.group(1).strip()

            # Extrai celular
            celular_match = re.search(r'celular["\']*\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
            if celular_match:
                contact['celular'] = celular_match.group(1).strip()

            # Extrai setor
            setor_match = re.search(r'setor["\']*\s*:\s*["\']?([^"\'{},]+)["\']?', obj, re.IGNORECASE)
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
        # Enriquece com dados do CNES se houver
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

        # Atualiza campos do Lead
        lead.empresa = empresa_nome

        if row.get('Apelido'):
            lead.apelido = row['Apelido'].upper()

        if row.get('CNES'):
            lead.cnes = row['CNES'].strip()
        elif not lead.cnes and cnes_encontrado:
            lead.cnes = row.get('CNES', '').strip()

        if row.get('Telefone'):
            lead.telefone = row['Telefone'].strip()

        if row.get('CNPJ'):
            lead.cnpj = row['CNPJ'].strip()

        if row.get('Cidade'):
            lead.cidade = row['Cidade'].upper()

        if row.get('Estado'):
            lead.estado = row['Estado'].upper()

        if row.get('Código Natureza Jurídica'):
            lead.cod_nat_jur = row['Código Natureza Jurídica'].strip()

        if row.get('Natureza Jurídica'):
            lead.natureza_juridica = row['Natureza Jurídica'].upper()

        if row.get('Observações'):
            lead.observacoes = row['Observações'].strip()

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

        # Processa Contatos - Suporta tanto "Contatos" quanto "Contatos (JSON)"
        contatos_json = row.get('Contatos', '') or row.get('Contatos (JSON)', '')

        if contatos_json and contatos_json != '[]':
            contacts_data = ImportService._parse_contacts_json(contatos_json)

            if contacts_data:
                for c_data in contacts_data:
                    contact_data = {
                        'nome': c_data.get('nome', '').upper().strip(),
                        'setor': c_data.get('setor', '').upper().strip(),
                        'email': c_data.get('email', '').lower().strip(),
                        'email_extra': c_data.get('email_extra', '').lower().strip(),
                        'celular': c_data.get('celular', '').strip()
                    }

                    if contact_data['nome']:
                        ImportService._create_or_update_contact(lead, contact_data)
            else:
                results['errors'].append(f"Linha {empresa_nome}: Não foi possível parsear contatos: {contatos_json[:100]}")

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
            Contact.objects.create(
                lead=lead,
                nome=nome,
                email=email,
                email_extra=email_extra,
                celular=celular,
                setor=setor
            )
            logger.info(f"Contato criado: {nome} para lead {lead.empresa}")