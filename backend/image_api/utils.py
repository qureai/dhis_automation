import boto3
import os
from django.conf import settings
from portkey_ai import Portkey
import json
import base64
import mimetypes
from datetime import datetime
from typing import List, Dict, Any

class S3Handler:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def upload_file(self, file, key):
        try:
            self.s3_client.upload_fileobj(file, self.bucket_name, key)
            url = f"https://{self.bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{key}"
            return url
        except Exception as e:
            print(f"Error uploading to S3: {str(e)}")
            return None

class LLMProcessor:
    def __init__(self):
        if settings.PORTKEY_API_KEY and settings.PORTKEY_VIRTUAL_KEY:
            try:
                # Use the exact working implementation provided by user
                from portkey_ai import Portkey
                
                # Initialize Portkey with just api_key and virtual_key
                self.portkey = Portkey(
                    api_key=settings.PORTKEY_API_KEY,
                    virtual_key=settings.PORTKEY_VIRTUAL_KEY
                )
                print(f"Portkey initialized successfully with virtual key: {settings.PORTKEY_VIRTUAL_KEY[:10]}...")
            except Exception as e:
                print(f"Error initializing Portkey: {str(e)}")
                self.portkey = None
                print("Warning: Could not initialize Portkey")
        else:
            self.portkey = None
            if not settings.PORTKEY_API_KEY:
                print("Warning: PORTKEY_API_KEY not configured")
            if not settings.PORTKEY_VIRTUAL_KEY:
                print("Warning: PORTKEY_VIRTUAL_KEY not configured")
    
    def process_horizontal_table_images(self, image1_path: str, image2_path: str) -> List[Dict[str, Any]]:
        """
        Process two images that represent sides of a horizontal table containing multiple patient records
        """
        if not self.portkey:
            # Return demo data if Portkey is not configured
            return [{
                "patient_number": 1,
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2000-01-01",
                "date_of_diagnosis": "2025-07-23",
                "case_detection_options": "passive",
                "gender": "male",
                "index_case": False,
                "temperature": 98.6,
                "weight": 70.0,
                "pregnancy_status": False,
                "tested_by": "Dr. Smith",
                "in_out_patient": "outpatient",
                "clinical_status": "stable",
                "malaria_medication": "none",
                "additional_medications": "none",
                "referred_by": False,
                "travelled_12m": False,
                "complete_event": True,
                "additional_info": "Demo data - Configure Portkey API to process real images"
            }]
        
        try:
            # Read and encode both images
            with open(image1_path, 'rb') as img1:
                image1_bytes = img1.read()
            encoded_string1 = base64.b64encode(image1_bytes).decode('utf-8')
            mime_type1, _ = mimetypes.guess_type(image1_path)
            if mime_type1 is None:
                mime_type1 = "application/octet-stream"
            image1_url = f"data:{mime_type1};base64,{encoded_string1}"
            
            with open(image2_path, 'rb') as img2:
                image2_bytes = img2.read()
            encoded_string2 = base64.b64encode(image2_bytes).decode('utf-8')
            mime_type2, _ = mimetypes.guess_type(image2_path)
            if mime_type2 is None:
                mime_type2 = "application/octet-stream"
            image2_url = f"data:{mime_type2};base64,{encoded_string2}"
            
            # Enhanced prompt for horizontal table reading
            system_prompt = """You are an expert medical data extraction system specialized in reading horizontal tables from medical documents.
            
IMPORTANT CONTEXT:
- You are viewing TWO images that together form ONE LONG HORIZONTAL TABLE
- Image 1 shows the LEFT side of the table
- Image 2 shows the RIGHT side of the table
- The table contains MULTIPLE PATIENT RECORDS (rows)
- Each row represents a different patient
- The columns span across both images horizontally

YOUR TASK:
1. Mentally align the two images side by side to reconstruct the complete table
2. Read each row completely by following it from Image 1 to Image 2
3. Extract data for ALL patients (all rows) found in the table
4. Return an array of patient records in the specified JSON format

READING STRATEGY:
- Start with the leftmost columns in Image 1
- Continue to the rightmost columns in Image 2
- Maintain row alignment between the two images
- Each patient's data spans across both images
- options for case_detection_options are: reactive, active, passive

Be precise with dates, numbers, and ensure all extracted information is accurate.
If a field is not visible or unclear, use null or appropriate default values."""

            user_prompt = """Please extract ALL patient records from this horizontal table that spans across these two images.

REMEMBER:
- These two images show the LEFT side (Image 1) and RIGHT side (Image 2) of the SAME horizontal table
- Read each row from left to right across BOTH images
- Extract data for EVERY patient row you can see
- Return an array of patient objects
- options for case_detection_options are: reactive, active, passive

Extract and return the data in this exact JSON structure:"""
            
            # Using Portkey's chat completions API with JSON schema for array response
            # Use openai/gpt-4.1 or similar model that supports vision
            completion = self.portkey.chat.completions.create(
                model=settings.PORTKEY_VISION_MODEL if hasattr(settings, 'PORTKEY_VISION_MODEL') else "openai/gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image1_url,
                                    "detail": "high"
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image2_url,
                                    "detail": "high"
                                },
                            },
                        ],
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "patient_records",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "patients": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "patient_number": {"type": "integer"},
                                            "first_name": {"type": "string"},
                                            "last_name": {"type": "string"},
                                            "date_of_birth": {"type": "string"},
                                            "date_of_diagnosis": {"type": "string"},
                                            "case_detection_options": {"type": "string"},
                                            "gender": {"type": "string"},
                                            "index_case": {"type": "boolean"},
                                            "temperature": {"type": "number"},
                                            "weight": {"type": "number"},
                                            "pregnancy_status": {"type": "boolean"},
                                            "tested_by": {"type": "string"},
                                            "in_out_patient": {"type": "string"},
                                            "clinical_status": {"type": "string"},
                                            "malaria_medication": {"type": "string"},
                                            "additional_medications": {"type": "string"},
                                            "referred_by": {"type": "boolean"},
                                            "travelled_12m": {"type": "boolean"},
                                            "complete_event": {"type": "boolean"}
                                        },
                                        "required": [
                                            "patient_number", "first_name", "last_name", "date_of_birth",
                                            "date_of_diagnosis", "case_detection_options", "gender",
                                            "index_case", "temperature", "weight", "pregnancy_status",
                                            "tested_by", "in_out_patient", "clinical_status", 
                                            "malaria_medication", "additional_medications", "referred_by",
                                            "travelled_12m", "complete_event"
                                        ],
                                        "additionalProperties": False
                                    }
                                },
                                "total_patients": {"type": "integer"},
                                "extraction_notes": {"type": "string"}
                            },
                            "required": ["patients", "total_patients", "extraction_notes"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                },
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=4000,  # Increased for multiple records
            )
            
            # Parse the response using dictionary notation like the working example
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Completion: {completion}")
            result = json.loads(completion['choices'][0]['message']['content'])
            
            # Extract the patients array
            patients = result.get('patients', [])
            
            # Post-process each patient record
            for patient in patients:
                for key, value in patient.items():
                    if value == "" or value == "Not Found" or value == "N/A":
                        if key in ["index_case", "pregnancy_status", "referred_by", "travelled_12m", "complete_event"]:
                            patient[key] = False
                        elif key in ["temperature", "weight"]:
                            patient[key] = 0.0
                        elif key == "patient_number":
                            patient[key] = 0
                        else:
                            patient[key] = None
            
            # Add metadata
            for patient in patients:
                patient["extraction_method"] = "horizontal_table"
                patient["processed_at"] = datetime.now().isoformat()
            
            return patients
            
        except Exception as e:
            print(f"Error processing horizontal table with Portkey LLM: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return demo data on error
            return [{
                "patient_number": 1,
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2000-01-01",
                "date_of_diagnosis": str(datetime.now().date()),
                "case_detection_options": "passive",
                "gender": "unknown",
                "index_case": False,
                "temperature": 98.6,
                "weight": 70.0,
                "pregnancy_status": False,
                "tested_by": "Unknown",
                "in_out_patient": "outpatient",
                "clinical_status": "stable",
                "malaria_medication": "none",
                "additional_medications": "none",
                "referred_by": False,
                "travelled_12m": False,
                "complete_event": True,
                "error": f"Error during processing: {str(e)}"
            }]
    
    def process_image(self, image_path):
        """
        Process a single image (legacy support)
        """
        if not self.portkey:
            return {
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2000-01-01",
                "date_of_diagnosis": "2025-07-23",
                "case_detection_options": "passive",
                "additional_info": "Demo data - Configure Portkey API"
            }
        
        try:
            # Read and encode the image
            with open(image_path, 'rb') as img:
                image_bytes = img.read()
            
            encoded_string = base64.b64encode(image_bytes).decode('utf-8')
            
            # Guess MIME type
            mime_type, _ = mimetypes.guess_type(image_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            
            # Create data URL
            image_url = f"data:{mime_type};base64,{encoded_string}"
            
            # Process single image
            completion = self.portkey.chat.completions.create(
                model=settings.PORTKEY_VISION_MODEL if hasattr(settings, 'PORTKEY_VISION_MODEL') else "openai/gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract medical information from the image."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract patient information from this medical document."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                },
                            },
                        ],
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "patient_info",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                                "date_of_birth": {"type": "string"},
                                "date_of_diagnosis": {"type": "string"},
                                "case_detection_options": {"type": "string"}
                            },
                            "required": ["first_name", "last_name", "date_of_birth", "date_of_diagnosis", "case_detection_options"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                },
                temperature=0.1,
                max_tokens=1000,
            )
            
            return json.loads(completion['choices'][0]['message']['content'])
            
        except Exception as e:
            print(f"Error processing with Portkey LLM: {str(e)}")
            return {
                "first_name": "Unknown",
                "last_name": "Unknown",
                "date_of_birth": "Unknown",
                "date_of_diagnosis": "Unknown",
                "case_detection_options": "Unknown",
                "error": str(e)
            }

