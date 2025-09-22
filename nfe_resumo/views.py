from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from app.permissions import GlobalDefaultPermission

from empresa.models import Empresa
from nfe_resumo.models import ResumoNFe

from nfe_resumo.processor.resumo_processor import ResumoNFeProcessor
from nfe_resumo.processor.resumo_manifesto import ManifestoNFeProcessor
from nfe_resumo.serializers import ResumoNFeSerializer

from app.utils.nfe import Nfe


class ResumoNFeProcessAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)
    serializer_class = ResumoNFeSerializer

    def get_queryset(self):
        return ResumoNFe.objects.filter(empresa__usuario=self.request.user, deleted_at__isnull=True).order_by('-data_emissao')

    def post(self, request, *args, **kwargs):
        try:
            empresa_id = request.data.get('empresa_id')
            nsu = request.data.get('nsu')
            file_xml = request.data.get('fileXml')
            tipo = request.data.get('tipo')

            if not all([empresa_id, nsu, file_xml, tipo]):
                return Response({'error': 'Todos os campos são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

            if tipo != 'resumo_nsu':
                return Response({'error': 'Tipo de documento não suportado'}, status=status.HTTP_400_BAD_REQUEST)

            empresa = Empresa.objects.get(pk=empresa_id)
            processor = ResumoNFeProcessor(empresa, nsu, file_xml)
            resumo = processor.processar()

            serializer = self.get_serializer(resumo)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Empresa.DoesNotExist:
            return Response({'error': 'Empresa não encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResumoNFeRetriveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = ResumoNFeSerializer

    def get_queryset(self):
        return ResumoNFe.objects.filter(empresa__usuario=self.request.user, deleted_at__isnull=True)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResumoNFeManifestacaoAPIView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, GlobalDefaultPermission)

    def post(self, request, *args, **kwargs):
        try:
            # Pegar o ID da URL (kwargs) em vez do body (request.data)
            resumo_id = kwargs.get('pk')
            if not resumo_id:
                return Response({'error': 'ID do resumo não encontrado na URL'}, status=400)

            empresa_id = request.data.get('empresa_id')
            tipo_manifestacao = request.data.get('tipo_manifestacao')
            justificativa = request.data.get('justificativa', None)

            if not all([empresa_id, tipo_manifestacao]):
                return Response({'error': 'empresa_id e tipo_manifestacao são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

            empresa = Empresa.objects.get(pk=empresa_id)
            resumo = ResumoNFe.objects.get(pk=resumo_id, empresa=empresa)

            utils_nfe = Nfe(empresa=empresa, resumo=resumo, homologacao=False)

            # 1. VERIFICAR TIPO DA NOTA ANTES DE MANIFESTAR
            natureza_operacao = utils_nfe.obter_natureza_operacao()

            if natureza_operacao:
                # Aqui você pode tomar decisões baseadas no tipo de operação
                print(f"Natureza da operação: {natureza_operacao}")

                # Se for devolução, pode aplicar regras específicas
                if 'DEVOLUCAO' in natureza_operacao:
                    print("Nota identificada como DEVOLUÇÃO - Aplicando regras específicas")
                    # Aqui você pode adicionar lógica adicional para devoluções
                elif 'COMPRA' in natureza_operacao:
                    print("Nota identificada como COMPRA - Processamento normal")
                # Adicione outros casos conforme necessário

            # 2. CONSULTAR STATUS NA SEFAZ
            consulta_resposta = utils_nfe.consultar_nfe()
            print(f"Resposta da consulta :::: {consulta_resposta}")

            if not consulta_resposta:
                return Response({'error': 'NFe não encontrada ou erro na consulta'}, status=status.HTTP_400_BAD_REQUEST)

            # CORREÇÃO: Verificar se a consulta foi bem-sucedida de forma mais robusta
            status_consulta = consulta_resposta.get('status')
            motivo_consulta = consulta_resposta.get('motivo', '')

            # Se houve erro no parsing, mas temos dados úteis
            if 'error' in consulta_resposta:
                print(f"⚠️ Aviso no parsing: {consulta_resposta.get('error')}")
                # Tentar inferir o status da resposta bruta
                if 'cStat>100</cStat>' in consulta_resposta.get('resposta_bruta', ''):
                    print("✅ Nota autorizada (detectado via análise textual)")
                    status_consulta = '100'
                    motivo_consulta = 'Autorizado o uso da NF-e'
                else:
                    return Response({
                        'error': f'Erro na consulta: {consulta_resposta.get("error")}',
                        'detalhes': 'Não foi possível determinar o status da nota'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 3. VERIFICAR SE A NOTA ESTÁ AUTORIZADA
            if status_consulta != '100':
                return Response({
                    'error': f'Nota não está autorizada. Status: {status_consulta} - {motivo_consulta}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 4. PROCESSAR MANIFESTO (remover a pausa de debug)
            processor = ManifestoNFeProcessor(empresa, resumo)
            resultado = processor.manifestar(int(tipo_manifestacao), justificativa) or {}

            if resultado['success']:
                return Response({
                    'success': True,
                    'message': resultado['mensagem'],
                    'protocolo': resultado['protocolo'],
                    'evento_id': resultado.get('evento_id'),
                    'natureza_operacao': natureza_operacao
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': resultado['erro'],
                    'natureza_operacao': natureza_operacao
                }, status=status.HTTP_400_BAD_REQUEST)

        except Empresa.DoesNotExist:
            return Response({'error': 'Empresa não encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except ResumoNFe.DoesNotExist:
            return Response({'error': 'Resumo não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Erro interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
