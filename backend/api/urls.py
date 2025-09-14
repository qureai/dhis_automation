from django.urls import path
from . import views

urlpatterns = [
    # Main processing endpoint (combined PDF processing + DHIS filling)
    path('process-pdf-and-fill-dhis', views.process_pdf_and_fill_dhis, name='process_pdf_and_fill_dhis'),
    
    # Legacy individual endpoints (kept for backward compatibility)
    path('process-pdf', views.process_pdf, name='process_pdf'),
    path('fill-dhis-form', views.fill_dhis_form, name='fill_dhis_form'),
    
    # Status and monitoring endpoints
    path('upload/<int:upload_id>/status', views.upload_status, name='upload_status'),
    path('upload/<int:upload_id>/logs', views.upload_logs, name='upload_logs'),
    path('system-status', views.system_status, name='system_status'),
    path('health', views.health_check, name='health_check'),
]