/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  Grid,
  Select,
  MenuItem,
  Stack,
  IconButton,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import MicIcon from '@mui/icons-material/Mic';
import MicOffIcon from '@mui/icons-material/MicOff';

// ===================== CONFIG =====================
const PYTHON_SERVER = 'http://192.168.1.50:5000'; // Jetson Orin Nano (Backend)

// ===================== Helper UI Components =====================

const GroupBox = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <Box
    sx={{
      border: '1px solid #666',
      borderRadius: '4px',
      p: 3,
      pt: 4,
      mb: 3,
      position: 'relative',
      bgcolor: 'transparent',
    }}
  >
    <Typography
      sx={{
        position: 'absolute',
        top: '-10px',
        left: '10px',
        bgcolor: '#121212',
        px: 0.5,
        color: '#e0e0e0',
        fontSize: '0.9rem',
      }}
    >
      {title}
    </Typography>
    {children}
  </Box>
);

const StdButton = ({
  text,
  onClick,
  sx = {},
  disabled = false,
  ...rest
}: {
  text: string;
  onClick?: () => void;
  sx?: any;
  disabled?: boolean;
  [key: string]: any;
}) => (
  <Button
    variant="contained"
    onClick={onClick}
    disabled={disabled}
    sx={{
      background: '#e0e0e0 !important',
      color: 'black !important',
      textTransform: 'none',
      boxShadow: 'none',
      border: '1px solid #999',
      minWidth: '40px',
      height: '30px',
      fontSize: '0.8rem',
      p: '0 10px',
      '&:hover': { background: '#dcdcdc !important' },
      ...sx,
    }}
    {...rest}
  >
    {text}
  </Button>
);

const ColorButton = ({
  text,
  color,
  onClick,
  textColor = 'white',
  sx = {},
  disabled = false,
  ...rest
}: {
  text: string;
  color: string;
  onClick?: () => void;
  textColor?: string;
  sx?: any;
  disabled?: boolean;
  [key: string]: any;
}) => (
  <Button
    variant="contained"
    onClick={onClick}
    disabled={disabled}
    sx={{
      background: `${color} !important`,
      color: `${textColor} !important`,
      textTransform: 'none',
      boxShadow: 'none',
      fontWeight: 'bold',
      height: '32px',
      fontSize: '0.85rem',
      borderRadius: '4px',
      '&:hover': { opacity: 0.8 },
      ...sx,
    }}
    {...rest}
  >
    {text}
  </Button>
);

const InputField = ({
  value,
  onChange,
  width = 80,
  ...rest
}: {
  value: any;
  onChange: (e: any) => void;
  width?: number;
  [key: string]: any;
}) => (
  <TextField
    variant="outlined"
    size="small"
    value={value}
    onChange={onChange}
    {...rest}
    sx={{
      width,
      '& .MuiOutlinedInput-root': {
        bgcolor: 'white !important',
        color: 'black !important',
        borderRadius: 0,
        height: 30,
        '& fieldset': { borderColor: '#999' },
        '&:hover fieldset': { borderColor: '#666' },
        '&.Mui-focused fieldset': { borderColor: '#007bff' },
      },
      '& input': { p: '4px 8px', color: 'black !important', fontWeight: 500 },
    }}
  />
);

const EmergencyStopButton = ({ onClick }: { onClick: () => void }) => (
  <>
    <Box
      onClick={onClick}
      sx={{
        width: 110,
        height: 110,
        borderRadius: '50%',
        background: '#d00000',
        border: '4px solid #ff4444',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        fontWeight: 'bold',
        fontSize: 13,
        color: 'white',
        cursor: 'pointer',
        textAlign: 'center',
        lineHeight: 1.1,
        boxShadow: '0 0 12px #ff4444',
        animation: 'pulseRing 1.3s infinite',
        userSelect: 'none',
        '&:hover': { transform: 'scale(1.05)', background: '#e00000' },
        '&:active': { transform: 'scale(0.95)' },
      }}
    >
      EMERGENCY
      <br />
      STOP
    </Box>

    <style>
      {`
        @keyframes pulseRing {
          0% { box-shadow: 0 0 0px #ff4444; }
          50% { box-shadow: 0 0 20px #ff4444; }
          100% { box-shadow: 0 0 0px #ff4444; }
        }
      `}
    </style>
  </>
);

