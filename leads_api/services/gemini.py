import os
import requests
import json
import google.generativeai as genai
from django.conf import settings


if hasattr(settings, 'GEMINI_API_KEY'):
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Idealmente, use variáveis de ambiente: os.environ.get("GEMINI_API_KEY")
API_KEY = os.environ.get("GEMINI_API_KEY")
BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"


class GeminiService:
    @staticmethod
    def _call_gemini(prompt):
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        try:
            response = requests.post(BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            # Extração segura
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text_response)
        except Exception as e:
            print(f"Erro na API Gemini: {e}")
            return None

    @staticmethod
    def generate_sales_strategy(lead_data):
        empresa = lead_data.get('empresa')
        produtos = ", ".join([str(p) for p in lead_data.get('produtos_interesse', [])])
        contatos = ", ".join([c.get('nome', '') for c in lead_data.get('contatos', [])])

        prompt = f"""
        Atue como um estrategista de vendas B2B sênior. Analise esta EMPRESA (Lead) e seus contatos para gerar uma estratégia.
        Dados da Empresa:
        - Nome: {empresa}
        - Segmento: {lead_data.get('segmento')}
        - Cidade/UF: {lead_data.get('cidade')}/{lead_data.get('estado')}
        - Classificação Atual: {lead_data.get('classificacao')}
        - Produtos de Interesse: {produtos or 'Genérico'}
        Contatos Disponíveis: {contatos or 'Nenhum'}

        Saída desejada (APENAS JSON VÁLIDO):
        {{
            "analise": "Análise breve sobre a empresa.",
            "pontos_abordagem": ["Ponto 1", "Ponto 2", "Ponto 3"],
            "email_assunto": "Assunto profissional",
            "email_corpo": "Email sugerido."
        }}
        """
        return GeminiService._call_gemini(prompt)

    @staticmethod
    def generate_event_followup(event_name, event_date):
        prompt = f"""
        Você é um assistente comercial. Escreva um email de "Follow-up" profissional.
        Contexto: Encontramos o lead no evento "{event_name}" que ocorreu em {event_date}.
        Objetivo: Agradecer a visita e sugerir reunião.
        Saída desejada (APENAS JSON VÁLIDO):
        {{
            "assunto": "Assunto do email",
            "corpo": "Texto do corpo do email"
        }}
        """
        return GeminiService._call_gemini(prompt)
