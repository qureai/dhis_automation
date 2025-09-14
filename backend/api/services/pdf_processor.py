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
        Process uploaded PDF using the EXACT logic from root llm.py
        Returns: (extracted_data, comparison_result)
        """
        if not self.llm_module or not self.portkey_client:
            raise Exception("llm.py module or Portkey client not available - check import from root folder")
        
        try:
            logger.info(f"Processing PDF using EXACT root llm.py logic: {pdf_path}")
            
            # Step 1: Use the exact same processing logic as root llm.py
            extracted_data = self._process_pdf_with_root_llm_logic(pdf_path)
            
            # Step 2: Create comparison result
            comparison_result = self._create_comparison_result(extracted_data)
            
            logger.info(f"PDF processing completed using root llm.py. Extracted {len(extracted_data)} fields")
            
            return extracted_data, comparison_result
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise Exception(f"PDF processing error: {str(e)}")
    
    def _process_pdf_with_root_llm_logic(self, pdf_path: str) -> Dict[str, Any]:
        """Use the EXACT same processing logic as the root llm.py file"""
        
        try:
            # Convert PDF to base64 (same as root llm.py)
            with open(pdf_path, 'rb') as f:
                base64_image_actual = base64.b64encode(f.read()).decode('utf-8')
            
            # Get reference PDF base64 (same as root llm.py)
            base64_image_digital = None
            if self.reference_pdf_path.exists():
                with open(self.reference_pdf_path, 'rb') as f:
                    base64_image_digital = base64.b64encode(f.read()).decode('utf-8')
            
            data_url_actual = f"data:application/pdf;base64,{base64_image_actual}"
            data_url_digital = f"data:application/pdf;base64,{base64_image_digital}" if base64_image_digital else None
            
            # Use the EXACT same processing loop from root llm.py
            master_result = {}
            tab_types = list(self.schema_mapping.keys())
            
            logger.info(f"Processing {len(tab_types)} schema types using root llm.py logic")
            
            for tab_type in tab_types:
                try:
                    logger.info(f"Processing schema type: {tab_type}")
                    
                    # Build messages array exactly like root llm.py
                    messages = [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant."
                        },
                        {
                            "role": "user",
                            "content": []
                        }
                    ]
                    
                    # Add images exactly like root llm.py
                    if data_url_digital:
                        messages[1]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": data_url_digital}
                        })
                    
                    messages[1]["content"].append({
                        "type": "image_url", 
                        "image_url": {"url": data_url_actual}
                    })
                    
                    # Add exact text prompt from root llm.py
                    messages[1]["content"].append({
                        "type": "text",
                        "text": f"""
                            There are 2 PDF files uploaded. One is master copy in digital format. The other is handwritten and scanned. 
                            From the handwritten document, extract information for {tab_type}
                                
                            The ouput should contain all the keys on the same level. (no nested keys just keys on the same level)
                            Your job is to map the layout of the two documents and compare the two documents and extract information from the handwritten document and return it in a json format.
                            For the keys that are not present in the handwritten document, return empty string.
                            
                            Some pages of the PDF can be oriented differently like landscape or portrait.
                            Strictly no markdown
                            """
                    })
                    
                    # Make API call exactly like root llm.py
                    completion = self.portkey_client.chat.completions.create(
                        messages=messages,
                        response_format=self.schema_mapping[tab_type],
                        model="gemini-2.5-flash"
                    )
                    
                    # Process response exactly like root llm.py
                    content = completion.choices[0].message.content
                    if isinstance(content, str):
                        try:
                            content_dict = json.loads(content)
                        except Exception:
                            content_dict = {}
                    elif isinstance(content, dict):
                        content_dict = content
                    else:
                        content_dict = {}
                    
                    # Merge content_dict into master_result (exact same as root llm.py)
                    master_result.update(content_dict)
                    logger.info(f"Updated {tab_type} - extracted {len(content_dict)} fields")
                    
                except Exception as e:
                    logger.warning(f"Failed to process schema type {tab_type}: {e}")
                    continue
            
            logger.info(f"Root llm.py processing completed: {len(master_result)} total fields extracted")
            return master_result
            
        except Exception as e:
            logger.error(f"Root llm.py processing failed: {e}")
            # Fallback to basic extraction
            return self._basic_pdf_extraction(pdf_path)
    
    
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
    
    def _create_comparison_result(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create comparison result following llm.py logic"""
        
        comparison_result = {
            "status": "completed",
            "method": "llm_comparison",
            "reference_pdf_found": self.reference_pdf_path.exists(),
            "schemas_processed": list(self.schema_mapping.keys()),
            "total_fields_extracted": len(extracted_data),
            "processing_notes": []
        }
        
        # Add processing details
        if self.reference_pdf_path.exists():
            comparison_result["processing_notes"].append("Reference PDF used for comparison mapping")
        else:
            comparison_result["processing_notes"].append("No reference PDF - processed single document only")
            
        if self.portkey_client:
            comparison_result["processing_notes"].append("AI processing with Portkey/Gemini")
        else:
            comparison_result["processing_notes"].append("Fallback to basic text extraction")
        
        return comparison_result
    
    
