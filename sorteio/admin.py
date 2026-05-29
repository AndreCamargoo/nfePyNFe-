from django.contrib import admin
from .models import EventoSorteio, ParticipanteSorteio


@admin.register(EventoSorteio)
class EventoSorteioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'data_evento', 'local', 'ativo', 'created_at']
    list_filter = ['ativo', 'data_evento']
    search_fields = ['nome', 'local']


@admin.register(ParticipanteSorteio)
class ParticipanteSorteioAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'empresa', 'contato_nome', 'evento', 'vencedor', 'created_at']
    list_filter = ['vencedor', 'evento']
    search_fields = ['empresa', 'contato_nome', 'codigo', 'email']
