import React, { useRef, useState, useEffect } from 'react';
import { Box, Typography, Stack, Chip, FormControlLabel, Switch } from '@mui/material';
import AdsClickIcon from '@mui/icons-material/AdsClick';
import PrecisionManufacturingIcon from '@mui/icons-material/PrecisionManufacturing';
import { API_ENDPOINTS } from 'config/api';

const InteractivePageCam2 = () => {
  const [lastClick, setLastClick] = useState<{x:number, y:number} | null>(null);
  const [status, setStatus] = useState("Connecting...");
  const [robotMode, setRobotMode] = useState<'MANUAL' | 'AUTO'>('MANUAL');
  const [targetPos, setTargetPos] = useState({ x: 0, y: 0 }); // [NEW] เก็บค่า XY
  const imgRef = useRef<HTMLImageElement>(null);

  // [NEW] Polling Loop: ดึงข้อมูลจาก Server ทุก 500ms
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(API_ENDPOINTS.data)
        .then(res => res.json())
        .then(data => {
          // อัปเดตข้อมูลบนหน้าจอ
          if (data.robot_mode) setRobotMode(data.robot_mode);
          if (data.status) setStatus(data.status);
          if (data.target_x !== undefined) setTargetPos({ x: data.target_x, y: data.target_y });
        })
        .catch(() => setStatus("Connection Lost"));
    }, 500);

    return () => clearInterval(interval);
  }, []);

  const handleModeToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newMode = e.target.checked ? 'AUTO' : 'MANUAL';
    // Call API to set mode
    fetch(API_ENDPOINTS.robotMode, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: newMode })
    });
    setRobotMode(newMode); // Update UI immediately for responsiveness
  };

  const handleClick = (e: React.MouseEvent) => {
    if (robotMode === 'AUTO') {
      alert("⚠️ Robot is in AUTO Mode. Switch to MANUAL to click.");
      return;
    }

    if (!imgRef.current) return;

    const rect = imgRef.current.getBoundingClientRect();
    const scaleX = 1280 / rect.width;
    const scaleY = 720 / rect.height;

    const px = (e.clientX - rect.left) * scaleX;
    const py = (e.clientY - rect.top) * scaleY;

    setLastClick({ x: Math.round(px), y: Math.round(py) });

    if (window.confirm(`🖱️ COMMAND: Pick at pixel (${Math.round(px)}, ${Math.round(py)})?`)) {
        setStatus("Sending command...");
        fetch(API_ENDPOINTS.robotClickMove, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: px, y: py })
        });
    }
  };

  // กำหนดสีสถานะ
  const getStatusColor = () => {
    if (status === 'DETECTED' || status === 'SUCCESS' || status === 'COMPLETED') return 'success';
    if (status.includes('FAILED') || status.includes('Error')) return 'error';
    if (status.includes('PICKING') || status.includes('MOVING')) return 'warning';
    return 'default';
  };

  return (
    <Box sx={{ p: 3, height: '100vh', bgcolor: '#0a0a0a', color: 'white' }}>

      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
         <Stack direction="row" spacing={3} alignItems="center">
             {robotMode === 'AUTO' ?
                <PrecisionManufacturingIcon sx={{ color: '#00e676', fontSize: 40 }} /> :
                <AdsClickIcon sx={{ color: '#ffca28', fontSize: 40 }} />
             }
             <Box>
                 <Typography variant="h4" fontWeight="bold">Smart Control (Camera 2)</Typography>
                 <Typography variant="body2" color="gray">
                    {robotMode === 'AUTO' ? 'Auto-Picking Active' : 'Click-to-Pick Mode'}
                 </Typography>
             </Box>

             {/* Toggle Switch */}
             <FormControlLabel
                control={
                  <Switch
                    checked={robotMode === 'AUTO'}
                    onChange={handleModeToggle}
                    color="success"
                  />
                }
                label={
                  <Typography fontWeight="bold" color={robotMode === 'AUTO' ? '#00e676' : '#ffca28'}>
                    {robotMode} MODE
                  </Typography>
                }
                sx={{ border: '1px solid #333', borderRadius: 2, pl: 1, pr: 2, py: 0.5, bgcolor: '#151515' }}
             />
         </Stack>

         <Stack direction="row" spacing={2} alignItems="center">
            {/* Target Display */}
            <Box sx={{ textAlign: 'right', mr: 2 }}>
                <Typography variant="caption" color="gray">TARGET (mm)</Typography>
                <Typography variant="h6" fontFamily="monospace" color="#00e676">
                    X:{targetPos.x.toFixed(1)} Y:{targetPos.y.toFixed(1)}
                </Typography>
            </Box>

            <Chip
                label={status}
                color={getStatusColor()}
                sx={{ fontSize: '1.2rem', px: 3, py: 2.5, fontWeight: 'bold' }}
            />
         </Stack>
      </Stack>

      {/* CAMERA FEED */}
      <Box display="flex" justifyContent="center" alignItems="center" sx={{ bgcolor: '#111', borderRadius: 4, p: 2, border: '1px solid #333' }}>
          <div style={{ position: 'relative', cursor: robotMode === 'AUTO' ? 'not-allowed' : 'crosshair' }}>
              <img
                ref={imgRef}
                src={API_ENDPOINTS.videoFeed2}
                alt="Camera 2 Interactive Feed"
                onClick={handleClick}
                style={{
                    display: 'block',
                    maxWidth: '100%',
                    height: 'auto',
                    borderRadius: '8px',
                    boxShadow: robotMode === 'AUTO' ? '0 0 20px rgba(0, 230, 118, 0.2)' : '0 0 20px rgba(255, 202, 40, 0.2)',
                    opacity: robotMode === 'AUTO' ? 0.9 : 1
                }}
              />

              {/* Overlay Text in Auto Mode */}
              {robotMode === 'AUTO' && (
                <Box position="absolute" top={15} right={15} bgcolor="rgba(0,0,0,0.7)" px={2} py={1} borderRadius={2} border="1px solid #00e676">
                   <Typography variant="body2" color="#00e676" fontWeight="bold">● AUTO-PILOT ON</Typography>
                </Box>
              )}

              {/* Click Indicator (Manual Only) */}
              {lastClick && robotMode === 'MANUAL' && (
                  <div style={{
                      position: 'absolute',
                      left: lastClick.x * (imgRef.current?.getBoundingClientRect().width || 1) / 1280 - 10,
                      top: lastClick.y * (imgRef.current?.getBoundingClientRect().height || 1) / 720 - 10,
                      width: 20, height: 20,
                      border: '3px solid #ffca28', borderRadius: '50%',
                      pointerEvents: 'none', boxShadow: '0 0 10px #ffca28'
                  }} />
              )}
          </div>
      </Box>
    </Box>
  );
};

export default InteractivePageCam2;
