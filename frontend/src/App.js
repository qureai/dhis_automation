import React, { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box } from '@mui/material';

import Navigation from './components/Navigation';
import HomePage from './components/HomePage';
import RegisterProcessor from './components/RegisterProcessor';
import PDFProcessor from './components/PDFProcessor';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#2e7d32',
    },
  },
  typography: {
    fontFamily: [
      'Roboto',
      'Arial',
      'sans-serif'
    ].join(','),
  },
});

function App() {
  const [currentView, setCurrentView] = useState('home');

  const handleViewChange = (view) => {
    setCurrentView(view);
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case 'register':
        return <RegisterProcessor />;
      case 'pdf':
        return <PDFProcessor />;
      case 'home':
      default:
        return <HomePage onViewChange={handleViewChange} />;
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'grey.100' }}>
        <Navigation 
          currentView={currentView} 
          onViewChange={handleViewChange}
        />
        {renderCurrentView()}
      </Box>
    </ThemeProvider>
  );
}

export default App;