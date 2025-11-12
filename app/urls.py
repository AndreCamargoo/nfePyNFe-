from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

# py ./manage.py spectacular --color --file schema.yml (GERAR DOCUMENTAÇÃO)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('authentication.urls')),

    # Sistema, Acesso e Notificações rotas e modulos
    path('api/v1/', include('sistema.urls')),
    path('api/v1/', include('empresa.urls')),
    path('api/v1/', include('notifications.urls')),

    # Allnube rotas e modulos
    path('api/v1/', include('nfe.urls')),
    path('api/v1/', include('nfe_evento.urls')),
    path('api/v1/', include('nfe_resumo.urls')),
    path('api/v1/', include('apexcharts.urls')),

    # Agenda rotas e modulos
    path('api/v1/', include('agendaGrupo.agenda.urls')),

    # YOUR PATTERNS
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    # path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/documentacao', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  # redoc
]

# + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
