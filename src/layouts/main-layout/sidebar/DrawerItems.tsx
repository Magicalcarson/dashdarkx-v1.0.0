import Link from '@mui/material/Link';
import List from '@mui/material/List';
import Stack from '@mui/material/Stack';
import Divider from '@mui/material/Divider';
import ButtonBase from '@mui/material/ButtonBase';
import Typography from '@mui/material/Typography';
import Image from 'components/base/Image';
import CollapseListItem from './list-items/CollapseListItem';
import ListItem from './list-items/ListItem';
import { topListData, bottomListData } from 'data/sidebarListData';

// >>> 1. เปลี่ยนชื่อไฟล์รูปตรงนี้ <<<
// (อย่าลืมเอาไฟล์ CPE101105V2.png ไปวางในโฟลเดอร์ assets/images ด้วยนะครับ)
import LogoImg from 'assets/images/CPE101105V2.png'; 

const DrawerItems = () => {
  return (
    <>
      {/* --- HEADER: LOGO & TITLE --- */}
      <Stack
        pt={5}
        pb={4}
        px={3} // ลด padding ซ้ายขวานิดนึงเพื่อให้มีพื้นที่ข้อความมากขึ้น
        position={'sticky'}
        top={0}
        bgcolor="info.darker"
        alignItems="center"
        justifyContent="flex-start"
        zIndex={1000}
      >
        <ButtonBase component={Link} href="/" disableRipple sx={{ width: '100%', justifyContent: 'flex-start' }}>
          {/* โลโก้ */}
          <Image src={LogoImg} alt="logo" height={45} width={45} sx={{ mr: 1.5, flexShrink: 0 }} />
          
          {/* >>> 2. ปรับขนาดตัวหนังสือไม่ให้ตกบรรทัด <<< */}
          <Typography 
            variant="subtitle1" // ลดขนาดจาก h5 เพื่อให้พอดี
            color="text.primary" 
            fontWeight={700} 
            letterSpacing={0} // ลดระยะห่างตัวอักษร
            noWrap // บังคับไม่ให้ขึ้นบรรทัดใหม่ (ถ้าล้นจริงๆ จะเป็น ...)
            sx={{ fontSize: '1.05rem' }} // กำหนดขนาดฟอนต์แบบละเอียด
          >
            KMUTT CPE101 - R14
          </Typography>
        </ButtonBase>
      </Stack>

      {/* --- MENU LIST --- */}
      <List component="nav" sx={{ px: 2.5, pt: 2 }}>
        {topListData.map((route, index) => {
          return <ListItem key={index} {...route} />;
        })}
      </List>

      {bottomListData.length > 0 && <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.1)' }} />}

      <List component="nav" sx={{ px: 2.5 }}>
        {bottomListData.map((route) => {
          if (route.items) {
            return <CollapseListItem key={route.id} {...route} />;
          }
          return <ListItem key={route.id} {...route} />;
        })}
      </List>

    </>
  );
};

export default DrawerItems;