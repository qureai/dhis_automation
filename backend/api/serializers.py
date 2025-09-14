from rest_framework import serializers
from .models import PDFUpload, ProcessingLog


class PDFUploadSerializer(serializers.ModelSerializer):
    """Serializer for PDF upload"""
    
    class Meta:
        model = PDFUpload
        fields = ['id', 'file', 'status', 'uploaded_at', 'processed_at', 
                 'extracted_data', 'comparison_result', 'dhis_result', 'error_message']
        read_only_fields = ['id', 'status', 'uploaded_at', 'processed_at', 
                           'extracted_data', 'comparison_result', 'dhis_result', 'error_message']


class ProcessingLogSerializer(serializers.ModelSerializer):
    """Serializer for processing logs"""
    
    class Meta:
        model = ProcessingLog
        fields = ['id', 'level', 'message', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class PDFProcessResponseSerializer(serializers.Serializer):
    """Serializer for PDF processing response"""
    
    id = serializers.IntegerField()
    status = serializers.CharField()
    extracted_data = serializers.JSONField()
    comparison_result = serializers.JSONField()
    message = serializers.CharField()


class DHISProcessResponseSerializer(serializers.Serializer):
    """Serializer for DHIS2 processing response"""
    
    status = serializers.CharField()
    fields_filled = serializers.IntegerField()
    success_rate = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField()