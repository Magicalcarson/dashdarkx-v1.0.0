import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import IconifyIcon from 'components/base/IconifyIcon';
import { fontFamily } from 'theme/typography';

// 1. ต้องมี Interface นี้ เพื่อบอก TypeScript ว่ารับค่าอะไรบ้าง
interface TopCardsProps {
  totalPicked: number;
  stackHeight: number;
  cycleTime: number;
  status: string;
}

const TopCards = ({ totalPicked, stackHeight, cycleTime, status }: TopCardsProps) => {
  
  const cardsData = [
    {
      id: 1,
      title: 'Total Picked',
      value: totalPicked.toString(),
      icon: 'fluent-mdl2:product',
      color: '#00e676',
      unit: 'pcs',
    },
    {
      id: 2,
      title: 'Stack Height',
      value: stackHeight.toFixed(1),
      icon: 'fluent:layer-24-filled',
      color: '#ffca28',
      unit: 'mm',
    },
    {
      id: 3,
      title: 'Avg. Cycle Time',
      value: cycleTime.toFixed(1),
      icon: 'mingcute:time-fill',
      color: '#29b6f6',
      unit: 'sec',
    },
    {
      id: 4,
      title: 'System Status',
      value: status === "OFFLINE" ? "OFFLINE" : "ONLINE",
      icon: 'fluent:presence-available-24-filled',
      color: status === "OFFLINE" ? '#f44336' : '#b388ff',
      unit: '',
    },
  ];

  return (
    <Grid container spacing={2.5}>
      {cardsData.map((item) => (
        <Grid item xs={12} sm={6} xl={3} key={item.id}>
          <Paper 
            sx={{ 
              p: 2.5, 
              height: '100%', 
              bgcolor: '#1E1E1E', 
              borderRadius: 3, 
              border: '1px solid rgba(255,255,255,0.05)',
              color: 'white',
              boxShadow: 'none'
            }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <IconifyIcon icon={item.icon} color={item.color} fontSize={24} />
                <Typography variant="body1" color="text.secondary" fontWeight={600}>
                  {item.title}
                </Typography>
              </Stack>
              <IconifyIcon icon="bi:three-dots" color="text.disabled" fontSize={20} />
            </Stack>

            <Stack direction="row" alignItems="baseline" spacing={1}>
              <Typography variant="h3" fontWeight={700} color="white" fontFamily={fontFamily.workSans}>
                {item.value}
              </Typography>
              <Typography variant="body2" color={item.color} fontWeight={600}>
                {item.unit}
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      ))}
    </Grid>
  );
};

export default TopCards;