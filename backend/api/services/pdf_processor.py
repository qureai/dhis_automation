import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from django.conf import settings
import base64

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Service that directly imports and uses functions from root llm.py"""
    
    def __init__(self):
        # Add root directory to Python path to import llm
        self.root_dir = Path(settings.BASE_DIR).parent
        if str(self.root_dir) not in sys.path:
            sys.path.insert(0, str(self.root_dir))
        
        # Import components from root llm.py
        try:
            import llm
            self.llm_module = llm
            
            # Get the portkey client from llm.py if available
            if hasattr(llm, 'port_key'):
                self.portkey_client = llm.port_key
                logger.info("Using Portkey client from root llm.py")
            else:
                self.portkey_client = None
                logger.warning("No Portkey client found in root llm.py")
            
            # Get schema mappings from llm.py
            if hasattr(llm, 'mapping'):
                self.schema_mapping = llm.mapping
                logger.info(f"Imported {len(self.schema_mapping)} schema mappings from root llm.py")
            else:
                logger.warning("No schema mappings found in root llm.py")
                self.schema_mapping = {}
                
        except ImportError as e:
            logger.error(f"Failed to import from root llm.py: {e}")
            self.llm_module = None
            self.portkey_client = None
            self.schema_mapping = {}
        
        # Path to reference PDF (report_digital.pdf)
        self.reference_pdf_path = self.root_dir / 'report_digital.pdf'
    
    def process_pdf(self, pdf_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Fake OCR process: Load health_facility_report.json directly instead of processing PDF
        Returns: (extracted_data, comparison_result)
        """
        try:
            logger.info(f"🎭 FAKE OCR: Simulating PDF processing for: {pdf_path}")
            logger.info("🎭 FAKE OCR: Loading health_facility_report.json instead of real OCR")
            
            # Step 1: Load data from health_facility_report.json (fake OCR)
            extracted_data = self._load_health_facility_data()
            
            # Step 2: Create fake comparison result
            comparison_result = self._create_fake_comparison_result(extracted_data)
            
            logger.info(f"🎭 FAKE OCR: Complete! Loaded {len(extracted_data)} fields from health_facility_report.json")
            
            return extracted_data, comparison_result
            
        except Exception as e:
            logger.error(f"Fake OCR process failed: {e}")
            raise Exception(f"Fake OCR error: {str(e)}")
    
    def _load_health_facility_data(self) -> Dict[str, Any]:
        """
        Load health facility data from JSON file (fake OCR)
        """
        try:
            health_facility_json_path = self.root_dir / 'health_facility_report.json'
            
            if not health_facility_json_path.exists():
                logger.error(f"🎭 FAKE OCR: health_facility_report.json not found at {health_facility_json_path}")
                raise FileNotFoundError("health_facility_report.json not found")
            
            logger.info(f"🎭 FAKE OCR: Loading data from {health_facility_json_path}")
            
            with open(health_facility_json_path, 'r', encoding='utf-8') as f:
                health_data = json.load(f)
            
            logger.info(f"🎭 FAKE OCR: Successfully loaded {len(health_data)} fields from health_facility_report.json")
            
            # Remove metadata fields that shouldn't be used for DHIS filling
            metadata_fields = ['province_name', 'health_facility_name', 'month', 'year', 'zone', 'type']
            filtered_data = {k: v for k, v in health_data.items() if k not in metadata_fields}
            
            logger.info(f"🎭 FAKE OCR: Filtered out metadata fields. {len(filtered_data)} data fields ready for DHIS")
            
            return filtered_data
            
        except Exception as e:
            logger.error(f"🎭 FAKE OCR: Failed to load health facility data: {e}")
            return {
                "error": f"Failed to load health facility data: {str(e)}",
                "fake_ocr_status": "failed"
            }
    
    
    def _basic_pdf_extraction(self, pdf_path: str) -> Dict[str, Any]:
        """Basic PDF extraction without AI as fallback"""
        try:
            import pdfplumber
            
            extracted_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
            
            # Return basic structure with extracted text
            return {
                "raw_text": extracted_text,
                "extraction_method": "basic",
                "note": "Basic text extraction - AI processing unavailable"
            }
            
        except Exception as e:
            logger.error(f"Basic PDF extraction failed: {e}")
            return {
                "error": f"PDF extraction failed: {str(e)}",
                "extraction_method": "failed"
            }
    
    def _create_fake_comparison_result(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create fake comparison result for testing"""
        
        comparison_result = {
            "status": "completed",
            "method": "fake_ocr_simulation",
            "source_file": "health_facility_report.json",
            "total_fields_extracted": len(extracted_data),
            "processing_notes": [
                "🎭 FAKE OCR: No real PDF processing performed",
                "🎭 FAKE OCR: Data loaded directly from health_facility_report.json",
                "🎭 FAKE OCR: Ready for DHIS form filling",
                "🎭 FAKE OCR: This is for testing/development purposes only"
            ],
            "fake_ocr_status": "success",
            "data_ready_for_dhis": True
        }
        
        # Add field count details
        if extracted_data:
            non_zero_fields = sum(1 for v in extracted_data.values() if v and str(v) != "0")
            comparison_result["fields_with_data"] = non_zero_fields
            comparison_result["fields_empty_or_zero"] = len(extracted_data) - non_zero_fields
        
        return comparison_result
    
    
