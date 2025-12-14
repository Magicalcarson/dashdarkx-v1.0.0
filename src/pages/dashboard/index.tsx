import { useState, useEffect } from 'react';
import Grid from '@mui/material/Grid';

// --- Imports (อิงตามที่คุณส่งมา) ---
import TopCards from 'components/sections/dashboard/top-cards';
import WebsiteVisitors from 'components/sections/dashboard/Detection_Status'; // Detection Panel
import RevenueByCustomer from 'components/sections/dashboard/Camera1'; // Camera 1 (ถ้าคุณแก้ชื่อโฟลเดอร์แล้วให้แก้ตรงนี้ให้ตรง)
import Products from 'components/sections/dashboard/Camera2'; // Camera 2
import CompletedTask from 'components/sections/dashboard/Stack_Progress'; // Stack Chart
import OrdersStatus from 'components/sections/dashboard/orders-status'; // Database Log
import { API_ENDPOINTS } from 'config/api';

const Dashboard = () => {
  // 1. State สำหรับเก็บข้อมูลทั้งหมดจาก Robot API
  const [robotData, setRobotData] = useState({
    x: 0,
    y: 0,
    stack_h: 0.0,
    total_picked: 0,
    cycle_time: 0.0,
    status: "OFFLINE",
    history: [],
    active_id: "-"
  });

  // 2. Fetch Data loop (ดึงข้อมูลทุกๆ 0.2 วินาที)
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(API_ENDPOINTS.data)
        .then((res) => res.json())
        .then((data) => {
          setRobotData(data);
        })
        .catch(() => {
          setRobotData(prev => ({ ...prev, status: "OFFLINE" }));
        });
    }, 200);

    return () => clearInterval(interval);
  }, []);

  // >>> 3. ตรวจสอบสถานะเพื่อทำ Visual Alarm (เพิ่มตรงนี้) <<<
  const isAlarm = robotData.status === "OFFLINE" || robotData.status.includes("ERROR");

  return (
    // >>> 4. เพิ่ม SX สำหรับ Alarm Animation ที่ Grid ตัวแม่ <<<
    <Grid container spacing={2.5}
      sx={{
        border: isAlarm ? '4px solid #f44336' : 'none', // ขอบแดงเมื่อ Error
        borderRadius: 2,
        p: isAlarm ? 1 : 0,
        transition: 'all 0.3s ease',
        // เพิ่มเงากระพริบ (Animation)
        boxShadow: isAlarm ? '0 0 20px rgba(244, 67, 54, 0.5)' : 'none',
        animation: isAlarm ? 'pulse-alarm 1.5s infinite' : 'none',
        '@keyframes pulse-alarm': {
          '0%': { boxShadow: '0 0 0 0 rgba(244, 67, 54, 0.7)' },
          '70%': { boxShadow: '0 0 0 20px rgba(244, 67, 54, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(244, 67, 54, 0)' },
        },
      }}
    >

      {/* --- ROW 1: Top Stats Cards (การ์ดสถิติบนสุด) --- */}
      <Grid item xs={12}>
        <TopCards
          totalPicked={robotData.total_picked || 0}
          stackHeight={robotData.stack_h || 0}
          cycleTime={robotData.cycle_time || 0}
          status={robotData.status}
        />
      </Grid>

      {/* --- ROW 2: Detection & Main Camera --- */}
      
      {/* Left: Detection Status Panel */}
      <Grid item xs={12} xl={4}>
        <WebsiteVisitors
          status={robotData.status}
          history={robotData.history}
          x={robotData.x}
          y={robotData.y}
        />
      </Grid>

      {/* Right: Main Camera (Webcam 1) */}
      <Grid item xs={12} xl={8}>
        <RevenueByCustomer />
      </Grid>

      {/* --- ROW 3: Stack Progress & Side Camera --- */}
      
      {/* Left: Stack Circular Chart */}
      <Grid item xs={12} xl={4}>
        <CompletedTask />
      </Grid>

      {/* Right: Side Camera (Camera 2) */}
      <Grid item xs={12} xl={8}>
         <Products />
      </Grid>

      {/* --- ROW 4: Full Database Log (ตารางประวัติล่างสุด) --- */}
      <Grid item xs={12}>
         {/* ส่ง History log ทั้งหมดไปแสดงในตาราง */}
         <OrdersStatus history={robotData.history} />
      </Grid>

    </Grid>
  );
};

export default Dashboard;