// ===================== MAIN PANEL =====================

const AdminPanel = () => {
  // --- Robot connection ---
  const [ip, setIp] = useState('192.168.1.6');
  const [ports, setPorts] = useState({ dash: 29999, move: 30003, feed: 30004 });
  const [isConnected, setIsConnected] = useState(false);

  // --- Motion / pose ---
  const [speed, setSpeed] = useState<number | string>(30);
  const [coords, setCoords] = useState({ x: 284, y: 0.5, z: 121, r: 269 });
  const [joints, setJoints] = useState({ j1: 0, j2: 0, j3: 0, j4: 0 });
  const [jogStep, setJogStep] = useState<number | string>(1);

  // --- Digital Output config ---
  const [doConfig, setDoConfig] = useState({ index: 1, status: 'On' });

  // --- Robot mode / drag ---
  const [robotMode, setRobotMode] = useState<'Manual' | 'Auto'>('Manual');
  const [dragMode, setDragMode] = useState(false);

  // --- Pose & IO (Feedback) ---
  const [pose, setPose] = useState<any | null>(null);
  const [ioState, setIoState] = useState<{ di: number[]; do: number[] }>({ di: [], do: [] });
  const [alarmText, setAlarmText] = useState('No Error...');

  // --- Jog hold state ---
  const jogIntervalRef = useRef<number | null>(null);

  // --- Log & Voice ---
  const [logs, setLogs] = useState<string[]>([
    '> System Ready...',
    '> Waiting for connection...',
  ]);
  const [isListening, setIsListening] = useState(false);
  const [voiceText, setVoiceText] = useState('');

  // ==================== Log Helper ====================
  const addLog = (msg: string) => {
    setLogs((prev) => [`> ${msg}`, ...prev].slice(0, 120));
  };

  // ==================== Backend Command Helper ====================

  const sendCommand = async (cmd: string, payload: any = {}) => {
    console.log('[CMD]', cmd, payload);
    addLog(`CMD: ${cmd}`);

    let endpoint = '';
    const method: 'POST' | 'GET' = 'POST';
    let body: any = {};

    switch (cmd) {
      case 'connect':
        endpoint = '/api/robot/connect';
        body = { ip };
        break;

      case 'enable':
        endpoint = '/api/robot/enable';
        body = { enable: true };
        break;

      case 'disable':
        endpoint = '/api/robot/enable';
        body = { enable: false };
        break;

      case 'reset':
        endpoint = '/api/robot/reset';
        break;

      case 'clear':
        endpoint = '/api/robot/clear';
        break;

      case 'estop':
        endpoint = '/api/robot/emergency_stop';
        break;

      case 'speed':
        endpoint = '/api/robot/speed';
        body = { val: Number(payload.val ?? speed) || 30 };
        break;

      case 'do':
        endpoint = '/api/robot/do';
        body = { index: Number(payload.index), status: payload.status };
        break;

      case 'movj':
        endpoint = '/api/robot/move';
        body = { mode: 'MovJ', ...coords };
        break;

      case 'movl':
        endpoint = '/api/robot/move';
        body = { mode: 'MovL', ...coords };
        break;

      case 'joint':
        endpoint = '/api/robot/move';
        body = { mode: 'JointMovJ', ...joints };
        break;

      case 'home':
        endpoint = '/api/robot/move';
        body = { mode: 'home' };
        break;

      // ================= Jog STEP (ใช้กับทั้งกดครั้งเดียว และกดค้าง) =================
      case 'jog_cartesian': {
        const step = Number(jogStep) || 1;
        const delta = step * (payload.dir || 1);
        const newCoords = { ...coords };

        if (payload.axis === 'X') newCoords.x = Number(newCoords.x) + delta;
        if (payload.axis === 'Y') newCoords.y = Number(newCoords.y) + delta;
        if (payload.axis === 'Z') newCoords.z = Number(newCoords.z) + delta;
        if (payload.axis === 'R') newCoords.r = Number(newCoords.r) + delta;

        setCoords(newCoords);
        endpoint = '/api/robot/move';
        body = { mode: 'MovL', ...newCoords };
        break;
      }

      case 'jog_joint': {
        const step = Number(jogStep) || 1;
        const delta = step * (payload.dir || 1);
        const newJ = { ...joints };

        if (payload.joint === 'J1') newJ.j1 = Number(newJ.j1) + delta;
        if (payload.joint === 'J2') newJ.j2 = Number(newJ.j2) + delta;
        if (payload.joint === 'J3') newJ.j3 = Number(newJ.j3) + delta;
        if (payload.joint === 'J4') newJ.j4 = Number(newJ.j4) + delta;

        setJoints(newJ);
        endpoint = '/api/robot/move';
        body = { mode: 'JointMovJ', ...newJ };
        break;
      }

      // UI only (ยังไม่ได้ต่อ backend จริง)
      case 'set_mode':
        addLog(`(UI) Robot mode -> ${payload.mode}`);
        return;

      case 'drag_on':
        setDragMode(true);
        addLog('(UI) Drag mode ON (add backend endpoint later)');
        return;

      case 'drag_off':
        setDragMode(false);
        addLog('(UI) Drag mode OFF (add backend endpoint later)');
        return;

      default:
        addLog(`Unknown command: ${cmd}`);
        return;
    }

    try {
      const res = await fetch(`${PYTHON_SERVER}${endpoint}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'POST' ? JSON.stringify(body) : undefined,
      });

      const data = await res.json().catch(() => ({}));

      if (data.status === 'success') {
        addLog(`OK: ${cmd}`);
        if (cmd === 'connect') setIsConnected(true);
      } else {
        const msg = data.message || 'Unknown error';
        addLog(`ERROR (${cmd}): ${msg}`);
        if (cmd === 'connect') setIsConnected(false);
      }
    } catch (err) {
      console.error(err);
      addLog(`ERROR: Failed to connect to Python Server (${cmd})`);
      if (cmd === 'connect') setIsConnected(false);
    }
  };

  // ==================== Jog Hold Functions (กดค้างให้วิ่งต่อเนื่อง) ====================

  const startJogCartesian = (axis: 'X' | 'Y' | 'Z' | 'R', dir: 1 | -1) => {
    if (jogIntervalRef.current !== null) return;

    const sendOne = () => {
      sendCommand('jog_cartesian', { axis, dir });
    };

    sendOne(); // ยิงครั้งแรกทันที
    jogIntervalRef.current = window.setInterval(sendOne, 150); // ยิงซ้ำทุก 150ms
  };

  const startJogJoint = (joint: 'J1' | 'J2' | 'J3' | 'J4', dir: 1 | -1) => {
    if (jogIntervalRef.current !== null) return;

    const sendOne = () => {
      sendCommand('jog_joint', { joint, dir });
    };

    sendOne();
    jogIntervalRef.current = window.setInterval(sendOne, 150);
  };

  const stopJog = () => {
    if (jogIntervalRef.current !== null) {
      clearInterval(jogIntervalRef.current);
      jogIntervalRef.current = null;
    }
  };

  // ==================== Voice Control ====================

  useEffect(() => {
    if (!('webkitSpeechRecognition' in window)) return;
    const recognition = new (window as any).webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);

    recognition.onresult = (event: any) => {
      const command = event.results[0][0].transcript.toLowerCase();
      setVoiceText(`"${command}"`);
      addLog(`Voice Command: ${command}`);

      if (command.includes('connect')) sendCommand('connect');
      else if (command.includes('enable')) sendCommand('enable');
      else if (command.includes('disable')) sendCommand('disable');
      else if (command.includes('reset')) sendCommand('reset');
      else if (command.includes('clear')) sendCommand('clear');
      else if (command.includes('home')) sendCommand('home');
      else if (command.includes('stop') || command.includes('emergency')) sendCommand('estop');
    };

    if (isListening) recognition.start();
    else recognition.stop();

    return () => recognition.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isListening]);

  const toggleMic = () => setIsListening((prev) => !prev);

  // ==================== Poll Pose + IO ====================

  useEffect(() => {
    if (!isConnected) return;

    const interval = window.setInterval(async () => {
      try {
        // Pose
        const resPose = await fetch(`${PYTHON_SERVER}/api/robot/pose`);
        if (resPose.ok) {
          const dataPose = await resPose.json();
          if (dataPose.status === 'success' || dataPose.x !== undefined) {
            setPose(dataPose);
          }
        }

        // IO
        const resIo = await fetch(`${PYTHON_SERVER}/api/robot/io`);
        if (resIo.ok) {
          const dataIo = await resIo.json();
          if (dataIo.status === 'success' || dataIo.di || dataIo.do) {
            setIoState({
              di: Array.isArray(dataIo.di) ? dataIo.di : [],
              do: Array.isArray(dataIo.do) ? dataIo.do : [],
            });
          }
          if (Array.isArray(dataIo.alarms) && dataIo.alarms.length > 0) {
            setAlarmText(
              dataIo.alarms
                .map((a: any) => (typeof a === 'string' ? a : a.msg || JSON.stringify(a)))
                .join('\n'),
            );
          } else if (dataIo.alarm_text) {
            setAlarmText(dataIo.alarm_text);
          } else {
            setAlarmText('No Error...');
          }
        }
      } catch (e) {
        // เงียบไว้ ไม่ spam log
      }
    }, 500);

    return () => window.clearInterval(interval);
  }, [isConnected]);

  // ==================== Render ====================

  return (
    <Box sx={{ p: 4, bgcolor: '#121212', minHeight: '100vh', color: '#e0e0e0' }}>
      {/* Header + Voice */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight="bold" color="white">
          Admin Control (Dobot-style)
        </Typography>

        <Stack
          direction="row"
          alignItems="center"
          spacing={2}
          bgcolor="#1e1e1e"
          px={2}
          py={0.5}
          borderRadius={5}
          border="1px solid #333"
        >
          <Typography
            variant="caption"
            color={isListening ? '#00e676' : 'gray'}
            sx={{ minWidth: 80, textAlign: 'right' }}
          >
            {voiceText || (isListening ? 'Listening...' : 'Voice Control')}
          </Typography>
          <IconButton onClick={toggleMic} sx={{ color: isListening ? '#f44336' : 'white' }}>
            {isListening ? <MicIcon /> : <MicOffIcon />}
          </IconButton>
        </Stack>
      </Stack>

      {/* ================= TOP ROW ================= */}
      <Grid container spacing={3}>
        {/* LEFT: Connect + Dashboard */}
        <Grid item xs={12} md={8}>
          {/* 1. Robot Connect */}
          <GroupBox title="Robot Connect">
            <Grid container alignItems="center" spacing={2}>
              <Grid item xs={12} md={9}>
                <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                  <Typography variant="body2">IP Address:</Typography>
                  <InputField
                    value={ip}
                    width={130}
                    onChange={(e: any) => setIp(e.target.value)}
                  />

                  <Typography variant="body2">Dashboard:</Typography>
                  <InputField
                    value={ports.dash}
                    width={80}
                    type="number"
                    onChange={(e: any) =>
                      setPorts({ ...ports, dash: Number(e.target.value) || 0 })
                    }
                  />
                  <Typography variant="body2">Move:</Typography>
                  <InputField
                    value={ports.move}
                    width={80}
                    type="number"
                    onChange={(e: any) =>
                      setPorts({ ...ports, move: Number(e.target.value) || 0 })
                    }
                  />
                  <Typography variant="body2">Feedback:</Typography>
                  <InputField
                    value={ports.feed}
                    width={80}
                    type="number"
                    onChange={(e: any) =>
                      setPorts({ ...ports, feed: Number(e.target.value) || 0 })
                    }
                  />
                </Stack>
              </Grid>
              <Grid item xs={12} md={3} textAlign="right">
                <ColorButton
                  text={isConnected ? 'Re-Connect' : 'Connect'}
                  color="#007bff"
                  onClick={() => sendCommand('connect')}
                  sx={{ width: 120 }}
                />
                <Typography
                  variant="caption"
                  display="block"
                  mt={0.5}
                  color={isConnected ? '#00e676' : 'gray'}
                >
                  Status: {isConnected ? 'Connected' : 'Disconnected'}
                </Typography>
              </Grid>
            </Grid>
          </GroupBox>

          {/* 2. Robot Dashboard */}
          <GroupBox title="Robot Dashboard">
            <Stack
              direction={{ xs: 'column', md: 'row' }}
              spacing={3}
              alignItems="flex-start"
              flexWrap="wrap"
            >
              {/* Robot Mode + Drag */}
              <Stack spacing={1}>
                <Typography variant="body2">Robot Mode</Typography>
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={robotMode}
                  onChange={(_, v) => {
                    if (!v) return;
                    setRobotMode(v);
                    sendCommand('set_mode', { mode: v });
                  }}
                >
                  <ToggleButton value="Manual">Manual</ToggleButton>
                  <ToggleButton value="Auto">Auto</ToggleButton>
                </ToggleButtonGroup>

                <Stack direction="row" spacing={1} mt={1} alignItems="center">
                  <StdButton
                    text={dragMode ? 'Drag: ON' : 'Drag: OFF'}
                    sx={{
                      background: dragMode
                        ? '#ff9800 !important'
                        : '#e0e0e0 !important',
                    }}
                    onClick={() => sendCommand(dragMode ? 'drag_off' : 'drag_on')}
                  />
                </Stack>
              </Stack>

              {/* Enable / Reset / Clear */}
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <ColorButton
                  text="Enable"
                  color="#28a745"
                  onClick={() => sendCommand('enable')}
                />
                <ColorButton
                  text="Disable"
                  color="#9e9e9e"
                  textColor="black"
                  onClick={() => sendCommand('disable')}
                />
                <ColorButton
                  text="Reset Robot"
                  color="#ffc107"
                  textColor="black"
                  onClick={() => sendCommand('reset')}
                />
                <ColorButton
                  text="Clear Error"
                  color="#ffc107"
                  textColor="black"
                  onClick={() => sendCommand('clear')}
                />
              </Stack>

              {/* Speed + DO */}
              <Stack direction="row" spacing={4} flexWrap="wrap">
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2">Speed Ratio:</Typography>
                  <InputField
                    value={speed}
                    width={80}
                    type="number"
                    onChange={(e: any) => setSpeed(e.target.value)}
                  />
                  <Typography variant="body2">%</Typography>
                  <StdButton
                    text="Confirm"
                    onClick={() => sendCommand('speed', { val: speed })}
                  />
                </Stack>

                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2">DO Index:</Typography>
                  <InputField
                    value={doConfig.index}
                    width={50}
                    type="number"
                    onChange={(e: any) =>
                      setDoConfig({
                        ...doConfig,
                        index: Number(e.target.value) || 0,
                      })
                    }
                  />
                  <Typography variant="body2">Status:</Typography>
                  <Select
                    value={doConfig.status}
                    onChange={(e) =>
                      setDoConfig({ ...doConfig, status: e.target.value as string })
                    }
                    size="small"
                    sx={{
                      bgcolor: 'white !important',
                      color: 'black !important',
                      height: 30,
                      borderRadius: 0,
                      width: 80,
                      border: '1px solid #999',
                      fontSize: '0.8rem',
                      '& .MuiSelect-select': {
                        paddingRight: '24px !important',
                        paddingLeft: '8px',
                      },
                      '& .MuiSvgIcon-root': { color: 'black !important' },
                    }}
                    MenuProps={{
                      PaperProps: {
                        sx: {
                          bgcolor: 'white',
                          color: 'black',
                          borderRadius: 0,
                          border: '1px solid #666',
                        },
                      },
                    }}
                  >
                    <MenuItem value="On" sx={{ fontSize: '0.85rem' }}>
                      On
                    </MenuItem>
                    <MenuItem value="Off" sx={{ fontSize: '0.85rem' }}>
                      Off
                    </MenuItem>
                  </Select>
                  <StdButton
                    text="Confirm"
                    onClick={() => sendCommand('do', doConfig)}
                  />
                </Stack>
              </Stack>
            </Stack>
          </GroupBox>
        </Grid>

        {/* RIGHT: Emergency & Log */}
        <Grid item xs={12} md={4}>
          <GroupBox title="Emergency & Log">
            <Stack direction="row" spacing={2}>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 130,
                }}
              >
                <EmergencyStopButton onClick={() => sendCommand('estop')} />
                <Typography
                  variant="caption"
                  sx={{ mt: 1, color: '#ff867c', textAlign: 'center' }}
                >
                  Press to stop robot immediately
                </Typography>
              </Box>

              <Box sx={{ flexGrow: 1 }}>
                <Typography
                  variant="caption"
                  color="#aaa"
                  sx={{ mb: 0.5, display: 'block' }}
                >
                  System Log
                </Typography>
                <Box
                  sx={{
                    width: '100%',
                    height: 220,
                    bgcolor: '#1e1e1e',
                    border: '1px solid #666',
                    color: '#00e676',
                    fontFamily: 'monospace',
                    p: 1,
                    overflowY: 'auto',
                    fontSize: '0.8rem',
                  }}
                >
                  {logs.map((line, i) => (
                    <div key={i}>{line}</div>
                  ))}
                </Box>
              </Box>
            </Stack>
          </GroupBox>
        </Grid>
      </Grid>

      {/* ================ SECOND ROW ================ */}
      <Grid container spacing={3}>
        {/* LEFT: Move Function + Jog  (ให้เต็มบรรทัด) */}
        <Grid item xs={12} md={12}>
          <GroupBox title="Move Function (Cartesian & Joint)">
            <Stack spacing={2}>
              {/* Coord Inputs */}
              <Stack direction="row" spacing={4} flexWrap="wrap">
                <Stack direction="row" spacing={2} alignItems="center">
                  <Typography width={20}>X:</Typography>
                  <InputField
                    value={coords.x}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setCoords({ ...coords, x: Number(e.target.value) })
                    }
                  />
                  <Typography width={20}>Y:</Typography>
                  <InputField
                    value={coords.y}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setCoords({ ...coords, y: Number(e.target.value) })
                    }
                  />
                  <Typography width={20}>Z:</Typography>
                  <InputField
                    value={coords.z}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setCoords({ ...coords, z: Number(e.target.value) })
                    }
                  />
                  <Typography width={20}>R:</Typography>
                  <InputField
                    value={coords.r}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setCoords({ ...coords, r: Number(e.target.value) })
                    }
                  />
                </Stack>

                <Stack direction="row" spacing={2} alignItems="center">
                  <Typography width={24}>J1:</Typography>
                  <InputField
                    value={joints.j1}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setJoints({ ...joints, j1: Number(e.target.value) })
                    }
                  />
                  <Typography width={24}>J2:</Typography>
                  <InputField
                    value={joints.j2}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setJoints({ ...joints, j2: Number(e.target.value) })
                    }
                  />
                  <Typography width={24}>J3:</Typography>
                  <InputField
                    value={joints.j3}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setJoints({ ...joints, j3: Number(e.target.value) })
                    }
                  />
                  <Typography width={24}>J4:</Typography>
                  <InputField
                    value={joints.j4}
                    width={70}
                    type="number"
                    onChange={(e: any) =>
                      setJoints({ ...joints, j4: Number(e.target.value) })
                    }
                  />
                </Stack>
              </Stack>

              {/* Move Buttons */}
              <Stack direction="row" spacing={2} alignItems="center">
                <StdButton
                  text="MovJ"
                  sx={{ width: 80, height: 35 }}
                  onClick={() => sendCommand('movj')}
                />
                <StdButton
                  text="MovL"
                  sx={{ width: 80, height: 35 }}
                  onClick={() => sendCommand('movl')}
                />
                <StdButton
                  text="JointMovJ"
                  sx={{ width: 100, height: 35 }}
                  onClick={() => sendCommand('joint')}
                />
                <Box flexGrow={1} />
                <ColorButton
                  text="GO HOME"
                  color="#4fc3f7"
                  textColor="black"
                  sx={{
                    width: 130,
                    height: 40,
                    fontSize: '1rem',
                    border: '2px solid #81d4fa',
                  }}
                  onClick={() => sendCommand('home')}
                />
              </Stack>

              {/* Jog Step */}
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">Jog Step:</Typography>
                <InputField
                  value={jogStep}
                  width={60}
                  type="number"
                  onChange={(e: any) => setJogStep(e.target.value)}
                />
                <Typography variant="body2">mm / deg</Typography>
              </Stack>

              {/* Jog Panel */}
              <Grid container spacing={1} sx={{ mt: 1 }}>
                {/* Joint Jog */}
                <Grid item xs={12} md={6}>
                  <Typography
                    variant="caption"
                    color="gray"
                    sx={{ mb: 0.5, display: 'block' }}
                  >
                    Joint Jog
                  </Typography>
                  <Grid container spacing={1}>
                    {[
                      { label: 'J1-', joint: 'J1', dir: -1 as 1 | -1 },
                      { label: 'J1+', joint: 'J1', dir: 1 as 1 | -1 },
                      { label: 'J2-', joint: 'J2', dir: -1 as 1 | -1 },
                      { label: 'J2+', joint: 'J2', dir: 1 as 1 | -1 },
                      { label: 'J3-', joint: 'J3', dir: -1 as 1 | -1 },
                      { label: 'J3+', joint: 'J3', dir: 1 as 1 | -1 },
                      { label: 'J4-', joint: 'J4', dir: -1 as 1 | -1 },
                      { label: 'J4+', joint: 'J4', dir: 1 as 1 | -1 },
                    ].map((btn) => (
                      <Grid item xs={3} key={btn.label}>
                        <StdButton
                          text={btn.label}
                          sx={{ width: '100%', minWidth: 0, px: 0, height: 36 }}
                          // กดค้าง
                          onMouseDown={() => startJogJoint(btn.joint as any, btn.dir)}
                          onMouseUp={stopJog}
                          onMouseLeave={stopJog}
                          onTouchStart={() => startJogJoint(btn.joint as any, btn.dir)}
                          onTouchEnd={stopJog}
                        />
                      </Grid>
                    ))}
                  </Grid>
                </Grid>

                {/* Cartesian Jog */}
                <Grid item xs={12} md={6}>
                  <Typography
                    variant="caption"
                    color="gray"
                    sx={{ mb: 0.5, display: 'block' }}
                  >
                    Cartesian Jog
                  </Typography>
                  <Grid container spacing={1}>
                    {[
                      { label: 'X-', axis: 'X', dir: -1 as 1 | -1 },
                      { label: 'X+', axis: 'X', dir: 1 as 1 | -1 },
                      { label: 'Y-', axis: 'Y', dir: -1 as 1 | -1 },
                      { label: 'Y+', axis: 'Y', dir: 1 as 1 | -1 },
                      { label: 'Z-', axis: 'Z', dir: -1 as 1 | -1 },
                      { label: 'Z+', axis: 'Z', dir: 1 as 1 | -1 },
                      { label: 'R-', axis: 'R', dir: -1 as 1 | -1 },
                      { label: 'R+', axis: 'R', dir: 1 as 1 | -1 },
                    ].map((btn) => (
                      <Grid item xs={3} key={btn.label}>
                        <StdButton
                          text={btn.label}
                          sx={{ width: '100%', minWidth: 0, px: 0, height: 36 }}
                          onMouseDown={() =>
                            startJogCartesian(btn.axis as any, btn.dir)
                          }
                          onMouseUp={stopJog}
                          onMouseLeave={stopJog}
                          onTouchStart={() =>
                            startJogCartesian(btn.axis as any, btn.dir)
                          }
                          onTouchEnd={stopJog}
                        />
                      </Grid>
                    ))}
                  </Grid>
                </Grid>
              </Grid>
            </Stack>
          </GroupBox>
        </Grid>

        {/* RIGHT: Feedback & Error Info  (ให้เต็มบรรทัด แยกบรรทัดถัดไป) */}
        <Grid item xs={12} md={12}>
          <GroupBox title="Feedback & Error Info">
            <Box sx={{ display: 'flex', gap: 2, height: 300 }}>
              {/* Left: Pose & IO */}
              <Box sx={{ width: '55%', display: 'flex', flexDirection: 'column' }}>
                <Typography variant="body2" mb={1}>
                  Current Speed Ratio: {Number(speed) || 0} %
                </Typography>
                <Typography variant="body2" mb={1}>
                  Robot Mode: {robotMode}
                </Typography>

                <Typography variant="body2" mb={1}>
                  Pose:
                </Typography>
                <Box
                  sx={{
                    bgcolor: '#1e1e1e',
                    border: '1px solid #666',
                    p: 1,
                    mb: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    color: '#e0e0e0',
                    minHeight: 80,
                  }}
                >
                  {pose ? (
                    <>
                      X: {pose.x?.toFixed?.(2) ?? pose.x ?? '-'}{' '}
                      Y: {pose.y?.toFixed?.(2) ?? pose.y ?? '-'}{' '}
                      Z: {pose.z?.toFixed?.(2) ?? pose.z ?? '-'}{' '}
                      R: {pose.r?.toFixed?.(2) ?? pose.r ?? '-'}
                      <br />
                      J1: {pose.j1 ?? '-'} J2: {pose.j2 ?? '-'} J3:{' '}
                      {pose.j3 ?? '-'} J4: {pose.j4 ?? '-'}
                    </>
                  ) : (
                    'No pose data'
                  )}
                </Box>

                <Typography variant="body2" mb={0.5}>
                  IO State:
                </Typography>
                <Box
                  sx={{
                    bgcolor: '#1e1e1e',
                    border: '1px solid #666',
                    p: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    color: '#e0e0e0',
                    flexGrow: 1,
                  }}
                >
                  DO: {ioState.do.join(' ')}
                  <br />
                  DI: {ioState.di.join(' ')}
                </Box>
              </Box>

              {/* Right: Error Info */}
              <Box sx={{ width: '45%', display: 'flex', flexDirection: 'column' }}>
                <Typography
                  variant="caption"
                  color="#aaa"
                  sx={{ position: 'relative', top: -10, left: 10 }}
                >
                  Error / Alarm
                </Typography>
                <Box
                  sx={{
                    bgcolor: '#1e1e1e',
                    border: '1px solid #666',
                    flexGrow: 1,
                    mb: 1,
                    color: '#ff867c',
                    fontFamily: 'monospace',
                    p: 1,
                    fontSize: '0.8rem',
                    overflowY: 'auto',
                  }}
                >
                  {alarmText || 'No Error...'}
                </Box>
                <StdButton
                  text="Clear"
                  sx={{ alignSelf: 'flex-end', width: '100%' }}
                  onClick={() => sendCommand('clear')}
                />
              </Box>
            </Box>
          </GroupBox>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminPanel;
