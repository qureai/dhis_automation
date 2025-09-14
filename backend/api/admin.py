from django.contrib import admin
from .models import PDFUpload, ProcessingLog


@admin.register(PDFUpload)
class PDFUploadAdmin(admin.ModelAdmin):
    list_display = ['id', 'file', 'status', 'uploaded_at', 'processed_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['file', 'error_message']
    readonly_fields = ['uploaded_at', 'processed_at']
    
    fieldsets = (
        (None, {
            'fields': ('file', 'status')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'processed_at')
        }),
        ('Processing Results', {
            'fields': ('extracted_data', 'comparison_result', 'dhis_result'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'upload', 'level', 'message_preview', 'timestamp']
    list_filter = ['level', 'timestamp']
    search_fields = ['message', 'upload__file']
    readonly_fields = ['timestamp']
    
    def message_preview(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message
    message_preview.short_description = "Message Preview"