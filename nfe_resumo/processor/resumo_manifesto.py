import os
from re import sub
from lxml import etree
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime, now
from pynfe.entidades.evento import EventoManifestacaoDest
from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.processamento.serializacao import SerializacaoXML
from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.entidades.fonte_dados import _fonte_dados
from nfe_evento.models import EventoNFe, RetornoEvento
from app.utils.nfe import Nfe


class ManifestoNFeProcessor:
    def __init__(self, empresa, resumo):
        self.resumo = resumo
        self.empresa = empresa
        self.certificado_senha = empresa.senha
        self.uf = empresa.uf.upper()
        self.homologacao = settings.SANDBOX_NFE

        utils_nfe = Nfe(empresa=self.empresa, resumo=self.resumo, homologacao=self.homologacao)
        self.certificado_path = utils_nfe.obter_caminho_certificado()

        # Determinar a UF autorizadora corretamente
        self.uf_autorizadora_nfe = utils_nfe.mapeamento_uf(self.resumo.chave_nfe)

        if self.homologacao:
            self.uf_autorizadora_nfe = "AN"
            print("Homologação ativa - usando Ambiente Nacional (AN)")
        else:
            print(f"Produção - usando UF autorizadora: {self.uf_autorizadora_nfe}")

    def manifestar(self, tipo_manifestacao, justificativa=None):
        if tipo_manifestacao not in [1, 2, 3, 4]:
            raise ValueError("Tipo de manifestação inválido. Use: 1, 2, 3 ou 4")

        if tipo_manifestacao == 4 and not justificativa:
            raise ValueError("Justificativa é obrigatória para operação não realizada")

        evento = EventoManifestacaoDest(
            cnpj=sub(r"\D", "", self.empresa.documento),
            chave=self.resumo.chave_nfe,
            data_emissao=localtime(now()),
            uf=self.uf_autorizadora_nfe,
            operacao=tipo_manifestacao,
            justificativa=justificativa,
        )

        serializador = SerializacaoXML(_fonte_dados, homologacao=self.homologacao)
        xml_evento = serializador.serializar_evento(evento)

        assinatura = AssinaturaA1(self.certificado_path, self.certificado_senha)
        xml_assinado = assinatura.assinar(xml_evento)

        comunicacao = ComunicacaoSefaz(
            self.uf_autorizadora_nfe,
            self.certificado_path,
            self.certificado_senha,
            self.homologacao,
        )

        resposta = comunicacao.evento(modelo="nfe", evento=xml_assinado)

        return self._processar_resposta_sefaz(
            resposta.text, tipo_manifestacao, etree.tostring(xml_assinado, encoding="unicode")
        )

    def _extrair_xml_retorno(self, resposta_xml: str) -> str:
        """
        Extrai apenas o conteúdo do <retEnvEvento> de dentro do SOAP.
        """
        try:
            root = etree.fromstring(resposta_xml.encode("utf-8"))
            ns_soap = {"soap": "http://www.w3.org/2003/05/soap-envelope"}
            # localiza dentro do body o retorno da NFe
            body = root.find(".//soap:Body", namespaces=ns_soap)
            if body is None:
                return resposta_xml

            # busca retEnvEvento
            ret = body.find(".//{http://www.portalfiscal.inf.br/nfe}retEnvEvento")
            if ret is not None:
                return etree.tostring(ret, encoding="unicode")
        except Exception as e:
            print(f"DEBUG - Erro extraindo XML do SOAP: {e}")

        return resposta_xml

    def _processar_resposta_sefaz(self, resposta_xml, tipo_manifestacao, xml_assinado):
        try:
            resposta_limpa = self._extrair_xml_retorno(resposta_xml).strip()
            root = etree.fromstring(resposta_limpa.encode("utf-8"))
            ns = {"ns": "http://www.portalfiscal.inf.br/nfe"}
            cstat_lote = root.findtext(".//ns:cStat", namespaces=ns)
            xmotivo_lote = root.findtext(".//ns:xMotivo", namespaces=ns)

            if cstat_lote != "128":  # 128 = lote processado
                return {
                    "success": False,
                    "erro": f"Lote não processado: {cstat_lote} - {xmotivo_lote}",
                    "status": cstat_lote,
                }

            inf_evento = root.find(".//ns:retEvento/ns:infEvento", ns)

            if inf_evento is None:
                return {
                    "success": False,
                    "erro": "Resposta inválida da Sefaz - infEvento não encontrado",
                }

            cstat = inf_evento.findtext("ns:cStat", namespaces=ns)
            xmotivo = inf_evento.findtext("ns:xMotivo", namespaces=ns)
            nprot = inf_evento.findtext("ns:nProt", namespaces=ns)
            dh_reg_evento = inf_evento.findtext("ns:dhRegEvento", namespaces=ns)
            tp_evento = inf_evento.findtext("ns:tpEvento", namespaces=ns)
            n_seq_evento = inf_evento.findtext("ns:nSeqEvento", namespaces=ns)

            # 135 = sucesso, 573 = duplicidade
            if cstat in ["135", "573"]:

                if cstat == "573" and not nprot:
                    evento_existente = EventoNFe.objects.filter(
                        chave_nfe=self.resumo.chave_nfe,
                        tipo_evento=tipo_manifestacao
                    ).order_by("-id").first()

                    if evento_existente and evento_existente.numero_protocolo:
                        nprot = evento_existente.numero_protocolo
                    else:
                        nprot = f"DUP-{self.resumo.chave_nfe[-8:]}"

                evento = self._salvar_evento_manifestacao(
                    resposta_xml, xml_assinado, tipo_manifestacao,
                    cstat, xmotivo, nprot, dh_reg_evento, tp_evento, n_seq_evento
                )

                return {
                    "success": True,
                    "mensagem": xmotivo,
                    "protocolo": nprot,
                    "evento_id": evento.id if evento else None
                }

            return {
                "success": False,
                "erro": xmotivo or "Erro desconhecido",
                "status": cstat
            }

        except Exception as e:
            return {
                "success": False,
                "erro": f"Erro ao processar resposta: {str(e)}"
            }

    def _salvar_evento_manifestacao(
        self,
        resposta_xml,
        xml_assinado,
        tipo_manifestacao,
        cstat,
        xmotivo,
        nprot,
        dh_reg_evento,
        tp_evento,
        n_seq_evento,
    ):
        manifestacoes = {
            1: "Confirmação da operação",
            2: "Ciência da operação",
            3: "Desconhecimento da operação",
            4: "Operação não realizada",
        }
        descricao_evento = manifestacoes.get(tipo_manifestacao, "Manifestação")

        codigos_uf = {
            "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
            "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
            "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
            "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
        }

        uf_chave = self.resumo.chave_nfe[:2]
        uf_autorizadora = codigos_uf.get(uf_chave, "")

        xml_filename = f"manifesto_{self.resumo.chave_nfe}_{now().strftime('%Y%m%d_%H%M%S')}.xml"
        xml_path = os.path.join("xml", "eventos", xml_filename)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, "xml", "eventos"), exist_ok=True)

        with open(os.path.join(settings.MEDIA_ROOT, xml_path), "w", encoding="utf-8") as f:
            f.write(xml_assinado)

        evento = EventoNFe.objects.create(
            empresa=self.empresa,
            chave_nfe=self.resumo.chave_nfe,
            tipo_evento=tp_evento or "210200",
            sequencia_evento=int(n_seq_evento or 1),
            data_hora_evento=now(),
            data_hora_registro=parse_datetime(dh_reg_evento) if dh_reg_evento else now(),
            descricao_evento=descricao_evento,
            numero_protocolo=nprot,
            status=cstat,
            motivo=xmotivo,
            versao_aplicativo="",
            orgao=uf_autorizadora,
            ambiente=1 if not self.homologacao else 2,
            cnpj_destinatario=sub(r"\D", "", self.empresa.documento),
            file_xml=xml_path,
        )

        self._salvar_retorno_evento(evento, resposta_xml)
        return evento

    def _salvar_retorno_evento(self, evento, resposta_xml):
        try:
            resposta_limpa = self._extrair_xml_retorno(resposta_xml).strip()
            root = etree.fromstring(resposta_limpa.encode("utf-8"))

            ns = {"ns": "http://www.portalfiscal.inf.br/nfe"}
            inf_evento = root.find(".//ns:infEvento", ns)

            if inf_evento is not None:
                RetornoEvento.objects.create(
                    evento=evento,
                    tp_amb=int(inf_evento.findtext("ns:tpAmb", namespaces=ns) or 1),
                    ver_aplic=inf_evento.findtext("ns:verAplic", namespaces=ns) or "",
                    c_orgao=inf_evento.findtext("ns:cOrgao", namespaces=ns) or "",
                    c_stat=inf_evento.findtext("ns:cStat", namespaces=ns) or "",
                    x_motivo=inf_evento.findtext("ns:xMotivo", namespaces=ns) or "",
                    ch_nfe=inf_evento.findtext("ns:chNFe", namespaces=ns) or "",
                    tp_evento=inf_evento.findtext("ns:tpEvento", namespaces=ns) or "",
                    x_evento=inf_evento.findtext("ns:xEvento", namespaces=ns) or "",
                    n_seq_evento=int(inf_evento.findtext("ns:nSeqEvento", namespaces=ns) or 1),
                    cnpj_dest=inf_evento.findtext("ns:CNPJDest", namespaces=ns) or "",
                    dh_reg_evento=parse_datetime(inf_evento.findtext("ns:dhRegEvento", namespaces=ns)) or now(),
                    n_prot=inf_evento.findtext("ns:nProt", namespaces=ns) or "",
                )
        except Exception as e:
            print(f"Erro ao salvar retorno do evento: {str(e)}")

    def _atualizar_resumo_apos_manifestacao(self, tipo_manifestacao, numero_protocolo):
        manifestacoes = {1: "Confirmada", 2: "Ciência", 3: "Desconhecida", 4: "Não realizada"}
        descricao_manifestacao = manifestacoes.get(tipo_manifestacao, "Manifestada")

        self.resumo.descricao_evento = f"Manifestação: {descricao_manifestacao}"
        self.resumo.numero_protocolo = numero_protocolo
        self.resumo.data_recebimento = now()
        self.resumo.save()
