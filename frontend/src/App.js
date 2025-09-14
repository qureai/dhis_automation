import React, { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
  LinearProgress,
  Alert,
  Stepper,
  Step,
  StepLabel
} from '@mui/material';
import {
  CloudUpload,
  Assignment,
  CheckCircle
} from '@mui/icons-material';
import axios from 'axios';

const steps = [
  'Upload PDF',
  'Processing',
  'Complete'
];

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setError('');
      setActiveStep(1);
    } else {
      setError('Please select a valid PDF file');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('No file selected');
      return;
    }

    setUploading(true);
    setProcessing(true);
    setError('');
    setActiveStep(2); // Move to processing step
    
    const formData = new FormData();
    formData.append('pdf', selectedFile);

    try {
      const response = await axios.post('http://localhost:8005/api/process-pdf-and-fill-dhis', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 900000, // 15 minutes timeout for full processing
      });

      setResult(response.data);
      setActiveStep(3); // Move to complete step
      setUploading(false);
      setProcessing(false);
    } catch (err) {
      setError(err.response?.data?.error || 'Processing failed');
      setUploading(false);
      setProcessing(false);
      setActiveStep(1); // Reset to upload step on error
    }
  };

  const reset = () => {
    setActiveStep(0);
    setSelectedFile(null);
    setUploading(false);
    setProcessing(false);
    setResult(null);
    setError('');
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          DHIS2 PDF Automation
        </Typography>
        <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
          Upload a PDF report to automatically extract data and fill DHIS2 forms
        </Typography>

        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Step 0: File Selection */}
        {activeStep === 0 && (
          <Box sx={{ textAlign: 'center' }}>
            <input
              accept="application/pdf"
              style={{ display: 'none' }}
              id="pdf-upload"
              type="file"
              onChange={handleFileSelect}
            />
            <label htmlFor="pdf-upload">
              <Button
                variant="contained"
                component="span"
                startIcon={<CloudUpload />}
                size="large"
                sx={{ mb: 2 }}
              >
                Select PDF File
              </Button>
            </label>
            <Typography variant="body2" color="text.secondary">
              Upload a health facility report PDF for processing
            </Typography>
          </Box>
        )}

        {/* Step 1: File Selected */}
        {activeStep === 1 && selectedFile && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Selected File
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
              <Typography><strong>Name:</strong> {selectedFile.name}</Typography>
              <Typography><strong>Size:</strong> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</Typography>
              <Typography><strong>Type:</strong> {selectedFile.type}</Typography>
            </Paper>
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                onClick={handleUpload}
                disabled={uploading || processing}
                startIcon={<Assignment />}
                size="large"
              >
                {uploading || processing ? 'Processing...' : 'Process PDF & Fill DHIS2'}
              </Button>
              <Button variant="outlined" onClick={reset}>
                Cancel
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 2: Processing */}
        {activeStep === 2 && (uploading || processing) && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Processing PDF and Filling DHIS2 Form
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Current Status:</strong> {uploading ? 'Extracting data from PDF...' : 'Filling DHIS2 form...'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This process may take 10-15 minutes to complete.
              </Typography>
            </Paper>

            <LinearProgress sx={{ mb: 2 }} />
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button variant="outlined" onClick={reset} disabled={uploading || processing}>
                Cancel
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 3: Complete */}
        {activeStep === 3 && result && (
          <Box sx={{ textAlign: 'center' }}>
            <CheckCircle sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
            <Typography variant="h5" gutterBottom>
              Process Complete!
            </Typography>
            
            {/* PDF Processing Results */}
            {result.pdf_processing && (
              <Paper variant="outlined" sx={{ p: 2, mb: 2, textAlign: 'left' }}>
                <Typography variant="subtitle2" gutterBottom>
                  PDF Processing Results
                </Typography>
                <Typography variant="body2">
                  <strong>Fields Extracted:</strong> {result.pdf_processing.fields_extracted || 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Status:</strong> {result.pdf_processing.comparison_result?.status || 'Completed'}
                </Typography>
              </Paper>
            )}

            {/* DHIS2 Processing Results */}
            {result.dhis_processing && (
              <Paper variant="outlined" sx={{ p: 2, mb: 3, textAlign: 'left' }}>
                <Typography variant="subtitle2" gutterBottom>
                  DHIS2 Form Filling Results
                </Typography>
                <Typography variant="body2">
                  <strong>Fields Filled:</strong> {result.dhis_processing.fields_filled || 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Total Fields:</strong> {result.dhis_processing.total_fields || 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Success Rate:</strong> {result.dhis_processing.success_rate || '0%'}
                </Typography>
                <Typography variant="body2">
                  <strong>Form Validation:</strong> {result.dhis_processing.validation_passed ? '✅ Passed' : '⚠️ Issues'}
                </Typography>
                <Typography variant="body2">
                  <strong>Status:</strong> {result.dhis_processing.status || 'Completed'}
                </Typography>
              </Paper>
            )}

            <Button variant="contained" onClick={reset} size="large">
              Process Another PDF
            </Button>
          </Box>
        )}
      </Paper>
    </Container>
  );
}

export default App;