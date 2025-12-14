import { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import VideocamIcon from '@mui/icons-material/Videocam';
import VideocamOffIcon from '@mui/icons-material/VideocamOff';
import Chip from '@mui/material/Chip';

const CompletedTask = () => {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      fetch('http://192.168.1.50:5000/data')
        .then(() => setIsOnline(true))
        .catch(() => setIsOnline(false));
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <Paper sx={{ p: 3, height: 550, display: 'flex', flexDirection: 'column' }}>
      
      {/* --- Header --- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Stack direction="row" spacing={1} alignItems="center">
          <VideocamIcon sx={{ color: '#ffca28' }} /> {/* สีเหลือง เพื่อให้ต่างจากจอแรก */}
          <Typography variant="h6" fontWeight={600} color="text.primary">
            Camera 2 (Side View)
          </Typography>
        </Stack>
        
        <Chip 
          label={isOnline ? "LIVE" : "OFF"} 
          color={isOnline ? "warning" : "default"} 
          size="small"
          variant={isOnline ? "filled" : "outlined"}
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
          // ตรงนี้เรียก /video_feed_2 (ถ้ายังไม่ได้ทำ Python ให้แก้เป็น /video_feed ชั่วคราว)
          <img 
            src="http://192.168.1.50:5000/video_feed_2" 
            alt="Camera 2 Stream" 
            style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
          />
        ) : (
          <Stack alignItems="center" spacing={1} color="text.secondary">
            <VideocamOffIcon sx={{ fontSize: 40, opacity: 0.5 }} />
            <Typography variant="caption">No Signal</Typography>
          </Stack>
        )}
      </Box>

      {/* --- Footer Info --- */}
      <Stack direction="row" justifyContent="space-between" mt={1}>
        <Typography variant="caption" color="text.secondary">Source: Local Webcam (ID 1)</Typography>
        <Typography variant="caption" color="text.disabled">1280 x 720</Typography>
      </Stack>

    </Paper>
  );
};

export default CompletedTask;