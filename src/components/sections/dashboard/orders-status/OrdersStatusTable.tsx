import { DataGrid, GridColDef } from '@mui/x-data-grid';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';

// 1. เพิ่ม field 'zone' ใน Interface
export interface RobotLog {
  seq: number;
  id: number;
  time: string;
  status: string;
  zone: string; 
}

// 2. กำหนดคอลัมน์
const columns: GridColDef[] = [
  { 
    field: 'seq', 
    headerName: 'Sequence', 
    flex: 0.5,
    minWidth: 100,
    headerAlign: 'center',
    align: 'center',
    renderCell: (params) => (
      <span style={{ color: '#00e676', fontWeight: 'bold', fontFamily: 'monospace' }}>
        #{params.value}
      </span>
    )
  },
  { 
    field: 'id', 
    headerName: 'Tag ID', 
    flex: 1,
    minWidth: 120,
    headerAlign: 'center',
    align: 'center',
    renderCell: (params) => (
      <Chip 
        label={`ID: ${params.value}`} 
        size="small" 
        sx={{ 
          bgcolor: 'rgba(255, 82, 82, 0.2)', 
          color: '#ff5252', 
          fontWeight: 'bold',
          border: '1px solid rgba(255, 82, 82, 0.3)'
        }} 
      />
    )
  },
  
  // >>> แก้ไขคอลัมน์ ZONE ตรงนี้ <<<
  { 
    field: 'zone', 
    headerName: 'Detected Zone', 
    flex: 1.5,
    minWidth: 160,
    headerAlign: 'center',
    align: 'center',
    renderCell: (params) => {
        const zoneName = params.value || "Unknown";
        let color = "#999"; 
        let borderColor = "#555";

        if (zoneName.includes("Green")) { color = "#00e676"; borderColor = "rgba(0, 230, 118, 0.5)"; }
        if (zoneName.includes("Yellow")) { color = "#ffca28"; borderColor = "rgba(255, 202, 40, 0.5)"; }
        if (zoneName.includes("Red")) { color = "#f44336"; borderColor = "rgba(244, 67, 54, 0.5)"; }

        return (
            <Box sx={{ 
                color: color, 
                fontWeight: 'bold', 
                border: `1px solid ${borderColor}`, 
                bgcolor: `${color}11`, 
                
                // >>> จุดที่แก้ <<<
                lineHeight: 1,     // ตัดระยะห่างบรรทัดทิ้ง
                px: 1.5,           // Padding แนวนอน
                py: 0.5,           // Padding แนวตั้ง (ปรับเลขนี้ได้ตามใจชอบแล้ว)
                
                borderRadius: 1,
                fontSize: '0.75rem',
                display: 'inline-block'
            }}>
                {zoneName}
            </Box>
        );
    }
  },

  { 
    field: 'time', 
    headerName: 'Date & Time', 
    flex: 2,
    minWidth: 200, 
    headerAlign: 'left',
    align: 'left',
    renderCell: (params) => (
      <span style={{ color: '#448aff', fontFamily: 'monospace', fontSize: '0.9rem' }}>
        {params.value} 
      </span>
    )
  },
  { 
    field: 'status', 
    headerName: 'Status', 
    flex: 1,
    headerAlign: 'center',
    align: 'center',
    renderCell: () => (
      <Chip 
        label="Success" 
        size="small" 
        color="success" 
        variant="outlined" 
        sx={{ fontWeight: 'bold' }}
      />
    )
  },
];

const OrdersStatusTable = ({ rows }: { rows: RobotLog[] }) => {
  return (
    <Box sx={{ height: 450, width: '100%' }}>
      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(row) => row.seq} 
        initialState={{
          pagination: { paginationModel: { pageSize: 10 } }, 
        }}
        pageSizeOptions={[5, 10, 20, 50]}
        sx={{
          border: 'none',
          '& .MuiDataGrid-cell': { borderBottom: '1px solid rgba(255,255,255,0.05)' },
          '& .MuiDataGrid-columnHeaders': { 
              bgcolor: '#1E1E1E', 
              color: '#888',
              borderBottom: '1px solid #333',
              textTransform: 'uppercase',
              fontSize: '0.75rem'
          },
          '& .MuiDataGrid-row:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
          '& .MuiTablePagination-root': { color: 'gray' },
          color: 'white'
        }}
        disableRowSelectionOnClick
      />
    </Box>
  );
};

export default OrdersStatusTable;