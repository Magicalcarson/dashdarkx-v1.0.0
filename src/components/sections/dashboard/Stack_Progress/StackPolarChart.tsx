import { useMemo } from 'react';
import { useTheme } from '@mui/material';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { CanvasRenderer } from 'echarts/renderers';
import { PolarComponent, TooltipComponent, GraphicComponent } from 'echarts/components';

// ลงทะเบียน Component ที่ต้องใช้
echarts.use([PolarComponent, TooltipComponent, GraphicComponent, BarChart, CanvasRenderer]);

const StackPolarChart = ({ height }: { height: number }) => {
  const theme = useTheme();
  const MAX_HEIGHT = 300; 

  const option = useMemo(() => ({
    polar: {
      radius: ['85%', '100%'], 
    },
    angleAxis: {
      max: MAX_HEIGHT,
      startAngle: 90,
      show: false, 
    },
    radiusAxis: {
      type: 'category',
      show: false, 
    },
    tooltip: {
      formatter: '{c} mm', 
    },
    series: [
      {
        type: 'bar',
        data: [
          {
            value: height,
            itemStyle: {
              color: '#00d4ff', 
              shadowBlur: 20,
              shadowColor: 'rgba(0, 212, 255, 0.5)'
            },
          },
        ],
        coordinateSystem: 'polar',
        barWidth: 50,  
        roundCap: true, 
        showBackground: true,
        backgroundStyle: {
          color: '#2c2c2c', 
        },
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '45%', // ขยับตัวเลขขึ้นนิดนึง
        style: {
          text: `${height.toFixed(1)}`,
          fill: '#ffffff',
          fontSize: 45, // ปรับขนาดให้พอดี (ไม่ใหญ่เกิน)
          fontWeight: 'bold',
          fontFamily: 'Segoe UI',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: '58%', // ขยับหน่วยให้อยู่ใต้ตัวเลขพอดี
        style: {
          text: 'mm',
          fill: '#888',
          fontSize: 16, 
          fontWeight: 'normal',
        },
      }
    ],
  }), [height, theme]);

  return <ReactECharts echarts={echarts} option={option} style={{ height: 400, width: '100%' }} />;
};

export default StackPolarChart;