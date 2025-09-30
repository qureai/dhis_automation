"""
Service layer for image processing and DHIS2 integration
Separates business logic from views for better maintainability
"""
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .models import ImageUpload
from .utils import LLMProcessor, S3Handler
from .playwright_integration import sync_process_and_enter_data

logger = logging.getLogger(__name__)


class RegisterProcessingService:
    """Service for processing patient register images (dual upload feature)"""
    
    def __init__(self):
        self.llm_processor = LLMProcessor()
        self.s3_handler = S3Handler() if self._s3_enabled() else None
    
    def _s3_enabled(self) -> bool:
        """Check if S3 storage is configured"""
        return (getattr(settings, 'USE_S3_STORAGE', False) and 
                getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None))
    
    def process_register_images(
        self, 
        image1: UploadedFile, 
        image2: UploadedFile,
        enable_dhis_integration: bool = True
    ) -> Dict:
        """
        Process two register images and extract patient records
        
        Args:
            image1: Left side of register
            image2: Right side of register
            enable_dhis_integration: Whether to submit data to DHIS2
            
        Returns:
            Dict containing processing results
        """
        session_id = str(uuid.uuid4())
        logger.info(f"🏥 === REGISTER PROCESSING STARTED ===")
        logger.info(f"📋 Session ID: {session_id}")
        logger.info(f"📂 Image 1: {image1.name} ({image1.size} bytes)")
        logger.info(f"📂 Image 2: {image2.name} ({image2.size} bytes)")
        logger.info(f"🔗 DHIS2 Integration: {'Enabled' if enable_dhis_integration else 'Disabled'}")
        logger.info(f"☁️ S3 Storage: {'Enabled' if self.s3_handler else 'Disabled'}")
        
        try:
            logger.info("📝 Step 1: Creating database records...")
            upload1, upload2 = self._create_upload_records(image1, image2, session_id)
            
            logger.info("🤖 Step 2: Processing images with AI/LLM...")
            patient_records = self._extract_patient_data(upload1, upload2)
            
            logger.info("🏥 Step 3: DHIS2 integration check...")
            dhis_results = None
            if enable_dhis_integration and patient_records:
                logger.info(f"✅ DHIS2 integration enabled - submitting {len(patient_records)} records")
                dhis_results = self._submit_to_dhis(patient_records)
            else:
                logger.info("⏭️ DHIS2 integration skipped")
            
            logger.info("☁️ Step 4: S3 upload check...")
            s3_urls = self._upload_to_s3(upload1, upload2, patient_records, session_id)
            
            logger.info("💾 Step 5: Updating database records...")
            self._update_upload_records(upload1, upload2, patient_records, session_id)
            
            logger.info("🎉 Step 6: Building success response...")
            result = self._build_success_response(
                upload1, upload2, patient_records, session_id, s3_urls, dhis_results
            )
            
            logger.info(f"✅ REGISTER PROCESSING COMPLETED SUCCESSFULLY")
            logger.info(f"📊 Results: {len(patient_records)} patients extracted, Session: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ REGISTER PROCESSING FAILED: {str(e)}")
            logger.error(f"💥 Session: {session_id}")
            import traceback
            logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
            self._mark_uploads_failed(locals().get('upload1'), locals().get('upload2'))
            raise
    
    def _create_upload_records(
        self, 
        image1: UploadedFile, 
        image2: UploadedFile, 
        session_id: str
    ) -> Tuple[ImageUpload, ImageUpload]:
        """Create ImageUpload records for both images"""
        logger.info(f"📝 Creating database records for session {session_id}")
        
        upload1 = ImageUpload.objects.create(
            original_image=image1,
            original_filename=f"left_register_{image1.name}",
            processing_status='processing',
            session_id=session_id
        )
        logger.info(f"✅ Created upload record 1: ID={upload1.id}, file={upload1.original_filename}")
        
        upload2 = ImageUpload.objects.create(
            original_image=image2,
            original_filename=f"right_register_{image2.name}",
            processing_status='processing',
            session_id=session_id
        )
        logger.info(f"✅ Created upload record 2: ID={upload2.id}, file={upload2.original_filename}")
        
        return upload1, upload2
    
    def _extract_patient_data(
        self, 
        upload1: ImageUpload, 
        upload2: ImageUpload
    ) -> List[Dict]:
        """Extract patient records from register images"""
        logger.info("🤖 Starting AI/LLM processing of register images")
        logger.info(f"📸 Processing image pair: {upload1.original_filename} + {upload2.original_filename}")
        logger.info(f"📁 Image paths: {upload1.original_image.path}, {upload2.original_image.path}")
        
        try:
            logger.info("🚀 Calling LLM processor for horizontal table extraction...")
            patient_records = self.llm_processor.process_horizontal_table_images(
                upload1.original_image.path,
                upload2.original_image.path
            )
            
            logger.info(f"✅ LLM processing completed successfully!")
            logger.info(f"📊 Extracted {len(patient_records)} patient records from register images")
            
            if patient_records:
                # Log sample of first record for debugging
                first_record = patient_records[0]
                logger.info(f"📋 Sample record fields: {list(first_record.keys())}")
                logger.info(f"🧑‍⚕️ Sample patient: {first_record.get('patient_name', 'N/A')}")
            else:
                logger.warning("⚠️ No patient records extracted - images may be unclear or empty")
                
            return patient_records
            
        except Exception as e:
            logger.error(f"❌ LLM processing failed: {str(e)}")
            import traceback
            logger.error(f"🔍 Full error trace: {traceback.format_exc()}")
            return []
    
    def _submit_to_dhis(self, patient_records: List[Dict]) -> Optional[Dict]:
        """Submit patient records to DHIS2"""
        logger.info("🏥 Checking DHIS2 integration configuration...")
        
        if not os.environ.get('ENABLE_DHIS_INTEGRATION', 'False') == 'True':
            logger.info("⏭️ DHIS2 integration disabled via environment variable")
            return None
        
        # Use patient registration credentials (different from facility reporting)
        dhis_config = {
            'base_url': os.environ.get('DHIS_BASE_URL', 'http://172.236.165.102/dhis-test/apps/capture#/'),
            'username': os.environ.get('DHIS_PATIENT_USERNAME', 'admin'), 
            'password': '***' if os.environ.get('DHIS_PATIENT_PASSWORD') else 'district'
        }
        logger.info(f"🔧 DHIS2 Patient Registration Configuration: {dhis_config}")
        logger.info(f"📤 Submitting {len(patient_records)} patient records to DHIS2 Patient Registration System")
        
        try:
            logger.info("🚀 Calling DHIS2 patient registration sync_process_and_enter_data...")
            dhis_results = sync_process_and_enter_data(
                patient_records,
                base_url=os.environ.get('DHIS_BASE_URL', 'http://172.236.165.102/dhis-test/apps/capture#/'),
                username=os.environ.get('DHIS_PATIENT_USERNAME', 'admin'),
                password=os.environ.get('DHIS_PATIENT_PASSWORD', 'district')
            )
            
            logger.info("✅ DHIS2 submission completed successfully!")
            logger.info(f"📊 DHIS2 Results: {dhis_results}")
            
            # Update patient records with submission status
            for i, patient in enumerate(patient_records):
                patient['dhis_entry_status'] = 'submitted'
                logger.info(f"✅ Marked patient {i+1} as submitted to DHIS2")
                
            return dhis_results
            
        except Exception as e:
            logger.error(f"❌ DHIS2 submission failed: {str(e)}")
            import traceback
            logger.error(f"🔍 DHIS2 error trace: {traceback.format_exc()}")
            
            for i, patient in enumerate(patient_records):
                patient['dhis_entry_status'] = 'failed'
                logger.error(f"❌ Marked patient {i+1} as failed DHIS2 submission")
            return None
    
    def _upload_to_s3(
        self, 
        upload1: ImageUpload, 
        upload2: ImageUpload, 
        patient_records: List[Dict], 
        session_id: str
    ) -> Dict:
        """Upload files to S3 if configured"""
        s3_urls = {}
        
        if not self.s3_handler:
            return s3_urls
            
        try:
            # Upload images
            key1 = f"registers/{session_id}/left_side_{upload1.id}.jpg"
            s3_url1 = self.s3_handler.upload_file(upload1.original_image.file, key1)
            if s3_url1:
                upload1.s3_url = s3_url1
                upload1.save()
                s3_urls['left_side_s3_url'] = s3_url1
            
            key2 = f"registers/{session_id}/right_side_{upload2.id}.jpg"
            s3_url2 = self.s3_handler.upload_file(upload2.original_image.file, key2)
            if s3_url2:
                upload2.s3_url = s3_url2
                upload2.save()
                s3_urls['right_side_s3_url'] = s3_url2
            
            # Upload extracted data
            if patient_records:
                data_key = f"registers/{session_id}/extracted_patients.json"
                data_url = self._upload_json_to_s3(patient_records, session_id, data_key)
                if data_url:
                    s3_urls['extracted_data_s3_url'] = data_url
                    
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            
        return s3_urls
    
    def _upload_json_to_s3(self, data: List[Dict], session_id: str, key: str) -> Optional[str]:
        """Upload JSON data to S3"""
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "session_id": session_id,
                    "total_patients": len(data),
                    "patient_records": data,
                    "extracted_at": datetime.now().isoformat()
                }, f, indent=2)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                s3_url = self.s3_handler.upload_file(f, key)
            
            os.unlink(temp_path)
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading JSON to S3: {str(e)}")
            return None
    
    def _update_upload_records(
        self, 
        upload1: ImageUpload, 
        upload2: ImageUpload, 
        patient_records: List[Dict], 
        session_id: str
    ):
        """Update upload records with processing results"""
        extraction_summary = {
            "total_patients_extracted": len(patient_records),
            "extraction_method": "register_processing",
            "session_id": session_id,
            "processed_at": datetime.now().isoformat()
        }
        
        status = 'completed' if patient_records else 'failed'
        processed_at = datetime.now()
        
        for upload in [upload1, upload2]:
            upload.extracted_data = extraction_summary
            upload.processing_status = status
            upload.processed_at = processed_at
            upload.save()
    
    def _mark_uploads_failed(self, upload1: Optional[ImageUpload], upload2: Optional[ImageUpload]):
        """Mark uploads as failed"""
        for upload in [upload1, upload2]:
            if upload:
                try:
                    upload.processing_status = 'failed'
                    upload.save()
                except:
                    pass
    
    def _build_success_response(
        self, 
        upload1: ImageUpload, 
        upload2: ImageUpload, 
        patient_records: List[Dict], 
        session_id: str, 
        s3_urls: Dict,
        dhis_results: Optional[Dict]
    ) -> Dict:
        """Build successful response"""
        response_data = {
            "session_id": session_id,
            "feature_type": "register_processing",
            "image1_id": upload1.id,
            "image2_id": upload2.id,
            "total_patients_extracted": len(patient_records),
            "patient_records": patient_records,
            "processing_status": "completed",
            "uploaded_at": upload1.uploaded_at.isoformat(),
            "processed_at": upload1.processed_at.isoformat() if upload1.processed_at else None,
            "message": f"Successfully extracted {len(patient_records)} patient records from register images"
        }
        
        # Add S3 URLs if available
        response_data.update(s3_urls)
        
        # Add DHIS2 results if available
        if dhis_results:
            response_data['dhis2_submission'] = dhis_results
        
        return response_data