class LLMService:
    """Alias for LLMProcessor for backward compatibility"""
    def __init__(self):
        self.processor = LLMProcessor()
    
    def extract_medical_info(self, image_path):
        """Extract medical information from a single image"""
        return self.processor.process_image(image_path)
    
    def extract_from_horizontal_table(self, image1_path, image2_path):
        """Extract multiple patient records from horizontal table spanning two images"""
        return self.processor.process_horizontal_table_images(image1_path, image2_path)
    
    def extract_medical_info_from_text(self, text):
        """Extract medical information from text"""
        if not self.processor.portkey:
            return {
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2000-01-01",
                "date_of_diagnosis": str(datetime.now().date()),
                "case_detection_options": "passive",
                "additional_info": "Demo data - Configure Portkey API"
            }
        
        try:
            completion = self.processor.portkey.chat.completions.create(
                model=settings.PORTKEY_MODEL if hasattr(settings, 'PORTKEY_MODEL') else "openai/gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract medical information from the text and return as JSON."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "patient_info",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                                "date_of_birth": {"type": "string"},
                                "date_of_diagnosis": {"type": "string"},
                                "case_detection_options": {"type": "string"}
                            },
                            "required": ["first_name", "last_name", "date_of_birth", "date_of_diagnosis", "case_detection_options"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                },
                temperature=0.1,
                max_tokens=500,
            )
            
            return json.loads(completion['choices'][0]['message']['content'])
            
        except Exception as e:
            print(f"Error processing text with Portkey: {str(e)}")
            return {
                "first_name": "Unknown",
                "last_name": "Unknown",
                "date_of_birth": "Unknown",
                "date_of_diagnosis": "Unknown",
                "case_detection_options": "Unknown",
                "error": str(e)
            }