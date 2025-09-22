import os
import logging
import xml.etree.ElementTree as ET
from pynfe.processamento.comunicacao import ComunicacaoSefaz

from empresa.models import Empresa
from nfe_resumo.models import ResumoNFe

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Nfe:
    def __init__(self, empresa: Empresa, resumo: ResumoNFe, homologacao: bool = False):
        self.resumo = resumo
        self.empresa = empresa
        self.certificado_path = self.obter_caminho_certificado()
        self.certificado_senha = empresa.senha
        self.uf = empresa.uf.upper()
        self.homologacao = homologacao

    def obter_caminho_certificado(self):
        if self.empresa.file and hasattr(self.empresa.file, 'path'):
            return self.empresa.file.path
        raise ValueError('Certificado não encontrado para a empresa')

    def mapeamento_uf(self, chave_nfe):
        """
        Mapeia o código UF da chave NFe para sigla e determina o órgão autorizador
        """
        codigos_uf = {
            '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA',
            '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE',
            '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE',
            '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
            '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT',
            '52': 'GO', '53': 'DF'
        }

        # Pega os 2 primeiros dígitos da chave (cUF)
        uf_chave = chave_nfe[:2]

        # Verifica se é uma chave válida
        if not uf_chave.isdigit() or uf_chave not in codigos_uf:
            raise ValueError(f'UF da chave NFe inválida: {uf_chave}')

        uf_autorizadora = codigos_uf[uf_chave]

        # Para SVRS (alguns estados usam SVRS mesmo sendo de outra UF)
        # Estados que usam SVRS: AC, AL, AP, DF, ES, MG, PA, PB, RJ, RN, RO, RR, RS, SC, SE, SP, TO
        estados_svrs = ['AC', 'AL', 'AP', 'DF', 'ES', 'MG', 'PA', 'PB', 'RJ',
                        'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO']

        if uf_autorizadora in estados_svrs:
            print(f"Estado {uf_autorizadora} utiliza SVRS - enviando para AN")
            return 'AN'  # Ambiente Nacional para SVRS

        return uf_autorizadora

    def testar_conexao_sefaz(self):
        """Testa se a comunicação com a SEFAZ está funcionando"""
        try:
            ComunicacaoSefaz(
                self.uf,
                self.certificado_path,
                self.certificado_senha,
                self.homologacao
            )
            logging.info("Comunicação com a SEFAZ inicializada com sucesso")
            return True
        except Exception as e:
            logging.error(f"Erro na comunicação com SEFAZ: {str(e)}")
            return False

    def verificar_certificado(self):
        """Verificação básica do certificado"""
        try:
            if not os.path.exists(self.certificado_path):
                logging.error(f"Arquivo de certificado não encontrado: {self.certificado_path}")
                return False

            file_size = os.path.getsize(self.certificado_path)
            if file_size == 0:
                logging.error(f"Arquivo de certificado está vazio: {self.certificado_path}")
                return False

            logging.info(f"Certificado encontrado: {self.certificado_path} ({file_size} bytes)")
            return self.certificado_path
        except Exception as e:
            logging.error(f"Problema com certificado: {str(e)}")
            return False

    def baixar_xml_completo(self):
        """
        Tenta baixar o XML completo da NF-e usando o webservice de download
        """
        try:
            comunicacao = ComunicacaoSefaz(
                self.uf,
                self.certificado_path,
                self.certificado_senha,
                self.homologacao
            )

            # Método para download de NFe (depende da biblioteca)
            resposta = comunicacao.consulta_nota(
                modelo='nfe',
                chave=self.resumo.chave_nfe
            )

            # Verifica se a resposta contém o XML completo
            if resposta.text and 'nfeProc' in resposta.text:
                return resposta.text
            else:
                logging.warning("XML completo não disponível via download")
                return None

        except Exception as e:
            logging.error(f"Erro ao baixar XML completo: {str(e)}")
            return None

    def obter_natureza_operacao(self, xml_content=None):
        """
        Obtém a natureza da operação (natOp) do XML da NF-e.
        Retorna a string da natureza da operação ou None se não encontrar.
        """
        try:
            if xml_content is None:
                # Tenta ler do arquivo XML do resumo
                if not self.resumo.file_xml:
                    logging.warning("Arquivo XML não encontrado no resumo")
                    return None

                try:
                    with open(self.resumo.file_xml.path, 'rb') as f:  # Abrir em modo binário
                        xml_content = f.read().decode('utf-8')  # Decodificar para string
                except Exception as e:
                    logging.error(f"Erro ao ler arquivo XML: {str(e)}")
                    return None

            # Remove namespaces para facilitar a parsing
            xml_content_sem_ns = xml_content.replace('ns2:', '').replace('ns3:', '').replace('ns4:', '').replace('nfe:', '')

            # Usar etree.fromstring com bytes para evitar problema de encoding
            try:
                root = ET.fromstring(xml_content_sem_ns.encode('utf-8'))
            except ET.ParseError:
                # Se falhar, tentar sem a declaração XML
                lines = xml_content_sem_ns.split('\n')
                xml_sem_declaracao = '\n'.join([line for line in lines if not line.strip().startswith('<?xml')])
                root = ET.fromstring(xml_sem_declaracao.encode('utf-8'))

            # Procura pela tag natOp (Natureza da Operação)
            nat_op = root.find('.//natOp')

            if nat_op is not None and nat_op.text:
                logging.info(f"Natureza da operação encontrada: {nat_op.text}")
                return nat_op.text.strip().upper()
            else:
                logging.warning("Natureza da operação não encontrada no XML")
                return None

        except Exception as e:
            logging.error(f"Erro ao obter natureza da operação: {str(e)}")
            return None

    def consultar_nfe(self):
        """Consulta a NFe antes de manifestar"""
        try:
            comunicacao = ComunicacaoSefaz(
                self.uf,
                self.certificado_path,
                self.certificado_senha,
                self.homologacao
            )

            if hasattr(comunicacao, 'consulta_nota'):
                resposta = comunicacao.consulta_nota(
                    modelo='nfe',
                    chave=self.resumo.chave_nfe
                )

                # Verifica se a resposta tem algum conteúdo útil
                if resposta.text:
                    logging.info(f"Resposta consulta NFe: {resposta.text}")
                    # Agora formatamos a resposta para um dicionário legível
                    return self._formatar_resposta(resposta.text)
                else:
                    logging.warning("Resposta da consulta NFe não contém dados")
                    return None
            else:
                logging.error("Método consulta_nota não disponível nesta versão do pynfe")
                return None
        except Exception as e:
            logging.error(f"Erro ao consultar NFe: {str(e)}")
            return None

    def _formatar_resposta(self, resposta_xml):
        """Formatar a resposta da consulta NFe removendo namespaces"""
        try:
            if not resposta_xml:
                return {'error': 'Resposta XML está vazia'}

            # Debug: Ver o conteúdo da resposta
            print(f"DEBUG - Resposta XML completa: {resposta_xml[:500]}...")

            # Remover declaração XML se existir
            resposta_limpa = resposta_xml
            if resposta_limpa.startswith('<?xml'):
                lines = resposta_limpa.split('\n')
                resposta_limpa = '\n'.join([line for line in lines if not line.strip().startswith('<?xml')])

            # Remover namespaces SOAP
            resposta_limpa = resposta_limpa.replace('soap:', '').replace('ns2:', '').replace('ns3:', '').replace('ns4:', '')

            # Tentar encontrar o retConsSitNFe que contém os dados
            if '<retConsSitNFe' in resposta_limpa:
                # Extrair apenas o conteúdo do retConsSitNFe
                start = resposta_limpa.find('<retConsSitNFe')
                end = resposta_limpa.find('</retConsSitNFe>') + len('</retConsSitNFe>')
                if start != -1 and end != -1:
                    ret_cons_sit = resposta_limpa[start:end]
                    root = ET.fromstring(ret_cons_sit.encode('utf-8'))
                else:
                    root = ET.fromstring(resposta_limpa.encode('utf-8'))
            else:
                root = ET.fromstring(resposta_limpa.encode('utf-8'))

            # Buscar elementos diretamente (sem namespaces)
            cStat = root.find('.//cStat')
            xMotivo = root.find('.//xMotivo')
            nProt = root.find('.//nProt')
            dhRecbto = root.find('.//dhRecbto')
            chNFe = root.find('.//chNFe')

            # Se não encontrou no nível principal, procurar dentro de infProt
            if cStat is None:
                infProt = root.find('.//infProt')
                if infProt is not None:
                    cStat = infProt.find('cStat')
                    xMotivo = infProt.find('xMotivo')
                    nProt = infProt.find('nProt')
                    dhRecbto = infProt.find('dhRecbto')
                    # A chave NFe pode estar tanto no nível principal quanto no infProt
                    if chNFe is None:
                        chNFe = infProt.find('chNFe')

            resposta_dict = {
                'status': cStat.text if cStat is not None else 'Desconhecido',
                'motivo': xMotivo.text if xMotivo is not None else 'Sem motivo',
                'protocolo': nProt.text if nProt is not None else None,
                'data_recebimento': dhRecbto.text if dhRecbto is not None else None,
                'chave_nfe': chNFe.text if chNFe is not None else None
            }

            print(f"DEBUG - Dados extraídos: {resposta_dict}")

            return resposta_dict

        except Exception as e:
            logging.error(f"Erro ao processar resposta: {str(e)}")
            # Tentar uma abordagem mais simples - busca por texto com regex melhorado
            try:
                # Buscar padrões simples no XML - regex melhorado
                import re

                # Padrões mais robustos para capturar os dados
                cStat_match = re.search(r'<cStat>(\d+)</cStat>', resposta_xml)
                xMotivo_match = re.search(r'<xMotivo>([^<]+)</xMotivo>', resposta_xml)
                nProt_match = re.search(r'<nProt>([^<]+)</nProt>', resposta_xml)
                chNFe_match = re.search(r'<chNFe>([^<]+)</chNFe>', resposta_xml)
                dhRecbto_match = re.search(r'<dhRecbto>([^<]+)</dhRecbto>', resposta_xml)

                # Se não encontrou chNFe no padrão normal, tentar outros padrões
                if not chNFe_match:
                    # Tentar encontrar a chave em outros lugares
                    chNFe_match = re.search(r'<chNFe[^>]*>([^<]+)</chNFe>', resposta_xml)

                resposta_dict = {
                    'status': cStat_match.group(1) if cStat_match else 'Desconhecido',
                    'motivo': xMotivo_match.group(1) if xMotivo_match else 'Sem motivo',
                    'protocolo': nProt_match.group(1) if nProt_match else None,
                    'data_recebimento': dhRecbto_match.group(1) if dhRecbto_match else None,
                    'chave_nfe': chNFe_match.group(1) if chNFe_match else None
                }

                print(f"DEBUG - Dados via regex: {resposta_dict}")
                return resposta_dict

            except Exception as e2:
                logging.error(f"Erro também no fallback regex: {str(e2)}")
                return {
                    'error': f'Erro no parsing: {str(e)}',
                    'resposta_bruta': resposta_xml[:1000] + '...' if len(resposta_xml) > 1000 else resposta_xml
                }
