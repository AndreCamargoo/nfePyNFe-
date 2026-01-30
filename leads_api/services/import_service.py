import csv
import json
import io
import re
from leads_api.models import Lead, Company, Product, Contact
from django.db import transaction
from django.db.models import Q


class ImportService:
    @staticmethod
    def process_csv(file, duplicate=True):
        # Tenta decodificar o arquivo (UTF-8 ou Latin-1/ISO-8859-1 comum no Excel BR)
        try:
            decoded_file = file.read().decode('utf-8')
        except UnicodeDecodeError:
            file.seek(0)
            decoded_file = file.read().decode('latin-1')

        io_string = io.StringIO(decoded_file)

        # --- CORREÇÃO DO DELIMITADOR ---
        first_line = io_string.readline()
        # Retorna ao início
        io_string.seek(0) 
        delimiter = ';' if ';' in first_line else ','

        reader = csv.DictReader(io_string, delimiter=delimiter)

        results = {
            "created": 0,
            "updated": 0,
            "errors": []
        }

        field_map = ImportService._get_field_map()

        with transaction.atomic():
            for index, row in enumerate(reader):
                try:
                    clean_row = {}
                    for k, v in row.items():
                        if not k: continue
                        clean_key = k.strip().replace('\ufeff', '')

                        normalized_key = None
                        for map_key, map_list in field_map.items():
                            if any(x.lower() == clean_key.lower() for x in map_list):
                                normalized_key = map_key
                                break

                        if not normalized_key:
                            for map_key, map_list in field_map.items():
                                if any(x.lower() in clean_key.lower() for x in map_list):
                                    normalized_key = map_key
                                    break

                        if normalized_key:
                            clean_row[normalized_key] = v.strip() if v else ""

                    if not clean_row.get('empresa'):
                        continue

                    ImportService._process_row(clean_row, results, duplicate=duplicate)

                except Exception as e:
                    results['errors'].append(f"Linha {index + 2}: {str(e)}")

        return results

    @staticmethod
    def _get_field_map():
        return {
            'empresa': ['Empresa', 'Razão Social', 'Fantasia', 'Nome'],
            'cnpj': ['CNPJ'],
            'cnes': ['CNES', 'CNS'],
            'telefone': ['Telefone', 'Tel', 'Fixo'],
            'cidade': ['Cidade', 'Município'],
            'estado': ['Estado', 'UF'],
            'segmento': ['Segmento', 'Área'],
            'classificacao': ['Classificação', 'Status', 'Situação'],
            'origem': ['Origem', 'Fonte'],
            'empresas_grupo': ['Empresas do Grupo', 'Grupo'],
            'produtos_interesse': ['Produtos', 'Interesse', 'Produtos de Interesse'],
            'contatos_json': ['Contatos (JSON)', 'JSON', 'Contatos'],
            'contato_nome': ['Nome Contato', 'Contato Nome'],
            'contato_email': ['Email Contato', 'Contato Email'],
            'contato_celular': ['Celular', 'Móvel', 'Whatsapp', 'Contato Celular'],
            'contato_setor': ['Cargo', 'Setor', 'Departamento']
        }

    @staticmethod
    def _process_row(row, results, duplicate=False):
        empresa_nome = row['empresa'].upper()
        cnpj_raw = row.get('cnpj', '')

        # --- LÓGICA DE DEDUPLICAÇÃO MELHORADA ---
        lead = None

        # Só busca duplicatas se o parametro duplicate for False (padrão)
        if not duplicate:
            # 1. Tenta buscar por CNPJ (Prioridade Máxima)
            if cnpj_raw:
                # Limpa CNPJ para ter apenas números
                cnpj_digits = re.sub(r'\D', '', cnpj_raw)

                if cnpj_digits:
                    # Busca pelo valor exato ou pelo valor limpo (caso o banco guarde só números)
                    # Adicionamos busca flexível para encontrar "11.111..." ou "11111..."
                    # Tenta achar se estiver contido
                    lead = Lead.objects.filter(Q(cnpj=cnpj_raw) | Q(cnpj=cnpj_digits) | Q(cnpj__icontains=cnpj_digits)).first()

            # 2. Se não achou por CNPJ, tenta buscar pelo NOME exato
            if not lead:
                lead = Lead.objects.filter(empresa__iexact=empresa_nome).first()

        is_new = False
        if not lead:
            lead = Lead(empresa=empresa_nome)
            is_new = True

        # --- REATIVAR LEAD DELETADO (SOFT DELETE) ---
        if lead.deleted_at is not None:
            lead.deleted_at = None

        # --- ATUALIZAÇÃO DE CAMPOS ---
        # Atualiza o nome da empresa se o do arquivo for diferente (Ex: "LUCAS" -> "LUCAS 2")
        if not is_new and empresa_nome != lead.empresa:
            lead.empresa = empresa_nome

        # Prioriza dados do CSV
        if row.get('cnpj'): lead.cnpj = row['cnpj']
        if row.get('cnes'): lead.cnes = row['cnes']
        if row.get('telefone'): lead.telefone = row['telefone']
        if row.get('cidade'): lead.cidade = row['cidade'].upper()
        if row.get('estado'): lead.estado = row['estado'].upper()
        if row.get('segmento'): lead.segmento = row['segmento'].upper()
        if row.get('classificacao'): lead.classificacao = row['classificacao']
        if row.get('origem'): lead.origem = row['origem']

        if is_new and not lead.classificacao:
            lead.classificacao = 'Não Cliente'

        lead.save()

        # Processa ManyToMany: Empresas do Grupo
        if row.get('empresas_grupo'):
            grupos = [g.strip().upper() for g in row['empresas_grupo'].split(',') if g.strip()]
            for g_nome in grupos:
                company, _ = Company.objects.get_or_create(nome=g_nome)
                lead.empresas_grupo.add(company)

        # Processa ManyToMany: Produtos
        if row.get('produtos_interesse'):
            prods = [p.strip() for p in row['produtos_interesse'].split(',') if p.strip()]
            for p_nome in prods:
                product, _ = Product.objects.get_or_create(nome=p_nome)
                lead.produtos_interesse.add(product)

        # Processa Contatos (JSON)
        if row.get('contatos_json'):
            try:
                json_str = row['contatos_json']
                if json_str and json_str != '[]':
                    contacts_data = json.loads(json_str)
                    if isinstance(contacts_data, list):
                        for c_data in contacts_data:
                            ImportService._create_contact_if_not_exists(lead, c_data)
            except json.JSONDecodeError:
                pass

        # Processa Contato Flat
        if row.get('contato_nome'):
            flat_contact = {
                'nome': row['contato_nome'],
                'email': row.get('contato_email', ''),
                'celular': row.get('contato_celular', ''),
                'setor': row.get('contato_setor', '')
            }
            ImportService._create_contact_if_not_exists(lead, flat_contact)

        if is_new:
            results['created'] += 1
        else:
            results['updated'] += 1

    @staticmethod
    def _create_contact_if_not_exists(lead, data):
        nome = data.get('nome', '').upper()
        if not nome:
            return

        # Verifica duplicidade no banco
        if not Contact.objects.filter(lead=lead, nome__iexact=nome).exists():
            Contact.objects.create(
                lead=lead,
                nome=nome,
                email=data.get('email', '').lower(),
                celular=data.get('celular', ''),
                setor=data.get('setor', '').upper()
            )
