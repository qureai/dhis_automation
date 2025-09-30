from rest_framework import serializers
from .models import ImageUpload

class ImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageUpload
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at', 's3_url', 'processed_at']

class ProcessedDataSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    date_of_birth = serializers.DateField(required=True)
    date_of_diagnosis = serializers.DateField(required=True)
    case_detection_options = serializers.CharField(required=True)