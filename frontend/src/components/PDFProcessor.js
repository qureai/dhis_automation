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
  StepLabel,
  Card,
  CardContent,
  Grid,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  FormControlLabel,
  Switch,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  Assignment,
  CloudUpload,
  HourglassEmpty,
  CheckCircle,
  ExpandMore
} from '@mui/icons-material';
import axios from 'axios';

const steps = [
  'Upload PDF Document',
  'Data Extraction',
  'DHIS2 Form Filling', 
  'Complete'
];

const PDFProcessor = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [enableDhis, setEnableDhis] = useState(true);
  const [sessionId, setSessionId] = useState(null);

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

  const handleProcess = async () => {
    if (!selectedFile) {
      setError('No PDF file selected');
      return;
    }

    setProcessing(true);
    setError('');
    setActiveStep(2);
    
    const formData = new FormData();
    formData.append('pdf', selectedFile);
    formData.append('enable_dhis_integration', enableDhis.toString());

    try {
      const response = await axios.post(
        'http://localhost:8005/api/process-pdf-and-fill-dhis',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 900000, // 15 minutes timeout for full processing
        }
      );

      setResult(response.data);
      setSessionId(response.data.session_id);
      setActiveStep(3);
      setProcessing(false);
    } catch (err) {
      console.error('Processing error:', err);
      setError(err.response?.data?.error || 'Processing failed');
      setProcessing(false);
      setActiveStep(1);
    }
  };

  const reset = () => {
    setActiveStep(0);
    setSelectedFile(null);
    setProcessing(false);
    setResult(null);
    setError('');
    setSessionId(null);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          PDF Document Automation
        </Typography>
        <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
          Upload PDF health facility reports for automated data extraction and DHIS2 form filling
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
            <Assignment sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Select PDF Document
            </Typography>
            
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
            
            <Box sx={{ mt: 4, bgcolor: 'grey.50', p: 3, borderRadius: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Supported Documents
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="Health Facility Monthly Reports" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Patient Register Summaries" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Medical Data Reports" />
                </ListItem>
              </List>
            </Box>
          </Box>
        )}

        {/* Step 1: File Selected */}
        {activeStep === 1 && selectedFile && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Selected Document
            </Typography>
            
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Grid container spacing={2} alignItems="center">
                  <Grid item>
                    <Assignment sx={{ fontSize: 48, color: 'primary.main' }} />
                  </Grid>
                  <Grid item xs>
                    <Typography variant="subtitle1">
                      <strong>{selectedFile.name}</strong>
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Type: {selectedFile.type}
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
            
            <Divider sx={{ my: 3 }} />
            
            <Box sx={{ mb: 3 }}>
              <FormControlLabel
                control={
                  <Switch 
                    checked={enableDhis} 
                    onChange={(e) => setEnableDhis(e.target.checked)}
                  />
                }
                label="Enable automatic DHIS2 form filling"
              />
              <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>
                When enabled, extracted data will be automatically submitted to DHIS2
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button
                variant="contained"
                onClick={handleProcess}
                disabled={processing}
                startIcon={<HourglassEmpty />}
                size="large"
              >
                {enableDhis ? 'Extract Data & Fill DHIS2' : 'Extract Data Only'}
              </Button>
              <Button variant="outlined" onClick={reset}>
                Change File
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 2: Processing */}
        {activeStep === 2 && processing && (
          <Box sx={{ textAlign: 'center' }}>
            <HourglassEmpty sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Processing PDF Document
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Current Status:</strong> Extracting data from PDF document...
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                This process may take 10-15 minutes to complete.
              </Typography>
              {enableDhis && (
                <Typography variant="body2" color="text.secondary">
                  After extraction, data will be automatically filled into DHIS2 forms.
                </Typography>
              )}
            </Paper>

            <LinearProgress sx={{ mb: 3 }} />
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Processing steps:
              </Typography>
              <Box component="ul" sx={{ textAlign: 'left', display: 'inline-block' }}>
                <Typography component="li" variant="body2">PDF text extraction</Typography>
                <Typography component="li" variant="body2">AI-powered data analysis</Typography>
                <Typography component="li" variant="body2">Field mapping and validation</Typography>
                {enableDhis && (
                  <Typography component="li" variant="body2">DHIS2 form automation</Typography>
                )}
              </Box>
            </Box>
            
            <Button variant="outlined" onClick={reset} disabled={processing}>
              Cancel
            </Button>
          </Box>
        )}

        {/* Step 3: Complete */}
        {activeStep === 3 && result && (
          <Box>
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <CheckCircle sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
              <Typography variant="h5" gutterBottom>
                Processing Complete!
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Session ID: {sessionId}
              </Typography>
            </Box>
            
            {/* Processing Results */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Extraction Results
                    </Typography>
                    <List>
                      <ListItem>
                        <ListItemText 
                          primary="Processing Status"
                          secondary={
                            <Chip 
                              label={result.processing_status}
                              color={result.processing_status === 'completed' ? 'success' : 'warning'}
                              size="small"
                            />
                          }
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText 
                          primary="Feature Type"
                          secondary="PDF Document Processing"
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText 
                          primary="Upload ID"
                          secondary={result.upload_id}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      DHIS2 Integration
                    </Typography>
                    {result.dhis2_submission ? (
                      <List>
                        <ListItem>
                          <ListItemText 
                            primary="Submission Status"
                            secondary={
                              <Chip 
                                label="Submitted Successfully"
                                color="success"
                                size="small"
                              />
                            }
                          />
                        </ListItem>
                      </List>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {enableDhis ? 'DHIS2 submission failed or not configured' : 'DHIS2 submission was disabled'}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Extracted Data */}
            {result.extracted_data && Object.keys(result.extracted_data).length > 0 && (
              <Accordion sx={{ mb: 3 }}>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">
                    Extracted Data ({Object.keys(result.extracted_data).length} fields)
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Card sx={{ maxHeight: 400, overflow: 'auto' }}>
                    <CardContent>
                      <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(result.extracted_data, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                </AccordionDetails>
              </Accordion>
            )}

            {/* DHIS2 Results */}
            {result.dhis2_submission && (
              <Accordion sx={{ mb: 3 }}>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">
                    DHIS2 Submission Details
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Card sx={{ maxHeight: 400, overflow: 'auto' }}>
                    <CardContent>
                      <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(result.dhis2_submission, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                </AccordionDetails>
              </Accordion>
            )}

            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Button variant="contained" onClick={reset} size="large">
                Process Another PDF
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default PDFProcessor;