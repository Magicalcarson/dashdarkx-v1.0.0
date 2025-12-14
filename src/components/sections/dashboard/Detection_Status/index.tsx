import { fontFamily } from 'theme/typography';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';

interface HistoryItem {
  seq: number;
  id: number;
  time: string;
}

interface WebsiteVisitorsProps {
  status: string;
  history: HistoryItem[];
  x: number;
  y: number;
}

const WebsiteVisitors = ({ status, history, x, y }: WebsiteVisitorsProps) => {
  
  const getStatusColor = () => {
    if (status.includes("DETECTED")) return "#00e676"; 
    if (status.includes("BUSY")) return "#ffca28"; 
    if (status === "OFFLINE") return "#f44336"; 
    return "text.disabled"; 
  };

  // ฟังก์ชันตัดวันที่ทิ้ง
  const formatTimeOnly = (fullTime: string) => {
    if (!fullTime) return "--:--:--";
    const parts = fullTime.split(' '); 
    return parts.length > 1 ? parts[1] : fullTime;
  };

  return (
    <Paper sx={{ p: 3, height: '100%', minHeight: 530, display: 'flex', flexDirection: 'column', gap: 2 }}>
      
      {/* --- HEADER --- */}
      <Typography variant="h6" fontWeight={600} fontFamily={fontFamily.workSans} color="#00d4ff" mb={2}>
        Detection Status
      </Typography>

      {/* --- SECTION 1: STATUS & COORDINATES --- */}
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <Box sx={{ bgcolor: '#1E1E1E', p: 2, borderRadius: 2, textAlign: 'center', border: '1px solid rgba(255, 255, 255, 0.1)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Typography variant="caption" fontWeight={600} color="text.secondary" mb={1}>
              LATEST STATUS
            </Typography>
            <Typography variant="h5" fontWeight={700} fontFamily={fontFamily.workSans} sx={{ color: getStatusColor(), opacity: 0.9 }}>
              {status}
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6}>
          <Box sx={{ bgcolor: '#1E1E1E', p: 2, borderRadius: 2, border: '1px solid rgba(0, 255, 0, 0.2)' }}>
             <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" textAlign="center" mb={1}>
                TARGET (mm)
             </Typography>
             <Stack direction="row" justifyContent="space-around">
               <Box textAlign="center">
                 <Typography variant="h5" fontWeight="bold" color="white">{Math.round(x)}</Typography>
                 <Typography variant="caption" color="gray">X</Typography>
               </Box>
               <Box textAlign="center">
                 <Typography variant="h5" fontWeight="bold" color="white">{Math.round(y)}</Typography>
                 <Typography variant="caption" color="gray">Y</Typography>
               </Box>
             </Stack>
          </Box>
        </Grid>
      </Grid>

      {/* --- SECTION 2: HISTORY TABLE (FIXED LAYOUT) --- */}
      <Box sx={{ 
        bgcolor: '#1E1E1E', 
        borderRadius: 2, 
        border: '1px solid rgba(255, 255, 255, 0.1)', 
        flexGrow: 1, 
        overflow: 'hidden', 
        p: 2,
        display: 'flex',           
        flexDirection: 'column'    
      }}>
        <Typography variant="caption" fontWeight={600} color="text.secondary" mb={2} display="block">
          RECENT HISTORY (Max 5)
        </Typography>
        
        {/* Container สำหรับรายการประวัติ */}
        <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 1 }}>
          {history.length > 0 ? (
            // >>>> ตัดเหลือ 4 รายการ (0-4) <<<<
            history.slice(0, 5).map((row: HistoryItem) => ( 
              
              // แต่ละแถวใช้ Grid Container เพื่อแบ่งคอลัมน์แนวนอน
              <Grid container key={row.seq} alignItems="center" sx={{ width: '100%', borderBottom: '1px solid rgba(255,255,255,0.05)', pb: 1 }}>
                
                {/* Col 1: Sequence (เขียว) */}
                <Grid item xs={3}>
                  <Typography variant="body2" sx={{ color: '#00e676', fontFamily: 'monospace' }}>
                    #{row.seq}
                  </Typography>
                </Grid>
                
                {/* Col 2: ID Tag (แดง) */}
                <Grid item xs={6} textAlign="center">
                   <Typography variant="subtitle2" sx={{ color: '#ff5252', fontWeight: 'bold', fontFamily: 'monospace' }}>
                     ID: {row.id}
                   </Typography>
                </Grid>
                
                {/* Col 3: Time (น้ำเงิน) */}
                <Grid item xs={3} textAlign="right">
                   <Typography variant="caption" sx={{ color: '#448aff', fontFamily: 'monospace' }}>
                     {formatTimeOnly(row.time)}
                   </Typography>
                </Grid>

              </Grid>
            ))
          ) : (
            <Typography variant="caption" color="text.disabled" textAlign="center" mt={5}>
               - No History -
            </Typography>
          )}
        </Box>
      </Box>

      {/* --- SECTION 3: SYSTEM INFO --- */}
      <Box>
        <Typography variant="subtitle2" fontWeight={600} fontFamily={fontFamily.workSans} color="#00d4ff" mb={2} mt={2}>
          System Info
        </Typography>

        <Grid container spacing={1}>
          <Grid item xs={4} sx={{ textAlign: 'left' }}> 
            <Typography variant="caption" fontWeight={800} color="text.primary" display="block">Camera</Typography>
            <Typography variant="caption" fontWeight={700} color="text.secondary" display="block">RTSP Stream 2</Typography>
          </Grid>
          <Grid item xs={4} sx={{ textAlign: 'left' }}> 
            <Typography variant="caption" fontWeight={800} color="text.primary" display="block">Resolution</Typography>
            <Typography variant="caption" fontWeight={700} color="text.secondary" display="block">1280 x 720</Typography>
          </Grid>
          <Grid item xs={4} sx={{ textAlign: 'left' }}> 
            <Typography variant="caption" fontWeight={800} color="text.primary" display="block">Algorithm</Typography>
            <Typography variant="caption" fontWeight={700} color="text.secondary" display="block">Pupil AprilTags</Typography>
          </Grid>
        </Grid>
      </Box>

    </Paper>
  );
};

export default WebsiteVisitors;