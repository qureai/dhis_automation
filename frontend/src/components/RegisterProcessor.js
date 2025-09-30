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
  Switch
} from '@mui/material';
import {
  CameraAlt,
  CloudUpload,
  HourglassEmpty,
  CheckCircle,
  Error as ErrorIcon
} from '@mui/icons-material';
import axios from 'axios';

const steps = [
  'Upload Register Images',
  'Processing & Extraction',
  'DHIS2 Submission',
  'Complete'
];

const RegisterProcessor = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [leftImage, setLeftImage] = useState(null);
  const [rightImage, setRightImage] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [enableDhis, setEnableDhis] = useState(true);
  const [sessionId, setSessionId] = useState(null);

  const handleImageSelect = (side, event) => {
    const file = event.target.files[0];
    if (file && file.type.startsWith('image/')) {
      if (side === 'left') {
        setLeftImage(file);
      } else {
        setRightImage(file);
      }
      setError('');
      
      // Move to next step if both images selected
      if ((side === 'left' && rightImage) || (side === 'right' && leftImage)) {
        setActiveStep(1);
      }
    } else {
      setError(`Please select a valid image file for ${side} side`);
    }
  };

  const handleProcess = async () => {
    if (!leftImage || !rightImage) {
      setError('Both register images are required');
      return;
    }

    setProcessing(true);
    setError('');
    setActiveStep(2);
    
    const formData = new FormData();
    formData.append('image1', leftImage);
    formData.append('image2', rightImage);
    formData.append('enable_dhis_integration', enableDhis.toString());

    try {
      const response = await axios.post(
        'http://localhost:8005/api/images/process-register/', 
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 600000, // 10 minutes timeout
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
    setLeftImage(null);
    setRightImage(null);
    setProcessing(false);
    setResult(null);
    setError('');
    setSessionId(null);
  };

  const ImageUploadCard = ({ side, image, onSelect }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>
          {side === 'left' ? 'Left Side' : 'Right Side'}
        </Typography>
        
        {image ? (
          <Box>
            <img 
              src={URL.createObjectURL(image)} 
              alt={`${side} side preview`}
              style={{ 
                maxWidth: '100%', 
                maxHeight: '200px', 
                objectFit: 'contain',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
            />
            <Typography variant="body2" sx={{ mt: 1 }}>
              {image.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {(image.size / 1024 / 1024).toFixed(2)} MB
            </Typography>
          </Box>
        ) : (
          <Box sx={{ py: 4 }}>
            <CameraAlt sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="body2" color="text.secondary">
              Upload {side} side of register
            </Typography>
          </Box>
        )}
        
        <input
          accept="image/*"
          style={{ display: 'none' }}
          id={`${side}-image-upload`}
          type="file"
          onChange={(e) => onSelect(side, e)}
        />
        <label htmlFor={`${side}-image-upload`}>
          <Button
            variant={image ? 'outlined' : 'contained'}
            component="span"
            startIcon={<CloudUpload />}
            sx={{ mt: 2 }}
          >
            {image ? 'Change Image' : 'Select Image'}
          </Button>
        </label>
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          Patient Register Processing
        </Typography>
        <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
          Upload both sides of patient register images to extract patient records
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

        {/* Step 0 & 1: Image Upload */}
        {(activeStep === 0 || activeStep === 1) && (
          <Box>
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={6}>
                <ImageUploadCard 
                  side="left" 
                  image={leftImage} 
                  onSelect={handleImageSelect}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <ImageUploadCard 
                  side="right" 
                  image={rightImage} 
                  onSelect={handleImageSelect}
                />
              </Grid>
            </Grid>

            {leftImage && rightImage && (
              <Box>
                <Divider sx={{ my: 3 }} />
                
                <Box sx={{ mb: 3 }}>
                  <FormControlLabel
                    control={
                      <Switch 
                        checked={enableDhis} 
                        onChange={(e) => setEnableDhis(e.target.checked)}
                      />
                    }
                    label="Enable automatic DHIS2 submission"
                  />
                </Box>

                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
                  <Button
                    variant="contained"
                    onClick={handleProcess}
                    disabled={processing}
                    startIcon={<HourglassEmpty />}
                    size="large"
                  >
                    Process Register Images
                  </Button>
                  <Button variant="outlined" onClick={reset}>
                    Start Over
                  </Button>
                </Box>
              </Box>
            )}
          </Box>
        )}

        {/* Step 2: Processing */}
        {activeStep === 2 && processing && (
          <Box sx={{ textAlign: 'center' }}>
            <HourglassEmpty sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Processing Register Images
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Current Status:</strong> Extracting patient records from register images...
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                This process may take 5-10 minutes to complete.
              </Typography>
              {enableDhis && (
                <Typography variant="body2" color="text.secondary">
                  After extraction, data will be automatically submitted to DHIS2.
                </Typography>
              )}
            </Paper>

            <LinearProgress sx={{ mb: 3 }} />
            
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
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Extraction Results
                    </Typography>
                    <List>
                      <ListItem>
                        <ListItemText 
                          primary="Total Patients Extracted"
                          secondary={
                            <Chip 
                              label={result.total_patients_extracted || 0}
                              color="primary"
                              size="small"
                            />
                          }
                        />
                      </ListItem>
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
                          secondary="Patient Register Processing"
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

            {/* Patient Records */}
            {result.patient_records && result.patient_records.length > 0 && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Extracted Patient Records ({result.patient_records.length})
                </Typography>
                <Card sx={{ maxHeight: 400, overflow: 'auto' }}>
                  <CardContent>
                    <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(result.patient_records, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              </Box>
            )}

            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Button variant="contained" onClick={reset} size="large">
                Process Another Register
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default RegisterProcessor;