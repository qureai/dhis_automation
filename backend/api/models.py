from django.db import models
from django.utils import timezone


class PDFUpload(models.Model):
    """Model to track PDF uploads and processing status"""
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('compared', 'Compared'),
        ('dhis_processing', 'DHIS Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    file = models.FileField(upload_to='pdfs/', max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    uploaded_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Processing results
    extracted_data = models.JSONField(null=True, blank=True)
    comparison_result = models.JSONField(null=True, blank=True)
    dhis_result = models.JSONField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"PDF Upload {self.id} - {self.status}"


class ProcessingLog(models.Model):
    """Log processing steps for debugging"""
    
    LOG_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'), 
        ('error', 'Error'),
    ]
    
    upload = models.ForeignKey(PDFUpload, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=LOG_LEVELS)
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.level.upper()}: {self.message[:50]}"