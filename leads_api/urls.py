from django.urls import path
from .views import (
    CompanyListCreateView,
    CompanyRetrieveUpdateDestroyView,
    ProductListCreateView,
    ProductRetrieveUpdateDestroyView,
    EventListCreateView,
    EventRetrieveUpdateDestroyView,
    EventGenerateEmailView,
    LeadListCreateView,
    LeadRetrieveUpdateDestroyView,
    LeadCheckDuplicityView,
    LeadGenerateStrategyView,
    LeadBulkDeleteView,
    LeadLastTimestampsView
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
    path('leads/<int:pk>/', LeadRetrieveUpdateDestroyView.as_view()),
    path('leads/check-duplicity/', LeadCheckDuplicityView.as_view()),
    path('leads/generate-strategy/', LeadGenerateStrategyView.as_view()),
    path('leads/bulk-delete/', LeadBulkDeleteView.as_view()),

    # Lead last timestamps
    path('leads/last-timestamps/', LeadLastTimestampsView.as_view()),
]
