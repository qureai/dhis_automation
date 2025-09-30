from django.db import models
import uuid

class ImageUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_image = models.ImageField(upload_to='uploads/original/')
    original_filename = models.CharField(max_length=255, blank=True)
    s3_url = models.URLField(max_length=500, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Session tracking for dual uploads and processing workflows
    session_id = models.CharField(max_length=255, blank=True, null=True)
    feature_type = models.CharField(
        max_length=20,
        choices=[
            ('register', 'Patient Register Processing'),
            ('pdf', 'PDF Document Processing'),
            ('single_image', 'Single Image Processing')
        ],
        default='single_image'
    )
    
    # Legacy fields for backward compatibility
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_diagnosis = models.DateField(null=True, blank=True)
    case_detection_options = models.CharField(max_length=50, blank=True)
    
    # New fields for extracted data
    extracted_data = models.JSONField(default=dict, blank=True, null=True)
    processed_data = models.JSONField(default=dict, blank=True)  # Legacy field
    
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
