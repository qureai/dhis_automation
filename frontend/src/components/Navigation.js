import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Chip
} from '@mui/material';
import {
  Assignment,
  CameraAlt,
  Home
} from '@mui/icons-material';

const Navigation = ({ currentView, onViewChange }) => {
  const navItems = [
    { id: 'home', label: 'Home', icon: <Home /> },
    { id: 'register', label: 'Patient Register', icon: <CameraAlt />, description: 'Process register images' },
    { id: 'pdf', label: 'PDF Automation', icon: <Assignment />, description: 'Automate PDF reports' }
  ];

  return (
    <AppBar position="static" sx={{ mb: 3 }}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          DHIS2 Medical Processing System
          <Chip 
            label="v2.0" 
            size="small" 
            sx={{ ml: 2, bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
          />
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          {navItems.map((item) => (
            <Button
              key={item.id}
              color="inherit"
              onClick={() => onViewChange(item.id)}
              startIcon={item.icon}
              variant={currentView === item.id ? 'outlined' : 'text'}
              sx={{ 
                color: 'white',
                borderColor: currentView === item.id ? 'rgba(255,255,255,0.5)' : 'transparent',
                '&:hover': {
                  bgcolor: 'rgba(255,255,255,0.1)'
                }
              }}
            >
              {item.label}
            </Button>
          ))}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navigation;