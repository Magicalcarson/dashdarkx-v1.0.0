import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button'; // เพิ่ม
import DownloadIcon from '@mui/icons-material/Download'; // เพิ่ม (ต้อง npm install @mui/icons-material ก่อนนะ)
import OrdersStatusTable, { RobotLog } from './OrdersStatusTable';

interface OrdersStatusProps {
  history?: RobotLog[];
}

const OrdersStatus = ({ history = [] }: OrdersStatusProps) => {
  
  // ฟังก์ชันกดปุ่มแล้วดาวน์โหลดไฟล์
  const handleDownload = () => {
    window.open('http://localhost:5000/api/download_log', '_blank');
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h6" color="#00d4ff" fontWeight="bold">
          Full Operation Database
        </Typography>
        
        <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="caption" color="text.secondary">
              Total Records: {history.length}
            </Typography>
            
            {/* >>> ปุ่ม Export CSV <<< */}
            <Button 
                variant="outlined" 
                startIcon={<DownloadIcon />}
                onClick={handleDownload}
                sx={{ 
                  borderColor: '#00d4ff', 
                  color: '#00d4ff', 
                  '&:hover': { borderColor: '#00b0ff', bgcolor: 'rgba(0, 212, 255, 0.1)' } 
                }}
            >
                Export CSV
            </Button>
        </Stack>
      </Stack>

      <OrdersStatusTable rows={history} />
    </Paper>
  );
};

export default OrdersStatus;