from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.core.files.storage import default_storage
from django.conf import settings
import os
import json
import uuid
import logging
import traceback
from datetime import datetime

from .models import ImageUpload
from .serializers import ImageUploadSerializer, ProcessedDataSerializer
from .utils import S3Handler, LLMProcessor
from .playwright_integration import sync_process_and_enter_data

# Configure logger
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Simple health check endpoint that requires no authentication
    """
    return Response({
        "status": "healthy",
        "message": "DHIS Medical Image Processing API is running",
        "authentication_required": False,
        "endpoints": {
            "upload_image": "/api/images/",
            "upload_dual_images": "/api/images/dual-upload/",
            "process_image": "/api/images/{id}/process/",
            "get_image": "/api/images/{id}/",
            "list_images": "/api/images/"
        }
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def dual_image_upload(request):
    """
    Upload and process two images representing left and right sides of a horizontal table
    containing multiple patient records
    """
    logger.info("=== DUAL IMAGE UPLOAD STARTED ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
    logger.info(f"Request POST data: {request.POST}")
    logger.info(f"Request content type: {request.content_type}")
    
    # Check for required files
    if 'image1' not in request.FILES or 'image2' not in request.FILES:
        logger.error("Missing required files - image1 or image2")
        logger.error(f"Available files: {list(request.FILES.keys())}")
        return Response(
            {"error": "Both image1 (left side) and image2 (right side) are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    image1 = request.FILES['image1']  # Left side of horizontal table
    image2 = request.FILES['image2']  # Right side of horizontal table
    
    logger.info(f"Image1 name: {image1.name}, size: {image1.size}")
    logger.info(f"Image2 name: {image2.name}, size: {image2.size}")
    
    # Generate a unique session ID for this dual upload
    session_id = str(uuid.uuid4())
    logger.info(f"Generated session ID: {session_id}")
    
    try:
        logger.info("Creating ImageUpload objects...")
        
        # Save both images
        try:
            upload1 = ImageUpload.objects.create(
                original_image=image1,
                original_filename=f"left_side_{image1.name}",
                processing_status='processing'
            )
            logger.info(f"Created upload1 with ID: {upload1.id}")
        except Exception as e:
            logger.error(f"Error creating upload1: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
        try:
            upload2 = ImageUpload.objects.create(
                original_image=image2,
                original_filename=f"right_side_{image2.name}",
                processing_status='processing'
            )
            logger.info(f"Created upload2 with ID: {upload2.id}")
        except Exception as e:
            logger.error(f"Error creating upload2: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
        # Process horizontal table spanning both images
        logger.info("Initializing LLM Processor...")
        llm_processor = LLMProcessor()
        
        # Extract multiple patient records from the horizontal table
        logger.info(f"Processing images with paths:")
        logger.info(f"  Image1 path: {upload1.original_image.path}")
        logger.info(f"  Image2 path: {upload2.original_image.path}")
        
        try:
            patient_records = llm_processor.process_horizontal_table_images(
                upload1.original_image.path,
                upload2.original_image.path
            )
            logger.info(f"Successfully extracted {len(patient_records)} patient records")
            
            # Trigger Playwright integration to enter data into DHIS2
            if patient_records and os.environ.get('ENABLE_DHIS_INTEGRATION', 'False') == 'True':
                logger.info("Starting DHIS2 data entry via Playwright...")
                try:
                    dhis_results = sync_process_and_enter_data(
                        patient_records,
                        base_url=os.environ.get('DHIS_BASE_URL'),
                        username=os.environ.get('DHIS_USERNAME'),
                        password=os.environ.get('DHIS_PASSWORD')
                    )
                    logger.info(f"DHIS2 data entry results: {dhis_results}")
                    # Add DHIS results to response
                    for patient in patient_records:
                        patient['dhis_entry_status'] = 'submitted'
                except Exception as e:
                    logger.error(f"Error in DHIS2 data entry: {str(e)}")
                    for patient in patient_records:
                        patient['dhis_entry_status'] = 'failed'
                        
        except Exception as e:
            logger.error(f"Error processing images with LLM: {str(e)}")
            logger.error(traceback.format_exc())
            # Don't raise here, return a partial response
            patient_records = []
        
        # Store the extraction results
        extraction_summary = {
            "total_patients_extracted": len(patient_records),
            "extraction_method": "horizontal_table",
            "session_id": session_id,
            "processed_at": datetime.now().isoformat()
        }
        logger.info(f"Extraction summary: {extraction_summary}")
        
        # Update upload records with extraction summary
        try:
            upload1.extracted_data = extraction_summary
            upload1.processing_status = 'completed' if patient_records else 'failed'
            upload1.processed_at = datetime.now()
            upload1.save()
            logger.info("Updated upload1 with extraction summary")
        except Exception as e:
            logger.error(f"Error updating upload1: {str(e)}")
            logger.error(traceback.format_exc())
        
        try:
            upload2.extracted_data = extraction_summary
            upload2.processing_status = 'completed' if patient_records else 'failed'
            upload2.processed_at = datetime.now()
            upload2.save()
            logger.info("Updated upload2 with extraction summary")
        except Exception as e:
            logger.error(f"Error updating upload2: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Upload to S3 if configured
        s3_urls = {}
        if settings.USE_S3_STORAGE and settings.AWS_STORAGE_BUCKET_NAME:
            s3_handler = S3Handler()
            
            # Upload image1 to S3
            key1 = f"horizontal-tables/{session_id}/left_side_{upload1.id}.{image1.name.split('.')[-1]}"
            s3_url1 = s3_handler.upload_file(upload1.original_image.file, key1)
            if s3_url1:
                upload1.s3_url = s3_url1
                upload1.save()
                s3_urls['left_side_s3_url'] = s3_url1
            
            # Upload image2 to S3
            key2 = f"horizontal-tables/{session_id}/right_side_{upload2.id}.{image2.name.split('.')[-1]}"
            s3_url2 = s3_handler.upload_file(upload2.original_image.file, key2)
            if s3_url2:
                upload2.s3_url = s3_url2
                upload2.save()
                s3_urls['right_side_s3_url'] = s3_url2
            
            # Upload extracted patient records as JSON to S3
            if patient_records:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump({
                        "session_id": session_id,
                        "total_patients": len(patient_records),
                        "patient_records": patient_records,
                        "extracted_at": datetime.now().isoformat()
                    }, f, indent=2)
                    temp_path = f.name
                
                with open(temp_path, 'rb') as f:
                    key = f"horizontal-tables/{session_id}/extracted_patients.json"
                    results_url = s3_handler.upload_file(f, key)
                    if results_url:
                        s3_urls['extracted_data_s3_url'] = results_url
                
                os.unlink(temp_path)
        
        response_data = {
            "id": session_id,
            "image1_id": upload1.id,
            "image2_id": upload2.id,
            "left_side_url": request.build_absolute_uri(upload1.original_image.url),
            "right_side_url": request.build_absolute_uri(upload2.original_image.url),
            "total_patients_extracted": len(patient_records),
            "patient_records": patient_records,
            "extraction_summary": extraction_summary,
            "processing_status": "completed",
            "uploaded_at": upload1.uploaded_at.isoformat(),
            "processed_at": upload1.processed_at.isoformat() if upload1.processed_at else None,
            "message": f"Successfully extracted {len(patient_records)} patient records from horizontal table"
        }
        
        # Add S3 URLs if available
        response_data.update(s3_urls)
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"=== FATAL ERROR IN DUAL IMAGE UPLOAD ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Full traceback:")
        logger.error(traceback.format_exc())
        
        # Update status to failed
        if 'upload1' in locals():
            try:
                upload1.processing_status = 'failed'
                upload1.save()
                logger.info("Set upload1 status to failed")
            except:
                pass
        if 'upload2' in locals():
            try:
                upload2.processing_status = 'failed'
                upload2.save()
                logger.info("Set upload2 status to failed")
            except:
                pass
        
        # Return more detailed error information in debug mode
        error_response = {
            "error": f"Failed to process horizontal table: {str(e)}",
            "error_type": type(e).__name__,
        }
        
        if settings.DEBUG:
            error_response["traceback"] = traceback.format_exc()
            error_response["session_id"] = session_id if 'session_id' in locals() else None
            
        return Response(
            error_response,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class ImageUploadViewSet(viewsets.ModelViewSet):
    queryset = ImageUpload.objects.all()
    serializer_class = ImageUploadSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]  # No authentication required
    authentication_classes = []  # No authentication required
    
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            
            if instance.original_image:
                s3_handler = S3Handler()
                image_file = instance.original_image.file
                key = f"uploads/{instance.id}/{instance.original_image.name}"
                s3_url = s3_handler.upload_file(image_file, key)
                
                if s3_url:
                    instance.s3_url = s3_url
                    instance.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        instance = self.get_object()
        
        if instance.processing_status in ['processing', 'completed']:
            return Response(
                {"error": "Image is already being processed or has been processed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.processing_status = 'processing'
        instance.save()
        
        try:
            llm_processor = LLMProcessor()
            image_path = instance.original_image.path
            
            processed_data = llm_processor.process_image(image_path)
            
            if processed_data:
                instance.first_name = processed_data.get('first_name', '')
                instance.last_name = processed_data.get('last_name', '')
                
                try:
                    instance.date_of_birth = datetime.strptime(
                        processed_data.get('date_of_birth', ''), '%Y-%m-%d'
                    ).date() if processed_data.get('date_of_birth') != 'Not Found' else None
                except:
                    instance.date_of_birth = None
                
                try:
                    instance.date_of_diagnosis = datetime.strptime(
                        processed_data.get('date_of_diagnosis', ''), '%Y-%m-%d'
                    ).date() if processed_data.get('date_of_diagnosis') != 'Not Found' else None
                except:
                    instance.date_of_diagnosis = None
                
                instance.case_detection_options = processed_data.get('case_detection_options', '')
                instance.processed_data = processed_data
                instance.processing_status = 'completed'
                instance.processed_at = datetime.now()
                
                if settings.AWS_STORAGE_BUCKET_NAME:
                    s3_handler = S3Handler()
                    import json
                    import tempfile
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(processed_data, f)
                        temp_path = f.name
                    
                    with open(temp_path, 'rb') as f:
                        key = f"processed/{instance.id}/result.json"
                        s3_handler.upload_file(f, key)
                    
                    os.unlink(temp_path)
            else:
                instance.processing_status = 'failed'
            
            instance.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
            
        except Exception as e:
            instance.processing_status = 'failed'
            instance.save()
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
