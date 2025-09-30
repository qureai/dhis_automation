# DHIS Jupyter Notebooks

This directory contains Jupyter notebooks for data analysis and Django interaction.

## Getting Started

1. Start the notebook service:
   ```bash
   ./start.sh notebook
   ```

2. Access Jupyter at http://localhost:8888
   - Password: `Qure@123`

3. Open `dhis_demo.ipynb` to see examples of:
   - Django model queries
   - Data analysis with pandas
   - LLM service testing
   - Export functionality

## Django Integration

The notebook environment has full access to Django models and utilities. Django is automatically configured when you run:

```python
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'image_processor.settings')
django.setup()
```

## Available Models

- `ImageUpload`: Main model for uploaded images and extracted data
- `LLMService`: Service for medical information extraction

## Notes

- All notebooks except `dhis_demo.ipynb` are git-ignored
- CSV exports and other generated files are also ignored
- The notebook runs in the same Docker network as the backend