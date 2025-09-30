from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_v2 import (
    ImageUploadViewSet, 
    health_check, 
    process_register, 
    process_pdf,
    get_session_status,
    list_sessions,
    system_info
)

# Legacy router for backward compatibility
router = DefaultRouter()
router.register(r'legacy', ImageUploadViewSet)

urlpatterns = [
    # Main feature endpoints
    path('health/', health_check, name='health_check'),
    path('process-register/', process_register, name='process_register'),
    path('process-pdf/', process_pdf, name='process_pdf'),
    
    # Session management
    path('session/<str:session_id>/', get_session_status, name='get_session_status'),
    path('sessions/', list_sessions, name='list_sessions'),
    path('system/', system_info, name='system_info'),
    
    # Legacy endpoints for backward compatibility
    path('', include(router.urls)),
]