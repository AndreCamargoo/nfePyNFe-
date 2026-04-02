from django.urls import path
from .views import (
    CompanyListCreateView, CompanyRetrieveUpdateDestroyView,
    ProductListCreateView, ProductRetrieveUpdateDestroyView,
    EventListCreateView, EventRetrieveUpdateDestroyView, EventGenerateEmailView,
    LeadListCreateView, LeadRetrieveUpdateDestroyView, LeadCheckDuplicityView, LeadGenerateStrategyView,
    LeadBulkDeleteView, LeadLastTimestampsView, LeadExportView,
    CnesListView, CnesImportView, MunicipalitiesView, MunicipalitiesImportView,
    LeadImportView, LeadImportStatusView, LeadImportCancelView, LeadImportTasksView,
    LeadImportDownloadReportView, LeadImportCleanupView
)

urlpatterns = [
    # Company
    path('leads/companies/', CompanyListCreateView.as_view()),
    path('leads/companies/<int:pk>/', CompanyRetrieveUpdateDestroyView.as_view()),

    # Product
    path('leads/products/', ProductListCreateView.as_view()),
    path('leads/products/<int:pk>/', ProductRetrieveUpdateDestroyView.as_view()),

    # Event
    path('leads/events/', EventListCreateView.as_view()),
    path('leads/events/<int:pk>/', EventRetrieveUpdateDestroyView.as_view()),
    path('leads/events/<int:pk>/generate-email/', EventGenerateEmailView.as_view()),

    # Lead
    path('leads/', LeadListCreateView.as_view()),
    path('leads/export/', LeadExportView.as_view()),

    # Celery
    path('leads/import/', LeadImportView.as_view()),
    path('leads/import/status/<str:task_id>/', LeadImportStatusView.as_view(), name='lead-import-status'),
    path('leads/import/cancel/<str:task_id>/', LeadImportCancelView.as_view(), name='lead-import-cancel'),
    path('leads/import/tasks/', LeadImportTasksView.as_view(), name='lead-import-tasks'),
    path('leads/import/download-report/', LeadImportDownloadReportView.as_view(), name='lead-import-download'),
    path('leads/import/cleanup/', LeadImportCleanupView.as_view(), name='lead-import-cleanup'),

    path('leads/<int:pk>/', LeadRetrieveUpdateDestroyView.as_view()),
    path('leads/check-duplicity/', LeadCheckDuplicityView.as_view()),
    path('leads/generate-strategy/', LeadGenerateStrategyView.as_view()),
    path('leads/bulk-delete/', LeadBulkDeleteView.as_view()),

    # Lead last timestamps
    path('leads/last-timestamps/', LeadLastTimestampsView.as_view()),

    # Cnes
    path('cnes/', CnesListView.as_view()),
    path('cnes/import/', CnesImportView.as_view()),

    # Municipios
    path('municipios/', MunicipalitiesView.as_view()),
    path('municipios/import/', MunicipalitiesImportView.as_view()),
]
