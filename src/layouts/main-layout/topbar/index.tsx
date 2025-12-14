import { useLocation, useNavigate } from 'react-router-dom';
import { fontFamily } from 'theme/typography';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import ButtonBase from '@mui/material/ButtonBase';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import IconifyIcon from 'components/base/IconifyIcon';
import Image from 'components/base/Image';
import LogoImg from 'assets/images/Logo.png';
import LogoutIcon from '@mui/icons-material/Logout';

interface TopbarProps {
  isClosing: boolean;
  mobileOpen: boolean;
  setMobileOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

const Topbar = ({ isClosing, mobileOpen, setMobileOpen }: TopbarProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleDrawerToggle = () => {
    if (!isClosing) {
      setMobileOpen(!mobileOpen);
    }
  };

  // 1. ฟังก์ชัน Logout
  const handleLogout = () => {
    if (window.confirm("Are you sure you want to logout?")) {
        localStorage.removeItem('isAuthenticated');
        navigate('/authentication/login');
    }
  };

  // 2. ฟังก์ชันเปลี่ยนชื่อหัวข้อตามหน้า
  const getHeaderTitle = () => {
    const path = location.pathname;
    if (path.includes('/admin')) return 'Admin Control Panel';
    if (path.includes('/calibration')) return 'Calibration Panel';
    return 'Automated Pick & Place System via AprilTags';
  };

  return (
    <Stack 
      direction="row" 
      alignItems="center" 
      justifyContent="space-between" 
      mb={{ xs: 0, lg: 1 }}
      sx={{ height: 90 }} 
    >
      
      {/* --- ส่วนซ้าย: เมนู + โลโก้ + ชื่อหน้า (ตัวใหญ่) --- */}
      <Stack spacing={3} direction="row" alignItems="center">
        
        <Toolbar sx={{ display: { xm: 'block', lg: 'none' } }}>
          <IconButton size="medium" edge="start" color="inherit" onClick={handleDrawerToggle}>
            <IconifyIcon icon="mingcute:menu-line" />
          </IconButton>
        </Toolbar>

        <ButtonBase component={Link} href="/" disableRipple sx={{ display: { xm: 'block', lg: 'none' } }}>
          <Image src={LogoImg} alt="logo" height={24} width={24} />
        </ButtonBase>

        <Typography
          variant="h3" // ใหญ่สะใจ
          fontWeight={800} 
          letterSpacing={0.5}
          fontFamily={fontFamily.workSans}
          display={{ xs: 'none', lg: 'block' }}
          sx={{
            color: 'white !important', 
            background: 'none !important', 
            WebkitTextFillColor: 'white !important', 
            textShadow: 'none !important' 
          }}
        >
          {getHeaderTitle()}
        </Typography>
      </Stack>

      {/* --- ส่วนขวา: ปุ่ม Logout (เอากลับมาแล้ว!) --- */}
      <Stack direction="row" alignItems="center" spacing={2} pr={2}>
        <Tooltip title="Logout">
            <IconButton 
                onClick={handleLogout} 
                sx={{ 
                    color: '#ff4444', // สีแดง
                    bgcolor: 'rgba(255, 68, 68, 0.1)', 
                    border: '1px solid rgba(255, 68, 68, 0.3)',
                    width: 45, height: 45,
                    '&:hover': { 
                        bgcolor: '#ff4444', 
                        color: 'white',
                        boxShadow: '0 0 10px rgba(255, 68, 68, 0.5)'
                    } 
                }}
            >
                <LogoutIcon />
            </IconButton>
        </Tooltip>
      </Stack>
      
    </Stack>
  );
};

export default Topbar;