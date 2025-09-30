"""
Enhanced views for dual-feature DHIS2 system
Supports both patient register processing and PDF automation
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
import logging

from .models import ImageUpload
from .serializers import ImageUploadSerializer
from .services import RegisterProcessingService, PDFProcessingService
from .validators import RequestValidator, SystemValidator

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for both features"""
    return Response({
        "status": "healthy",
        "message": "DHIS2 Medical Processing System is running",
        "features": {
            "register_processing": {
                "description": "Upload 2 sides of patient register for processing",
                "endpoint": "/api/images/process-register/",
                "method": "POST",
                "fields": ["image1", "image2"]
            },
            "pdf_processing": {
                "description": "Upload PDF document for DHIS2 automation",
                "endpoint": "/api/images/process-pdf/",
                "method": "POST", 
                "fields": ["pdf_file"]
            }
        },
        "dhis2_integration": "Available if configured in environment"
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def process_register(request):
    """
    Process patient register images (dual upload feature)
    Upload 2 sides of a patient register and extract patient records
    """
    logger.info("🚀 === REGISTER PROCESSING REQUEST RECEIVED ===")
    logger.info(f"📨 Request method: {request.method}")
    logger.info(f"📂 Files received: {list(request.FILES.keys())}")
    logger.info(f"📋 POST parameters: {dict(request.POST)}")
    logger.info(f"🌐 Client IP: {request.META.get('REMOTE_ADDR', 'Unknown')}")
    logger.info(f"🔗 User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    
    # Validate request
    logger.info("✅ Validating request structure...")
    validation_result = RequestValidator.validate_register_request(request)
    if not validation_result['valid']:
        logger.warning(f"❌ Register request validation failed: {validation_result['errors']}")
        logger.warning(f"📋 Required fields: image1, image2")
        logger.warning(f"📂 Received files: {list(request.FILES.keys())}")
        return Response({
            "error": "Invalid request",
            "validation_errors": validation_result['errors'],
            "required_fields": ["image1", "image2"],
            "received_files": list(request.FILES.keys())
        }, status=status.HTTP_400_BAD_REQUEST)
    
    logger.info("✅ Request validation passed")
    
    # Get optional parameters
    enable_dhis = request.POST.get('enable_dhis_integration', 'true').lower() == 'true'
    logger.info(f"🔗 DHIS2 integration setting: {enable_dhis}")
    
    try:
        # Use service layer for processing
        service = RegisterProcessingService()
        result = service.process_register_images(
            image1=request.FILES['image1'],
            image2=request.FILES['image2'], 
            enable_dhis_integration=enable_dhis
        )
        
        logger.info(f"Register processing completed successfully: {result['session_id']}")
        return Response(result, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Register processing failed: {str(e)}")
        return Response({
            "error": "Failed to process register images",
            "message": str(e),
            "feature_type": "register_processing"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def process_pdf(request):
    """
    Process PDF document (PDF automation feature)
    Upload a PDF health facility report and extract data for DHIS2
    """
    logger.info("=== PDF PROCESSING STARTED ===")
    
    # Validate request
    validation_result = RequestValidator.validate_pdf_request(request)
    if not validation_result['valid']:
        logger.warning(f"PDF request validation failed: {validation_result['errors']}")
        return Response({
            "error": "Invalid request",
            "validation_errors": validation_result['errors'],
            "required_fields": ["pdf_file"],
            "received_files": list(request.FILES.keys())
        }, status=status.HTTP_400_BAD_REQUEST)
    
    pdf_file = request.FILES['pdf_file']
    
    # Get optional parameters
    enable_dhis = request.POST.get('enable_dhis_integration', 'true').lower() == 'true'
    
    try:
        # Use service layer for processing
        service = PDFProcessingService()
        result = service.process_pdf(
            pdf_file=pdf_file,
            enable_dhis_integration=enable_dhis
        )
        
        logger.info(f"PDF processing completed successfully: {result['session_id']}")
        return Response(result, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"PDF processing failed: {str(e)}")
        return Response({
            "error": "Failed to process PDF document",
            "message": str(e),
            "feature_type": "pdf_processing"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_session_status(request, session_id):
    """Get processing status for a session"""
    try:
        uploads = ImageUpload.objects.filter(session_id=session_id)
        
        if not uploads.exists():
            return Response({
                "error": "Session not found",
                "session_id": session_id
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get session info from first upload
        first_upload = uploads.first()
        
        response_data = {
            "session_id": session_id,
            "feature_type": first_upload.feature_type,
            "processing_status": first_upload.processing_status,
            "uploaded_at": first_upload.uploaded_at.isoformat(),
            "processed_at": first_upload.processed_at.isoformat() if first_upload.processed_at else None,
            "total_files": uploads.count(),
            "extracted_data": first_upload.extracted_data
        }
        
        # Add file-specific info
        files_info = []
        for upload in uploads:
            files_info.append({
                "id": str(upload.id),
                "filename": upload.original_filename,
                "status": upload.processing_status,
                "s3_url": upload.s3_url if upload.s3_url else None
            })
        
        response_data["files"] = files_info
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        return Response({
            "error": "Failed to get session status",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_sessions(request):
    """List recent processing sessions"""
    try:
        # Get distinct sessions ordered by most recent
        sessions = ImageUpload.objects.values(
            'session_id', 'feature_type', 'processing_status', 'uploaded_at'
        ).filter(
            session_id__isnull=False
        ).order_by('-uploaded_at')[:20]  # Last 20 sessions
        
        session_list = []
        for session in sessions:
            session_list.append({
                "session_id": session['session_id'],
                "feature_type": session['feature_type'],
                "processing_status": session['processing_status'],
                "uploaded_at": session['uploaded_at'].isoformat()
            })
        
        return Response({
            "sessions": session_list,
            "total_sessions": len(session_list)
        })
        
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        return Response({
            "error": "Failed to list sessions",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def system_info(request):
    """Get system information and configuration"""
    from django.conf import settings
    
    # Validate system configuration
    system_validation = SystemValidator.validate_system_config()
    
    return Response({
        "system": {
            "name": "DHIS2 Medical Processing System",
            "version": "2.0.0",
            "features": ["register_processing", "pdf_processing"],
            "status": "ready" if system_validation['valid'] else "configuration_issues"
        },
        "configuration": system_validation['config'],
        "validation": {
            "valid": system_validation['valid'],
            "issues": system_validation['issues'],
            "warnings": system_validation['warnings']
        },
        "endpoints": {
            "register_processing": "/api/images/process-register/",
            "pdf_processing": "/api/images/process-pdf/",
            "session_status": "/api/images/session/{session_id}/",
            "list_sessions": "/api/images/sessions/"
        },
        "limits": {
            "max_image_size_mb": 50,
            "max_pdf_size_mb": 100,
            "supported_image_formats": [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"],
            "supported_document_formats": [".pdf"]
        }
    })


# Legacy ViewSet for backward compatibility
class ImageUploadViewSet(viewsets.ModelViewSet):
    """Legacy ViewSet maintained for backward compatibility"""
    queryset = ImageUpload.objects.all()
    serializer_class = ImageUploadSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]
    
    def create(self, request):
        """Legacy single image upload"""
        logger.info("Legacy single image upload")
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save(feature_type='single_image')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)