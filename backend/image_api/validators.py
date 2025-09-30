"""
Input validation for image and PDF processing
"""
import os
from typing import List, Dict, Optional
from django.core.files.uploadedfile import UploadedFile


class FileValidator:
    """Validates uploaded files"""
    
    # Supported image formats
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
    
    # Supported document formats  
    SUPPORTED_PDF_FORMATS = {'.pdf'}
    
    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_PDF_SIZE = 100 * 1024 * 1024   # 100MB
    
    @classmethod
    def validate_image_file(cls, file: UploadedFile) -> Dict[str, any]:
        """
        Validate image file for register processing
        
        Returns:
            Dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        # Check if file exists
        if not file:
            errors.append("No file provided")
            return {'valid': False, 'errors': errors}
        
        # Check file extension
        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in cls.SUPPORTED_IMAGE_FORMATS:
            errors.append(f"Unsupported image format: {file_ext}. Supported formats: {', '.join(cls.SUPPORTED_IMAGE_FORMATS)}")
        
        # Check file size
        if file.size > cls.MAX_IMAGE_SIZE:
            errors.append(f"Image file too large: {file.size / 1024 / 1024:.1f}MB. Maximum size: {cls.MAX_IMAGE_SIZE / 1024 / 1024}MB")
        
        # Check minimum file size (avoid empty files)
        if file.size < 1024:  # 1KB minimum
            errors.append("Image file too small. Minimum size: 1KB")
        
        # Basic content-type check
        if hasattr(file, 'content_type') and file.content_type:
            if not file.content_type.startswith('image/'):
                errors.append(f"Invalid content type: {file.content_type}. Expected image/*")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'file_info': {
                'name': file.name,
                'size': file.size,
                'extension': file_ext,
                'content_type': getattr(file, 'content_type', 'unknown')
            }
        }
    
    @classmethod
    def validate_pdf_file(cls, file: UploadedFile) -> Dict[str, any]:
        """
        Validate PDF file for document processing
        
        Returns:
            Dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        # Check if file exists
        if not file:
            errors.append("No file provided")
            return {'valid': False, 'errors': errors}
        
        # Check file extension
        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in cls.SUPPORTED_PDF_FORMATS:
            errors.append(f"Unsupported document format: {file_ext}. Only PDF files are supported")
        
        # Check file size
        if file.size > cls.MAX_PDF_SIZE:
            errors.append(f"PDF file too large: {file.size / 1024 / 1024:.1f}MB. Maximum size: {cls.MAX_PDF_SIZE / 1024 / 1024}MB")
        
        # Check minimum file size
        if file.size < 1024:  # 1KB minimum
            errors.append("PDF file too small. Minimum size: 1KB")
        
        # Basic content-type check
        if hasattr(file, 'content_type') and file.content_type:
            if file.content_type != 'application/pdf':
                errors.append(f"Invalid content type: {file.content_type}. Expected application/pdf")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'file_info': {
                'name': file.name,
                'size': file.size,
                'extension': file_ext,
                'content_type': getattr(file, 'content_type', 'unknown')
            }
        }
    
    @classmethod
    def validate_dual_images(cls, image1: UploadedFile, image2: UploadedFile) -> Dict[str, any]:
        """
        Validate both images for register processing
        
        Returns:
            Dict with validation results for both images
        """
        result1 = cls.validate_image_file(image1)
        result2 = cls.validate_image_file(image2)
        
        combined_errors = []
        
        if not result1['valid']:
            combined_errors.extend([f"Image 1: {error}" for error in result1['errors']])
        
        if not result2['valid']:
            combined_errors.extend([f"Image 2: {error}" for error in result2['errors']])
        
        # Additional validation for dual images
        if result1['valid'] and result2['valid']:
            # Check if images are too similar in size (might be duplicates)
            size_diff = abs(image1.size - image2.size)
            if size_diff < 1024:  # Less than 1KB difference
                combined_errors.append("Images appear to be very similar in size. Please ensure you uploaded different sides of the register")
        
        return {
            'valid': len(combined_errors) == 0,
            'errors': combined_errors,
            'image1_validation': result1,
            'image2_validation': result2
        }


