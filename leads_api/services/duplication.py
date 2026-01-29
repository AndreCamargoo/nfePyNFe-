from django.db.models import Q
from ..models import Lead


class DuplicationService:
    @staticmethod
    def analyze(data):
        """
        Analisa se o lead (data) já existe no banco.
        Retorna um dict com status e metadados.
        """
        empresa_nome = data.get('empresa', '').strip()
        cnpj = data.get('cnpj', '').strip()

        if not empresa_nome and not cnpj:
            return {"isDuplicate": False}

        # Query de busca (Case insensitive para nome)
        query = Q()
        if empresa_nome:
            query |= Q(empresa__iexact=empresa_nome)
        if cnpj:
            # Remove pontuação básica para comparar se necessário,
            # aqui assume que vem formatado ou limpo
            query |= Q(cnpj=cnpj)

        # Busca no banco
        # Pega o primeiro match
        matches = Lead.objects.filter(query).first()

        if matches:
            return {
                "isDuplicate": True,
                "confidence": 100,
                "reason": "Empresa com mesmo nome ou CNPJ encontrada no banco de dados.",
                "similarLeadName": matches.empresa,
                "similarLeadId": matches.id
            }

        return {"isDuplicate": False}