class PDFProcessingService:
    """Service for processing PDF documents (single PDF feature)"""
    
    def __init__(self):
        self.s3_handler = S3Handler() if self._s3_enabled() else None
    
    def _s3_enabled(self) -> bool:
        """Check if S3 storage is configured"""
        return (getattr(settings, 'USE_S3_STORAGE', False) and 
                getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None))
    
    def process_pdf(
        self, 
        pdf_file: UploadedFile,
        enable_dhis_integration: bool = True
    ) -> Dict:
        """
        Process PDF document and extract health facility data
        
        Args:
            pdf_file: Uploaded PDF file
            enable_dhis_integration: Whether to submit data to DHIS2
            
        Returns:
            Dict containing processing results
        """
        session_id = str(uuid.uuid4())
        logger.info(f"Processing PDF - Session: {session_id}")
        
        try:
            # Create database record
            upload = self._create_pdf_upload_record(pdf_file, session_id)
            
            # Process PDF with existing automation system
            extracted_data = self._extract_pdf_data(pdf_file)
            
            # Submit to DHIS2 if enabled
            dhis_results = None
            if enable_dhis_integration and extracted_data:
                dhis_results = self._submit_pdf_to_dhis(pdf_file, extracted_data)
            
            # Upload to S3 if configured
            s3_urls = self._upload_pdf_to_s3(upload, extracted_data, session_id)
            
            # Update database record
            self._update_pdf_upload_record(upload, extracted_data, session_id)
            
            return self._build_pdf_success_response(
                upload, extracted_data, session_id, s3_urls, dhis_results
            )
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            if 'upload' in locals():
                self._mark_pdf_upload_failed(upload)
            raise
    
    def _create_pdf_upload_record(self, pdf_file: UploadedFile, session_id: str) -> ImageUpload:
        """Create database record for PDF upload"""
        upload = ImageUpload.objects.create(
            original_image=pdf_file,  # Reusing image field for PDF
            original_filename=pdf_file.name,
            processing_status='processing',
            session_id=session_id
        )
        logger.info(f"Created PDF upload: {upload.id}")
        return upload
    
    def _extract_pdf_data(self, pdf_file: UploadedFile) -> Dict:
        """Extract data from PDF using existing automation system"""
        logger.info("Extracting data from PDF")
        
        try:
            # Save PDF temporarily for processing
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                for chunk in pdf_file.chunks():
                    f.write(chunk)
                temp_path = f.name
            
            # Use existing PDF processor from api app
            from ..api.services.pdf_processor import PDFProcessor
            processor = PDFProcessor()
            extracted_data, comparison_result = processor.process_pdf(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            logger.info(f"Successfully extracted PDF data: {len(extracted_data)} fields")
            return {
                'extracted_data': extracted_data,
                'comparison_result': comparison_result,
                'fields_count': len(extracted_data)
            }
            
        except Exception as e:
            logger.error(f"Error extracting PDF data: {str(e)}")
            return {}
    
    def _submit_pdf_to_dhis(self, pdf_file: UploadedFile, extracted_data: Dict) -> Optional[Dict]:
        """Submit PDF data to DHIS2"""
        if not os.environ.get('ENABLE_DHIS_INTEGRATION', 'False') == 'True':
            logger.info("DHIS2 integration disabled for PDF")
            return None
            
        logger.info("Submitting PDF data to DHIS2")
        
        try:
            # Use existing DHIS automation system from api app
            from ..api.services.dhis_automation import DHISAutomationService
            dhis_service = DHISAutomationService()
            
            # Extract the actual data if it's wrapped
            pdf_data = extracted_data.get('extracted_data', extracted_data)
            
            dhis_results = dhis_service.fill_dhis_form(pdf_data)
            logger.info("Successfully submitted PDF data to DHIS2")
            return dhis_results
            
        except Exception as e:
            logger.error(f"Error submitting PDF to DHIS2: {str(e)}")
            return None
    
    def _upload_pdf_to_s3(
        self, 
        upload: ImageUpload, 
        extracted_data: Dict, 
        session_id: str
    ) -> Dict:
        """Upload PDF and extracted data to S3"""
        s3_urls = {}
        
        if not self.s3_handler:
            return s3_urls
            
        try:
            # Upload PDF
            pdf_key = f"pdfs/{session_id}/{upload.original_filename}"
            pdf_url = self.s3_handler.upload_file(upload.original_image.file, pdf_key)
            if pdf_url:
                upload.s3_url = pdf_url
                upload.save()
                s3_urls['pdf_s3_url'] = pdf_url
            
            # Upload extracted data
            if extracted_data:
                data_key = f"pdfs/{session_id}/extracted_data.json"
                data_url = self._upload_pdf_json_to_s3(extracted_data, session_id, data_key)
                if data_url:
                    s3_urls['extracted_data_s3_url'] = data_url
                    
        except Exception as e:
            logger.error(f"Error uploading PDF to S3: {str(e)}")
            
        return s3_urls
    
    def _upload_pdf_json_to_s3(self, data: Dict, session_id: str, key: str) -> Optional[str]:
        """Upload PDF extracted JSON data to S3"""
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "session_id": session_id,
                    "extraction_type": "pdf_processing",
                    "extracted_data": data,
                    "extracted_at": datetime.now().isoformat()
                }, f, indent=2)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                s3_url = self.s3_handler.upload_file(f, key)
            
            os.unlink(temp_path)
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading PDF JSON to S3: {str(e)}")
            return None
    
    def _update_pdf_upload_record(
        self, 
        upload: ImageUpload, 
        extracted_data: Dict, 
        session_id: str
    ):
        """Update PDF upload record with processing results"""
        extraction_summary = {
            "extraction_type": "pdf_processing",
            "session_id": session_id,
            "processed_at": datetime.now().isoformat(),
            "fields_extracted": len(extracted_data) if extracted_data else 0
        }
        
        upload.extracted_data = extraction_summary
        upload.processing_status = 'completed' if extracted_data else 'failed'
        upload.processed_at = datetime.now()
        upload.save()
    
    def _mark_pdf_upload_failed(self, upload: ImageUpload):
        """Mark PDF upload as failed"""
        try:
            upload.processing_status = 'failed'
            upload.save()
        except:
            pass
    
    def _build_pdf_success_response(
        self, 
        upload: ImageUpload, 
        extracted_data: Dict, 
        session_id: str, 
        s3_urls: Dict,
        dhis_results: Optional[Dict]
    ) -> Dict:
        """Build successful PDF processing response"""
        response_data = {
            "session_id": session_id,
            "feature_type": "pdf_processing",
            "upload_id": upload.id,
            "extracted_data": extracted_data,
            "processing_status": "completed",
            "uploaded_at": upload.uploaded_at.isoformat(),
            "processed_at": upload.processed_at.isoformat() if upload.processed_at else None,
            "message": f"Successfully extracted data from PDF: {upload.original_filename}"
        }
        
        # Add S3 URLs if available
        response_data.update(s3_urls)
        
        # Add DHIS2 results if available
        if dhis_results:
            response_data['dhis2_submission'] = dhis_results
        
        return response_data