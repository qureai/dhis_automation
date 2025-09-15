import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FileUploadParser
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .models import PDFUpload, ProcessingLog
from .serializers import (
    PDFUploadSerializer, 
    PDFProcessResponseSerializer,
    DHISProcessResponseSerializer
)
from .services.pdf_processor import PDFProcessor
from .services.dhis_automation import DHISAutomationService

logger = logging.getLogger(__name__)


def log_processing_step(upload_instance, level, message):
    """Helper to log processing steps"""
    ProcessingLog.objects.create(
        upload=upload_instance,
        level=level,
        message=message
    )
    # Print to terminal with emoji based on level
    emoji = "ℹ️" if level == 'info' else "⚠️" if level == 'warning' else "❌"
    print(f"{emoji} Upload {upload_instance.id}: {message}")
    logger.info(f"Upload {upload_instance.id}: {message}")


@api_view(['POST'])
@parser_classes([MultiPartParser, FileUploadParser])
def process_pdf_and_fill_dhis(request):
    """
    Single API endpoint that processes PDF and fills DHIS2 form in one operation
    """
    print("\n🚀 === PDF Processing Request Started ===")
    logger.info("=== PDF Processing Request Started ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Content type: {request.content_type}")
    logger.info(f"Files in request: {list(request.FILES.keys())}")
    
    try:
        if 'pdf' not in request.FILES:
            print("❌ No PDF file provided in request")
            logger.warning("No PDF file provided in request")
            return Response(
                {'error': 'No PDF file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pdf_file = request.FILES['pdf']
        print(f"📄 PDF file received: {pdf_file.name} ({pdf_file.size} bytes)")
        logger.info(f"PDF file received: {pdf_file.name} ({pdf_file.size} bytes)")
        
        # Validate file type
        if not pdf_file.name.lower().endswith('.pdf'):
            print(f"❌ Invalid file type attempted: {pdf_file.name}")
            logger.warning(f"Invalid file type attempted: {pdf_file.name}")
            return Response(
                {'error': 'Only PDF files are allowed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print("✅ File validation passed - creating upload record")
        logger.info("File validation passed - proceeding with upload record creation")
        
        # Create upload record
        upload = PDFUpload.objects.create(
            file=pdf_file,
            status='uploaded'
        )
        
        print(f"📝 Upload record created with ID: {upload.id}")
        logger.info(f"Upload record created with ID: {upload.id}")
        log_processing_step(upload, 'info', f'PDF uploaded: {pdf_file.name} ({pdf_file.size} bytes)')
        
        # STEP 1: Process PDF
        print("\n🔄 STEP 1: Starting PDF Processing")
        logger.info("=== STEP 1: PDF Processing Started ===")
        
        upload.status = 'processing'
        upload.save()
        
        log_processing_step(upload, 'info', 'Starting PDF processing')
        
        print("🎭 Initializing FAKE OCR PDF processor (loads health_facility_report.json)")
        logger.info("Initializing FAKE OCR PDF processor")
        processor = PDFProcessor()
        
        try:
            pdf_path = upload.file.path
            print(f"📁 PDF file uploaded at: {pdf_path}")
            logger.info(f"PDF file uploaded: {pdf_path}")
            
            print("🎭 FAKE OCR: Simulating PDF processing - will load health_facility_report.json")
            logger.info("Calling processor.process_pdf() with root llm.py integration")
            extracted_data, comparison_result = processor.process_pdf(pdf_path)
            
            print(f"🎭 FAKE OCR completed! Loaded {len(extracted_data)} fields from health_facility_report.json")
            logger.info(f"PDF processing successful - {len(extracted_data)} fields extracted")
            
            # Update upload with PDF processing results
            upload.extracted_data = extracted_data
            upload.comparison_result = comparison_result
            upload.status = 'compared'
            upload.processed_at = timezone.now()
            upload.save()
            
            log_processing_step(
                upload, 'info', 
                f'🎭 FAKE OCR completed. Loaded {len(extracted_data)} fields from health_facility_report.json'
            )
            
            print(f"📊 Sample loaded fields: {list(extracted_data.keys())[:5]}...")
            logger.info(f"Sample loaded fields from fake OCR: {list(extracted_data.keys())[:5]}")
            
        except Exception as e:
            print(f"❌ FAKE OCR failed: {str(e)}")
            logger.error(f"FAKE OCR processing failed: {str(e)}")
            
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            
            log_processing_step(upload, 'error', f'🎭 FAKE OCR failed: {str(e)}')
            
            return Response(
                {'error': f'FAKE OCR processing failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # STEP 2: Fill DHIS2 Form
        print("\n🏥 STEP 2: Starting DHIS2 Form Filling")
        logger.info("=== STEP 2: DHIS2 Form Filling Started ===")
        upload.status = 'dhis_processing'
        upload.save()
        
        log_processing_step(upload, 'info', 'Starting DHIS2 form filling')
        
        print("🔧 Initializing DHIS automation service")
        logger.info("Initializing DHIS automation service")
        dhis_service = DHISAutomationService()
        
        # Check if automation is ready
        print("🔍 Checking DHIS automation readiness...")
        logger.info("Checking DHIS automation status")
        automation_status = dhis_service.get_automation_status()
        
        print(f"📋 Automation status: {automation_status}")
        logger.info(f"Automation status check: {automation_status}")
        
        if not automation_status['ready']:
            error_msg = "DHIS automation not ready: "
            if not automation_status.get('dhis_automation_imported'):
                error_msg += "automation class not available; "
            if automation_status.get('missing_env_vars'):
                error_msg += f"missing environment variables: {', '.join(automation_status['missing_env_vars'])}"
            
            print(f"❌ DHIS automation not ready: {error_msg}")
            logger.error(f"DHIS automation not ready: {error_msg}")
            
            upload.status = 'failed'
            upload.error_message = error_msg
            upload.save()
            
            log_processing_step(upload, 'error', error_msg)
                
            return Response(
                {'error': error_msg.rstrip('; ')}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Run DHIS automation
        print("🚀 DHIS automation is ready - starting form filling")
        logger.info("DHIS automation ready - starting fill_dhis_form()")
        
        try:
            print("🤖 Calling dhis_service.fill_dhis_form() - using root dhis_automation.py logic")
            logger.info("Calling dhis_service.fill_dhis_form() with root automation integration")
            dhis_result = dhis_service.fill_dhis_form(extracted_data)
            
            print(f"✅ DHIS form filling completed: {dhis_result}")
            logger.info(f"DHIS form filling completed: {dhis_result}")
            
            # Update upload with DHIS results
            upload.dhis_result = dhis_result
            upload.status = 'completed'
            upload.save()
            
            log_processing_step(
                upload, 'info', 
                f'DHIS2 form filling completed: {dhis_result.get("fields_filled", 0)} fields filled'
            )
            
            print(f"🎉 Processing completed successfully!")
            print(f"📊 Fields filled: {dhis_result.get('fields_filled', 0)}/{dhis_result.get('total_fields', 0)}")
            print(f"📈 Success rate: {dhis_result.get('success_rate', '0%')}")
            logger.info(f"Complete workflow successful - {dhis_result.get('fields_filled', 0)} fields filled")
            
            # Prepare final response
            response_data = {
                'id': upload.id,
                'status': 'completed',
                'pdf_processing': {
                    'extracted_data': extracted_data,
                    'comparison_result': comparison_result,
                    'fields_extracted': len(extracted_data)
                },
                'dhis_processing': {
                    'status': dhis_result.get('status', 'completed'),
                    'fields_filled': dhis_result.get('fields_filled', 0),
                    'total_fields': dhis_result.get('total_fields', 0),
                    'success_rate': dhis_result.get('success_rate', '0%'),
                    'validation_passed': dhis_result.get('validation_passed', False),
                    'details': dhis_result.get('details', {})
                },
                'message': 'PDF processed and DHIS2 form filled successfully'
            }
            
            print("📤 Sending success response to frontend")
            logger.info("Sending success response to frontend")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ DHIS form filling failed: {str(e)}")
            logger.error(f"DHIS2 form filling failed: {str(e)}")
            
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            
            log_processing_step(upload, 'error', f'DHIS2 form filling failed: {str(e)}')
            
            return Response(
                {'error': f'DHIS2 form filling failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Unexpected error in process_pdf_and_fill_dhis: {e}")
        logger.error(f"Full traceback: {error_details}")
        
        # Try to log to upload record if it exists
        if 'upload' in locals():
            try:
                log_processing_step(upload, 'error', f'Unexpected error: {str(e)}')
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
            except:
                pass
        
        return Response(
            {
                'error': 'Internal server error',
                'details': str(e) if hasattr(e, '__str__') else 'Unknown error'
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([MultiPartParser, FileUploadParser])
def process_pdf(request):
    """
    Process uploaded PDF and compare with reference document
    """
    try:
        if 'pdf' not in request.FILES:
            return Response(
                {'error': 'No PDF file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pdf_file = request.FILES['pdf']
        
        # Validate file type
        if not pdf_file.name.lower().endswith('.pdf'):
            return Response(
                {'error': 'Only PDF files are allowed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create upload record
        upload = PDFUpload.objects.create(
            file=pdf_file,
            status='uploaded'
        )
        
        log_processing_step(upload, 'info', f'PDF uploaded: {pdf_file.name}')
        
        # Update status to processing
        upload.status = 'processing'
        upload.save()
        
        log_processing_step(upload, 'info', 'Starting PDF processing')
        
        # Process the PDF
        processor = PDFProcessor()
        
        try:
            pdf_path = upload.file.path
            extracted_data, comparison_result = processor.process_pdf(pdf_path)
            
            # Update upload with results
            upload.extracted_data = extracted_data
            upload.comparison_result = comparison_result
            upload.status = 'compared'
            upload.processed_at = timezone.now()
            upload.save()
            
            log_processing_step(
                upload, 'info', 
                f'PDF processing completed. Extracted {len(extracted_data)} fields'
            )
            
            # Prepare response
            response_data = {
                'id': upload.id,
                'status': upload.status,
                'extracted_data': extracted_data,
                'comparison_result': comparison_result,
                'message': 'PDF processed successfully'
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Update upload with error
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            
            log_processing_step(upload, 'error', f'PDF processing failed: {str(e)}')
            
            return Response(
                {'error': f'PDF processing failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in process_pdf: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def fill_dhis_form(request):
    """
    Fill DHIS2 form using extracted data
    """
    try:
        extracted_data = request.data.get('extracted_data')
        
        if not extracted_data:
            return Response(
                {'error': 'No extracted data provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Starting DHIS2 form filling with {len(extracted_data)} fields")
        
        # Initialize DHIS automation service
        dhis_service = DHISAutomationService()
        
        # Check if automation is ready
        automation_status = dhis_service.get_automation_status()
        
        if not automation_status['ready']:
            error_msg = "DHIS automation not ready: "
            if not automation_status['automation_script_exists']:
                error_msg += "automation script missing; "
            if automation_status['missing_env_vars']:
                error_msg += f"missing environment variables: {', '.join(automation_status['missing_env_vars'])}"
                
            return Response(
                {'error': error_msg.rstrip('; ')}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Run DHIS automation
        try:
            result = dhis_service.fill_dhis_form(extracted_data)
            
            logger.info(f"DHIS2 form filling completed: {result.get('fields_filled', 0)} fields filled")
            
            response_data = {
                'status': result.get('status', 'completed'),
                'fields_filled': result.get('fields_filled', 0),
                'success_rate': result.get('success_rate', '0%'),
                'message': 'DHIS2 form filled successfully',
                'details': result.get('details', {})
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"DHIS2 form filling failed: {e}")
            
            return Response(
                {'error': f'DHIS2 form filling failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in fill_dhis_form: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def upload_status(request, upload_id):
    """
    Get status of a specific upload
    """
    try:
        upload = PDFUpload.objects.get(id=upload_id)
        serializer = PDFUploadSerializer(upload)
        return Response(serializer.data)
        
    except PDFUpload.DoesNotExist:
        return Response(
            {'error': 'Upload not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def upload_logs(request, upload_id):
    """
    Get processing logs for a specific upload
    """
    try:
        upload = PDFUpload.objects.get(id=upload_id)
        logs = upload.logs.all()[:50]  # Get latest 50 logs
        
        log_data = [
            {
                'level': log.level,
                'message': log.message,
                'timestamp': log.timestamp
            }
            for log in logs
        ]
        
        return Response({'logs': log_data})
        
    except PDFUpload.DoesNotExist:
        return Response(
            {'error': 'Upload not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def system_status(request):
    """
    Get system status and configuration
    """
    try:
        # Check PDF processor status
        processor = PDFProcessor()
        pdf_status = {
            'ai_client_configured': processor.portkey_client is not None,
            'reference_pdf_exists': processor.reference_pdf_path.exists()
        }
        
        # Check DHIS automation status
        dhis_service = DHISAutomationService()
        dhis_status = dhis_service.get_automation_status()
        
        system_status = {
            'pdf_processor': pdf_status,
            'dhis_automation': dhis_status,
            'overall_ready': (
                pdf_status['reference_pdf_exists'] and 
                dhis_status['ready']
            )
        }
        
        return Response(system_status)
        
    except Exception as e:
        logger.error(f"Error checking system status: {e}")
        return Response(
            {'error': 'Failed to check system status'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """
    Simple health check endpoint
    """
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now(),
        'version': '1.0.0'
    })