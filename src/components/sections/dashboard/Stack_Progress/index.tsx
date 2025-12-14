import { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import StackPolarChart from './StackPolarChart'; // ดึงไฟล์ที่เราเพิ่งสร้างมาใช้

const CompletedTask = () => {
  
  const [stackHeight, setStackHeight] = useState(0);
  const MAX_STACK_HEIGHT = 300; 

  // ดึงข้อมูลจาก Python
  useEffect(() => {
    const interval = setInterval(() => {
      fetch('http://192.168.1.50s:5000/data')
        .then((res) => res.json())
        .then((data) => {
          let h = data.stack_h;
          if (h > MAX_STACK_HEIGHT) h = MAX_STACK_HEIGHT;
          setStackHeight(h);
        })
        .catch(() => setStackHeight(0));
    }, 200);
    return () => clearInterval(interval);
  }, []);

  return (
    <Paper sx={{ p: 3, height: 550, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h6" fontWeight={600} color="#00d4ff">
          Stack Progress
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ bgcolor: '#1E1E1E', px: 1, py: 0.5, borderRadius: 1 }}>
          Max: {MAX_STACK_HEIGHT} mm
        </Typography>
      </Stack>

      {/* Chart Area (กราฟวงกลม) */}
      <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', mt: 2 }}>
        <StackPolarChart height={stackHeight} />
      </Box>

      {/* Footer Info */}
      <Stack alignItems="center" mt={1}>
        <Typography variant="body2" color={stackHeight >= MAX_STACK_HEIGHT ? "error.main" : "text.secondary"}>
          {stackHeight >= MAX_STACK_HEIGHT ? "⚠️ LIMIT REACHED" : "● Monitoring..."}
        </Typography>
      </Stack>

    </Paper>
  );
};

export default CompletedTask;