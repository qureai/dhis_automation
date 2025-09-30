import React from 'react';
import {
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Box,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText
} from '@mui/material';
import {
  Assignment,
  CameraAlt,
  CheckCircle,
  CloudUpload,
  Speed,
  Security
} from '@mui/icons-material';

const HomePage = ({ onViewChange }) => {
  const features = [
    {
      id: 'register',
      title: 'Patient Register Processing',
      description: 'Upload both sides of patient register images to extract multiple patient records',
      icon: <CameraAlt sx={{ fontSize: 48, color: 'primary.main' }} />,
      features: [
        'Dual image upload support',
        'OCR and AI data extraction', 
        'Automatic DHIS2 submission',
        'Multi-patient processing'
      ],
      buttonText: 'Process Register Images',
      color: '#1976d2'
    },
    {
      id: 'pdf',
      title: 'PDF Document Automation',
      description: 'Upload PDF health facility reports for automated data extraction and DHIS2 form filling',
      icon: <Assignment sx={{ fontSize: 48, color: 'success.main' }} />,
      features: [
        'PDF text extraction',
        'Health facility data mapping',
        'Automated form filling',
        'Validation and submission'
      ],
      buttonText: 'Process PDF Documents',
      color: '#2e7d32'
    }
  ];

  const systemFeatures = [
    { icon: <Speed />, text: 'Fast processing with AI-powered extraction' },
    { icon: <Security />, text: 'Secure data handling and DHIS2 integration' },
    { icon: <CloudUpload />, text: 'Cloud storage support (S3)' },
    { icon: <CheckCircle />, text: 'Automatic validation and error handling' }
  ];

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ textAlign: 'center', mb: 6 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          DHIS2 Medical Processing System
        </Typography>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
          Automated data extraction and form filling for healthcare systems
        </Typography>
        <Chip 
          label="Production Ready" 
          color="success" 
          variant="outlined" 
          sx={{ mr: 1 }}
        />
        <Chip 
          label="AI Powered" 
          color="primary" 
          variant="outlined" 
        />
      </Box>

      {/* Main Features */}
      <Grid container spacing={4} sx={{ mb: 6 }}>
        {features.map((feature) => (
          <Grid item xs={12} md={6} key={feature.id}>
            <Card 
              sx={{ 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4
                }
              }}
            >
              <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
                <Box sx={{ mb: 2 }}>
                  {feature.icon}
                </Box>
                <Typography variant="h5" component="h2" gutterBottom>
                  {feature.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {feature.description}
                </Typography>
                
                <List dense>
                  {feature.features.map((item, index) => (
                    <ListItem key={index} sx={{ py: 0 }}>
                      <ListItemIcon sx={{ minWidth: 32 }}>
                        <CheckCircle sx={{ fontSize: 16, color: feature.color }} />
                      </ListItemIcon>
                      <ListItemText 
                        primary={item} 
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
              
              <CardActions sx={{ justifyContent: 'center', p: 2 }}>
                <Button 
                  variant="contained" 
                  size="large"
                  onClick={() => onViewChange(feature.id)}
                  sx={{ 
                    bgcolor: feature.color,
                    '&:hover': {
                      bgcolor: feature.color,
                      filter: 'brightness(0.9)'
                    }
                  }}
                >
                  {feature.buttonText}
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* System Features */}
      <Box sx={{ bgcolor: 'grey.50', borderRadius: 2, p: 4 }}>
        <Typography variant="h5" align="center" gutterBottom>
          System Features
        </Typography>
        <Grid container spacing={3}>
          {systemFeatures.map((item, index) => (
            <Grid item xs={12} sm={6} md={3} key={index}>
              <Box sx={{ textAlign: 'center' }}>
                <Box sx={{ mb: 1 }}>
                  {React.cloneElement(item.icon, { 
                    sx: { fontSize: 32, color: 'primary.main' } 
                  })}
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {item.text}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Getting Started */}
      <Box sx={{ mt: 6, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>
          Getting Started
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Choose a processing type above to begin. Both features support automatic DHIS2 integration
          and provide detailed processing results.
        </Typography>
      </Box>
    </Container>
  );
};

export default HomePage;