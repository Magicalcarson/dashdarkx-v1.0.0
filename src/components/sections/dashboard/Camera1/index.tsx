import { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import VideocamIcon from '@mui/icons-material/Videocam';
import VideocamOffIcon from '@mui/icons-material/VideocamOff';
import Chip from '@mui/material/Chip';
import { API_ENDPOINTS } from 'config/api';

const RevenueByCustomer = () => {
  // เช็คสถานะเซิร์ฟเวอร์
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      // ลองยิงไปเช็คว่า Server Python เปิดอยู่ไหม
      fetch(API_ENDPOINTS.data)
        .then(() => setIsOnline(true))
        .catch(() => setIsOnline(false));
    }, 2000); // เช็คทุก 2 วิ

    return () => clearInterval(interval);
  }, []);

  return (
    <Paper sx={{ p: 3, height: { xs: 400, md: 630 }, display: 'flex', flexDirection: 'column' }}>
      
      {/* --- Header --- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Stack direction="row" spacing={1} alignItems="center">
          <VideocamIcon sx={{ color: '#00d4ff' }} />
          <Typography variant="h6" fontWeight={600} color="text.primary">
            Camera 1 (Working View)
          </Typography>
        </Stack>
        
        <Chip 
          icon={isOnline ? <VideocamIcon /> : <VideocamOffIcon />} 
          label={isOnline ? "ONLINE" : "OFFLINE"} 
          color={isOnline ? "success" : "error"} 
          size="small"
          variant="outlined"
        />
      </Stack>

      {/* --- Video Area --- */}
      <Box 
        sx={{ 
          flexGrow: 1, 
          bgcolor: 'black', 
          borderRadius: 2, 
          border: '1px solid #333',
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          overflow: 'hidden',
          position: 'relative'
        }}
      >
        {isOnline ? (
          // ดึงภาพจาก Python (Webcam)
          <img
            src={API_ENDPOINTS.videoFeed}
            alt="Webcam Stream"
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        ) : (
          // ถ้าต่อไม่ได้
          <Stack alignItems="center" spacing={1} color="text.secondary">
            <VideocamOffIcon sx={{ fontSize: 60, opacity: 0.5 }} />
            <Typography variant="body2">No Signal from Server</Typography>
          </Stack>
        )}
      </Box>

      {/* --- Footer Info --- */}
      <Stack direction="row" justifyContent="space-between" mt={2}>
        <Typography variant="caption" color="text.secondary">Source: Local Webcam (ID 0)</Typography>
        <Typography variant="caption" color="text.disabled">1280 x 720</Typography>
      </Stack>

    </Paper>
  );
};

export default RevenueByCustomer;