class RequestValidator:
    """Validates API request data"""
    
    @classmethod
    def validate_register_request(cls, request) -> Dict[str, any]:
        """Validate register processing request"""
        errors = []
        
        # Check required files
        if 'image1' not in request.FILES:
            errors.append("Missing required file: image1 (left side of register)")
        
        if 'image2' not in request.FILES:
            errors.append("Missing required file: image2 (right side of register)")
        
        # If files are present, validate them
        if 'image1' in request.FILES and 'image2' in request.FILES:
            validation_result = FileValidator.validate_dual_images(
                request.FILES['image1'], 
                request.FILES['image2']
            )
            if not validation_result['valid']:
                errors.extend(validation_result['errors'])
        
        # Validate optional parameters
        enable_dhis = request.POST.get('enable_dhis_integration', 'true')
        if enable_dhis.lower() not in ['true', 'false']:
            errors.append("Invalid value for enable_dhis_integration. Must be 'true' or 'false'")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @classmethod
    def validate_pdf_request(cls, request) -> Dict[str, any]:
        """Validate PDF processing request"""
        errors = []
        
        # Check required file
        if 'pdf_file' not in request.FILES:
            errors.append("Missing required file: pdf_file")
        
        # If file is present, validate it
        if 'pdf_file' in request.FILES:
            validation_result = FileValidator.validate_pdf_file(request.FILES['pdf_file'])
            if not validation_result['valid']:
                errors.extend(validation_result['errors'])
        
        # Validate optional parameters
        enable_dhis = request.POST.get('enable_dhis_integration', 'true')
        if enable_dhis.lower() not in ['true', 'false']:
            errors.append("Invalid value for enable_dhis_integration. Must be 'true' or 'false'")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class SystemValidator:
    """Validates system configuration and prerequisites"""
    
    @classmethod
    def validate_system_config(cls) -> Dict[str, any]:
        """Validate system configuration for processing"""
        issues = []
        warnings = []
        
        # Check environment variables
        required_env_vars = ['PORTKEY_API_KEY']
        optional_env_vars = ['DHIS_USERNAME', 'DHIS_PASSWORD', 'DHIS_URL']
        
        for var in required_env_vars:
            if not os.environ.get(var):
                issues.append(f"Missing required environment variable: {var}")
        
        for var in optional_env_vars:
            if not os.environ.get(var):
                warnings.append(f"Optional environment variable not set: {var} (DHIS2 integration will be disabled)")
        
        # Check DHIS integration status
        dhis_enabled = os.environ.get('ENABLE_DHIS_INTEGRATION', 'False') == 'True'
        if dhis_enabled:
            required_dhis_vars = ['DHIS_USERNAME', 'DHIS_PASSWORD', 'DHIS_URL']
            missing_dhis_vars = [var for var in required_dhis_vars if not os.environ.get(var)]
            
            if missing_dhis_vars:
                issues.append(f"DHIS2 integration enabled but missing required variables: {', '.join(missing_dhis_vars)}")
        
        # Check S3 configuration if enabled
        s3_enabled = os.environ.get('USE_S3_STORAGE', 'False') == 'True'
        if s3_enabled:
            s3_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_STORAGE_BUCKET_NAME']
            missing_s3_vars = [var for var in s3_vars if not os.environ.get(var)]
            
            if missing_s3_vars:
                issues.append(f"S3 storage enabled but missing required variables: {', '.join(missing_s3_vars)}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'config': {
                'dhis_integration_enabled': dhis_enabled,
                's3_storage_enabled': s3_enabled,
                'portkey_configured': bool(os.environ.get('PORTKEY_API_KEY'))
            }
        }