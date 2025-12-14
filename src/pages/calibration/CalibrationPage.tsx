/* eslint-disable @typescript-eslint/consistent-type-definitions */
import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Grid,
  Paper,
  Stack,
  TextField,
  Typography,
  Chip,
  LinearProgress,
} from "@mui/material";
import { API_ENDPOINTS } from "config/api";

// -------------------- Types --------------------
type Zone = {
  id: number;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  color: string;
};

type CalibPoint = {
  name: string; // "P1" | "P2" | "P3" | "P4" | "C"
  camX: number;
  camY: number;
  robX: number;
  robY: number;
};

type CalibPointsState = {
  [zoneId: number]: CalibPoint[];
};

type AffineParams = {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
};

type AffineRecord = {
  params: AffineParams;
  residual: number;
  timestamp?: string;
};

type AffineResult = {
  params: AffineParams;
  residual: number;
};

// -------------------- Constants --------------------
const VIDEO_W = 1280;
const VIDEO_H = 720;
const baseDisplayWidth = 960;

// ค่าเริ่มต้น
const DEFAULT_ZONES: Zone[] = [
  { id: 1, name: "Zone 1 (Green)", x: 50, y: 50, w: 200, h: 200, z: 0, color: "#00e676" },
  { id: 2, name: "Zone 2 (Yellow)", x: 300, y: 50, w: 200, h: 200, z: 0, color: "#ffca28" },
  { id: 3, name: "Zone 3 (Red)", x: 550, y: 50, w: 200, h: 200, z: 0, color: "#f44336" },
];

const createDefaultCalibPoints = (zonesInit: Zone[]): CalibPointsState => {
  const obj: CalibPointsState = {};
  zonesInit.forEach((z) => {
    obj[z.id] = [
      { name: "P1", camX: 0, camY: 0, robX: 0, robY: 0 },
      { name: "P2", camX: 0, camY: 0, robX: 0, robY: 0 },
      { name: "P3", camX: 0, camY: 0, robX: 0, robY: 0 },
      { name: "P4", camX: 0, camY: 0, robX: 0, robY: 0 },
      { name: "C", camX: 0, camY: 0, robX: 0, robY: 0 },
    ];
  });
  return obj;
};

// สีเตือน residual
const getResidualStatus = (res: number | null | undefined) => {
  if (res == null || Number.isNaN(res)) return { label: "N/A", color: "default" as const };
  if (res <= 1.0) return { label: `OK (${res.toFixed(2)} mm)`, color: "success" as const };
  if (res <= 3.0) return { label: `WARN (${res.toFixed(2)} mm)`, color: "warning" as const };
  return { label: `HIGH (${res.toFixed(2)} mm)`, color: "error" as const };
};

// -------------------- Component --------------------
const CalibrationPage: React.FC = () => {
  const [zones, setZones] = useState<Zone[]>(DEFAULT_ZONES);
  const [selectedZoneId, setSelectedZoneId] = useState<number>(1);
  const [status, setStatus] = useState<string>("Connecting...");
  const containerRef = useRef<HTMLDivElement | null>(null);

  // drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);

  const [displaySize, setDisplaySize] = useState<{ w: number; h: number }>({
    w: baseDisplayWidth,
    h: Math.round((baseDisplayWidth * VIDEO_H) / VIDEO_W),
  });

  // 5-point calibration per zone
  const [calibPoints, setCalibPoints] = useState<CalibPointsState>(() =>
    createDefaultCalibPoints(DEFAULT_ZONES)
  );

  // affine compute result (ล่าสุดใน UI ตอนนี้)
  const [affineResult, setAffineResult] = useState<AffineResult | null>(null);
  const [isComputing, setIsComputing] = useState(false);

  // ✅ Residual history per zone (ไว้ใช้วาด mini-graph / table)
  const [zoneResiduals, setZoneResiduals] = useState<{
    [zoneId: number]: { residual: number; timestamp: string }[];
  }>({});

  // ✅ Matrix ที่ save อยู่ใน server ปัจจุบัน (จาก AFFINE_FILE)
  const [serverAffine, setServerAffine] = useState<{ [zoneId: number]: AffineRecord }>({});

  // ---------------- API: Load zones ----------------
  useEffect(() => {
    fetch(API_ENDPOINTS.calibrationZones)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setZones(data);
        }
        setStatus("Ready to Calibrate");
      })
      .catch(() => {
        setStatus("Error: Cannot connect to Python");
      });
  }, []);

  // ---------------- API: Load saved affine map ----------------
  const refreshServerAffine = () => {
    fetch(API_ENDPOINTS.calibrationAffine)
      .then((r) => r.json())
      .then((data) => {
        // data = { "1": {params,residual,timestamp}, ... }
        const mapped: { [zoneId: number]: AffineRecord } = {};
        Object.entries(data || {}).forEach(([zid, rec]) => {
          const znum = Number(zid);
          if (!Number.isNaN(znum) && rec && typeof rec === "object") {
            const r = rec as {
              params?: AffineParams;
              residual?: number;
              timestamp?: string;
            };
            if (r.params) {
              mapped[znum] = {
                params: r.params,
                residual: typeof r.residual === "number" ? r.residual : 0,
                timestamp: r.timestamp,
              };
            }
          }
        });
        setServerAffine(mapped);
      })
      .catch(() => {
        // เงียบๆ ไป ไม่ต้อง alert
      });
  };

  useEffect(() => {
    refreshServerAffine();
  }, []);

  // ---------------- Update display size on resize ----------------
  useEffect(() => {
    const updateSize = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const w = Math.max(200, Math.min(rect.width, baseDisplayWidth));
      const h = Math.round((w * VIDEO_H) / VIDEO_W);
      setDisplaySize({ w, h });
    };

    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Helper: Client -> Video Coords
  const clientToVideoCoords = (clientX: number, clientY: number) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    const localX = clientX - rect.left;
    const localY = clientY - rect.top;
    const scaleX = VIDEO_W / rect.width;
    const scaleY = VIDEO_H / rect.height;
    return {
      x: Math.max(0, Math.min(VIDEO_W, Math.round(localX * scaleX))),
      y: Math.max(0, Math.min(VIDEO_H, Math.round(localY * scaleY))),
    };
  };

  // Mouse Events สำหรับลากโซน
  const handleMouseDown = (e: React.MouseEvent) => {
    const pos = clientToVideoCoords(e.clientX, e.clientY);
    setIsDrawing(true);
    setStartPos(pos);
    setZones((prev) =>
      prev.map((z) => (z.id === selectedZoneId ? { ...z, x: pos.x, y: pos.y, w: 0, h: 0 } : z))
    );
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDrawing || !startPos) return;
    const current = clientToVideoCoords(e.clientX, e.clientY);
    const x = Math.min(startPos.x, current.x);
    const y = Math.min(startPos.y, current.y);
    const w = Math.abs(current.x - startPos.x);
    const h = Math.abs(current.y - startPos.y);
    setZones((prev) => prev.map((z) => (z.id === selectedZoneId ? { ...z, x, y, w, h } : z)));
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
    setStartPos(null);
  };

  // Update Zone Inputs
  const updateZoneField = (id: number, field: keyof Zone, value: number | string) => {
    const numericFields: (keyof Zone)[] = ["x", "y", "w", "h", "z"];
    setZones((prev) =>
      prev.map((z) => {
        if (z.id !== id) return z;
        const isNumeric = numericFields.includes(field);
        const newValue = isNumeric ? Number(value) || 0 : String(value);
        return {
          ...z,
          [field]: newValue,
        } as Zone;
      })
    );
  };

  const handleSaveZones = async () => {
    try {
      await fetch(API_ENDPOINTS.calibrationZones, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(zones),
      });
      alert("Zones Saved!");
    } catch (err) {
      alert("Save failed");
    }
  };

  const handleResetZones = () => {
    if (window.confirm("Reset all zones to default settings?")) {
      setZones(DEFAULT_ZONES);
    }
  };

  // ----- Calibration 5 points handlers -----
  const handleCalibFieldChange = (
    zoneId: number,
    index: number,
    field: keyof CalibPoint,
    value: string
  ) => {
    setCalibPoints((prev) => {
      const copy: CalibPointsState = { ...prev };
      const arr = copy[zoneId] ? [...copy[zoneId]] : [];
      if (!arr[index]) return prev;

      const numericFields: (keyof CalibPoint)[] = ["camX", "camY", "robX", "robY"];
      const isNumeric = numericFields.includes(field);
      const v: CalibPoint[keyof CalibPoint] = isNumeric
        ? (Number(value) as CalibPoint[keyof CalibPoint])
        : (value as CalibPoint[keyof CalibPoint]);

      arr[index] = {
        ...arr[index],
        [field]: v,
      };
      copy[zoneId] = arr;
      return copy;
    });
  };

  // ใช้ center ของโซนเป็น cam ของ C
  const handleUseZoneCenterAsC = () => {
    const zone = zones.find((z) => z.id === selectedZoneId);
    if (!zone) return;

    const cx = Math.round(zone.x + zone.w / 2);
    const cy = Math.round(zone.y + zone.h / 2);

    setCalibPoints((prev) => {
      const copy: CalibPointsState = { ...prev };
      const arr = copy[selectedZoneId] ? [...copy[selectedZoneId]] : [];
      const idx = arr.findIndex((p) => p.name === "C");
      if (idx !== -1) {
        arr[idx] = { ...arr[idx], camX: cx, camY: cy };
      }
      copy[selectedZoneId] = arr;
      return copy;
    });
  };

  // ✅ Auto Fill C จากตำแหน่งแขนกล (Robot XY -> robX/robY)
  const handleFillCFromRobot = async () => {
    try {
      const res = await fetch(API_ENDPOINTS.robotPosition);
      const data = await res.json();
      if (data.status !== "success") {
        alert("Cannot read robot pose");
        return;
      }
      const { x, y } = data as { x: number; y: number; status: string };
      setCalibPoints((prev) => {
        const copy: CalibPointsState = { ...prev };
        const arr = copy[selectedZoneId] ? [...copy[selectedZoneId]] : [];
        const idx = arr.findIndex((p) => p.name === "C");
        if (idx !== -1) {
          arr[idx] = { ...arr[idx], robX: x, robY: y };
        }
        copy[selectedZoneId] = arr;
        return copy;
      });
      alert(`Loaded robot XY into C: (${x.toFixed(2)}, ${y.toFixed(2)})`);
    } catch {
      alert("Error reading robot pose");
    }
  };

  // ---------------- Compute Affine (only compute) ----------------
  const callAffineCompute = async (zoneId: number) => {
    const points = calibPoints[zoneId] || [];
    const pairs = points.map((p) => ({
      cam: { x: p.camX, y: p.camY },
      robot: { x: p.robX, y: p.robY },
    }));

    const res = await fetch(API_ENDPOINTS.calibrationAffineCompute, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pairs }),
    });

    const data = await res.json();
    if (!data.params) {
      throw new Error(data.error || "Affine compute failed");
    }

    const result: AffineResult = {
      params: data.params,
      residual: data.residual ?? 0,
    };
    return result;
  };

  const handleComputeAffine = async () => {
    try {
      setIsComputing(true);
      const result = await callAffineCompute(selectedZoneId);
      setAffineResult(result);
      alert(`Compute Success – residual = ${result.residual.toFixed(3)} mm`);
    } catch (err) {
      alert(`Compute failed: ${(err as Error).message}`);
    } finally {
      setIsComputing(false);
    }
  };

  // ✅ Auto Calculate + Save + Sync Robot
  const handleAutoCalcAndSave = async () => {
    try {
      setIsComputing(true);
      const result = await callAffineCompute(selectedZoneId);
      setAffineResult(result);

      // 1) Save matrix ลง server
      await fetch(API_ENDPOINTS.calibrationAffine, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zone_id: selectedZoneId,
          params: result.params,
          residual: result.residual,
        }),
      });

      // 2) Sync matrix ลง Robot
      await fetch(API_ENDPOINTS.robotSyncAffine(selectedZoneId), {
        method: "POST",
      }).catch(() => {});

      // 3) update residual history
      setZoneResiduals((prev) => ({
        ...prev,
        [selectedZoneId]: [
          ...(prev[selectedZoneId] || []),
          { residual: result.residual, timestamp: new Date().toISOString() },
        ],
      }));

      // 4) refresh matrix ที่ save อยู่บน server
      refreshServerAffine();

      alert("✅ Auto Calculate + Save + Sync Robot Success");
    } catch (err) {
      alert(`Auto Calc + Save failed: ${(err as Error).message}`);
    } finally {
      setIsComputing(false);
    }
  };

  // ✅ Test Residual Only
  const handleTestResidual = async () => {
    try {
      const result = await callAffineCompute(selectedZoneId);

      setZoneResiduals((prev) => ({
        ...prev,
        [selectedZoneId]: [
          ...(prev[selectedZoneId] || []),
          { residual: result.residual, timestamp: new Date().toISOString() },
        ],
      }));

      alert(`🎯 Test Residual = ${result.residual.toFixed(3)} mm`);
    } catch (err) {
      alert(`Test residual failed: ${(err as Error).message}`);
    }
  };

  const currentZone = zones.find((z) => z.id === selectedZoneId);
  const currentPoints = calibPoints[selectedZoneId] || [];
  const savedAffine = serverAffine[selectedZoneId] || null;
  const lastResidual =
    zoneResiduals[selectedZoneId]?.[zoneResiduals[selectedZoneId].length - 1]?.residual ??
    savedAffine?.residual ??
    null;

  const residualStatus = getResidualStatus(lastResidual);

  return (
    <Box sx={{ p: 3, color: "white", minHeight: "100vh", bgcolor: "#0a0a0a" }}>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" color="#00d4ff" fontWeight="bold">
          Zone & Affine Calibration
        </Typography>
        <Stack direction="row" spacing={2} alignItems="center">
          <Chip
            label={residualStatus.label}
            color={residualStatus.color}
            size="small"
            sx={{ fontWeight: "bold" }}
          />
          <Typography color={status.includes("Error") ? "error" : "success.main"}>
            {status}
          </Typography>
        </Stack>
      </Stack>

      {/* Top: Camera Feed */}
      <Box display="flex" justifyContent="center" mb={4}>
        <Paper sx={{ p: 1.5, bgcolor: "#1e1e1e", border: "1px solid #444", width: "fit-content" }}>
          <Typography variant="caption" color="gray" mb={1} display="block">
            1. Select a zone below. 2. Drag on image to set area. 3. Use 5-point calibration to map
            camera → robot.
          </Typography>

          <div
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            style={{
              position: "relative",
              width: displaySize.w,
              height: displaySize.h,
              maxWidth: "100%",
              backgroundColor: "black",
              cursor: "crosshair",
              overflow: "hidden",
              borderRadius: 8,
            }}
          >
            <img
              src={API_ENDPOINTS.videoFeed}
              alt="Camera Feed"
              width={displaySize.w}
              height={displaySize.h}
              draggable={false}
              style={{
                display: "block",
                userSelect: "none",
                pointerEvents: "none",
                objectFit: "cover",
              }}
            />

            <svg
              viewBox={`0 0 ${VIDEO_W} ${VIDEO_H}`}
              width={displaySize.w}
              height={displaySize.h}
              style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
            >
              {zones.map((z) => {
                const isSelected = z.id === selectedZoneId;
                return (
                  <g key={z.id}>
                    <rect
                      x={z.x}
                      y={z.y}
                      width={Math.max(0, z.w)}
                      height={Math.max(0, z.h)}
                      fill={isSelected ? `${z.color}44` : "transparent"}
                      stroke={z.color}
                      strokeWidth={isSelected ? 6 : 3}
                      strokeDasharray={isSelected ? "0" : "6,6"}
                      rx={6}
                      ry={6}
                    />
                    <text
                      x={z.x + 8}
                      y={z.y + 22}
                      fill={z.color}
                      fontWeight="bold"
                      fontSize={18}
                      style={{ textShadow: "1px 1px 2px black" }}
                    >
                      {`${z.name} (Z:${z.z})`}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </Paper>
      </Box>

      {/* Bottom: Zone Settings */}
      <Typography variant="h6" color="white" mb={2}>
        Zone Settings
      </Typography>

      <Grid container spacing={3} alignItems="stretch">
        {zones.map((z) => (
          <Grid item xs={12} md={4} key={z.id}>
            <Paper
              onClick={() => setSelectedZoneId(z.id)}
              sx={{
                p: 2.5,
                height: "100%",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                bgcolor: selectedZoneId === z.id ? "#2a2a2a" : "#151515",
                border: selectedZoneId === z.id ? `2px solid ${z.color}` : "1px solid #2c2c2c",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
              elevation={0}
            >
              <Stack direction="row" spacing={2} alignItems="center">
                <Box
                  sx={{
                    width: 28,
                    height: 28,
                    bgcolor: z.color,
                    borderRadius: "50%",
                    border: "2px solid rgba(255,255,255,0.12)",
                    flexShrink: 0,
                  }}
                />
                <Box>
                  <Typography variant="h6" color="white">
                    {z.name}
                  </Typography>
                  <Typography variant="caption" color="gray">
                    Click card to select, then drag on image to edit area
                  </Typography>
                </Box>
              </Stack>

              <Box sx={{ mt: 2 }}>
                <TextField
                  label="Base Height (Z mm)"
                  size="small"
                  type="number"
                  value={z.z}
                  onChange={(e) => {
                    e.stopPropagation();
                    updateZoneField(z.id, "z", Number(e.target.value));
                  }}
                  fullWidth
                  inputProps={{ min: -10000, max: 10000 }}
                  sx={{
                    "& .MuiInputBase-input": { color: "white" },
                    "& .MuiInputLabel-root": { color: "gray" },
                    bgcolor: "#000",
                    borderRadius: 1,
                  }}
                />

                <Grid container spacing={1} sx={{ mt: 1 }}>
                  <Grid item xs={6}>
                    <TextField
                      label="X"
                      size="small"
                      type="number"
                      value={Math.round(z.x)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateZoneField(z.id, "x", Number(e.target.value))}
                      fullWidth
                      sx={{
                        "& .MuiInputBase-input": { color: "white" },
                        "& .MuiInputLabel-root": { color: "gray" },
                      }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="Y"
                      size="small"
                      type="number"
                      value={Math.round(z.y)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateZoneField(z.id, "y", Number(e.target.value))}
                      fullWidth
                      sx={{
                        "& .MuiInputBase-input": { color: "white" },
                        "& .MuiInputLabel-root": { color: "gray" },
                      }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="W"
                      size="small"
                      type="number"
                      value={Math.round(z.w)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateZoneField(z.id, "w", Number(e.target.value))}
                      fullWidth
                      sx={{
                        "& .MuiInputBase-input": { color: "white" },
                        "& .MuiInputLabel-root": { color: "gray" },
                      }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="H"
                      size="small"
                      type="number"
                      value={Math.round(z.h)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateZoneField(z.id, "h", Number(e.target.value))}
                      fullWidth
                      sx={{
                        "& .MuiInputBase-input": { color: "white" },
                        "& .MuiInputLabel-root": { color: "gray" },
                      }}
                    />
                  </Grid>
                </Grid>

                <Typography variant="caption" color="gray" sx={{ display: "block", mt: 1 }}>
                  Area: X={Math.round(z.x)}, Y={Math.round(z.y)}, W={Math.round(z.w)}, H=
                  {Math.round(z.h)}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Divider sx={{ borderColor: "#444", my: 4 }} />

      {/* Zone buttons */}
      <Stack direction="row" spacing={2} mb={4}>
        <Button
          variant="outlined"
          size="large"
          onClick={handleResetZones}
          fullWidth
          sx={{
            borderColor: "#ff9800",
            color: "#ff9800",
            fontWeight: "bold",
            height: 55,
            fontSize: "1.05rem",
            "&:hover": { borderColor: "#ffb74d", bgcolor: "rgba(255, 152, 0, 0.1)" },
          }}
        >
          RESET DEFAULTS
        </Button>

        <Button
          variant="contained"
          size="large"
          fullWidth
          onClick={handleSaveZones}
          sx={{
            bgcolor: "#00e676",
            color: "black",
            fontWeight: "bold",
            height: 55,
            fontSize: "1.05rem",
            "&:hover": { bgcolor: "#00c853" },
          }}
        >
          SAVE & APPLY ZONES
        </Button>
      </Stack>

      {/* ================== Affine Calibration (5 points) ================== */}
      <Typography variant="h6" color="white" mb={1}>
        Affine Calibration (5 points per zone)
      </Typography>
      <Typography variant="body2" color="gray" mb={2}>
        Use P1–P4 + C to fit linear mapping from camera (px) → robot (mm). C is usually the center
        of zone, with robot TCP positioned at AprilTag center.
      </Typography>

      <Grid container spacing={3} alignItems="flex-start">
        {/* Left: Table & Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2.5, bgcolor: "#111", border: "1px solid #333" }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="subtitle1" color="#00e5ff">
                Zone {selectedZoneId} – 5-point calibration
              </Typography>
              {currentZone && (
                <Typography variant="caption" color="gray">
                  Zone area: X={Math.round(currentZone.x)}, Y={Math.round(currentZone.y)}, W=
                  {Math.round(currentZone.w)}, H={Math.round(currentZone.h)}
                </Typography>
              )}
            </Stack>

            {/* Table header */}
            <Grid container spacing={1} sx={{ mb: 1 }}>
              <Grid item xs={2}>
                <Typography variant="caption" color="gray">
                  Point
                </Typography>
              </Grid>
              <Grid item xs={2}>
                <Typography variant="caption" color="gray">
                  Cam X (px)
                </Typography>
              </Grid>
              <Grid item xs={2}>
                <Typography variant="caption" color="gray">
                  Cam Y (px)
                </Typography>
              </Grid>
              <Grid item xs={3}>
                <Typography variant="caption" color="gray">
                  Robot X (mm)
                </Typography>
              </Grid>
              <Grid item xs={3}>
                <Typography variant="caption" color="gray">
                  Robot Y (mm)
                </Typography>
              </Grid>
            </Grid>

            {/* Rows */}
            {currentPoints.map((p, idx) => (
              <Grid container spacing={1} key={p.name} sx={{ mt: 0.5 }}>
                <Grid item xs={2}>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {p.name}
                  </Typography>
                </Grid>
                <Grid item xs={2}>
                  <TextField
                    size="small"
                    type="number"
                    value={p.camX}
                    onChange={(e) =>
                      handleCalibFieldChange(selectedZoneId, idx, "camX", e.target.value)
                    }
                    fullWidth
                    sx={{
                      "& .MuiInputBase-input": { color: "white", fontSize: 13 },
                      "& .MuiInputLabel-root": { color: "gray" },
                    }}
                  />
                </Grid>
                <Grid item xs={2}>
                  <TextField
                    size="small"
                    type="number"
                    value={p.camY}
                    onChange={(e) =>
                      handleCalibFieldChange(selectedZoneId, idx, "camY", e.target.value)
                    }
                    fullWidth
                    sx={{
                      "& .MuiInputBase-input": { color: "white", fontSize: 13 },
                      "& .MuiInputLabel-root": { color: "gray" },
                    }}
                  />
                </Grid>
                <Grid item xs={3}>
                  <TextField
                    size="small"
                    type="number"
                    value={p.robX}
                    onChange={(e) =>
                      handleCalibFieldChange(selectedZoneId, idx, "robX", e.target.value)
                    }
                    fullWidth
                    sx={{
                      "& .MuiInputBase-input": { color: "white", fontSize: 13 },
                      "& .MuiInputLabel-root": { color: "gray" },
                    }}
                  />
                </Grid>
                <Grid item xs={3}>
                  <TextField
                    size="small"
                    type="number"
                    value={p.robY}
                    onChange={(e) =>
                      handleCalibFieldChange(selectedZoneId, idx, "robY", e.target.value)
                    }
                    fullWidth
                    sx={{
                      "& .MuiInputBase-input": { color: "white", fontSize: 13 },
                      "& .MuiInputLabel-root": { color: "gray" },
                    }}
                  />
                </Grid>
              </Grid>
            ))}

            {/* Buttons */}
            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} mt={3}>
              <Button variant="outlined" onClick={handleUseZoneCenterAsC}>
                Set C.cam = Zone Center
              </Button>
              <Button variant="outlined" onClick={handleFillCFromRobot}>
                Read Robot XY → C.rob
              </Button>
              <Button
                variant="contained"
                color="info"
                onClick={handleComputeAffine}
                disabled={isComputing}
              >
                {isComputing ? "Computing..." : "Compute Only"}
              </Button>
              <Button
                variant="contained"
                color="success"
                onClick={handleAutoCalcAndSave}
                disabled={isComputing}
              >
                {isComputing ? "Saving..." : "Auto Calc + Save & Sync"}
              </Button>
              <Button variant="contained" color="secondary" onClick={handleTestResidual}>
                Test Residual
              </Button>
            </Stack>

            {affineResult && (
              <Box sx={{ mt: 2, p: 2, bgcolor: "#181818", borderRadius: 1 }}>
                <Typography variant="subtitle2" color="#00e5ff" gutterBottom>
                  Latest computed (not necessarily saved)
                </Typography>
                <Typography variant="body2">
                  a: {affineResult.params.a.toFixed(6)}&nbsp;&nbsp;
                  b: {affineResult.params.b.toFixed(6)}&nbsp;&nbsp;
                  c: {affineResult.params.c.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  d: {affineResult.params.d.toFixed(6)}&nbsp;&nbsp;
                  e: {affineResult.params.e.toFixed(6)}&nbsp;&nbsp;
                  f: {affineResult.params.f.toFixed(3)}
                </Typography>
                <Typography variant="caption" color="orange">
                  Residual: {affineResult.residual.toFixed(3)} mm
                </Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* ================= Dashboard Panels (moved under table) ================= */}
        <Grid item xs={12}>
          <Grid container spacing={2}>
            {/* Matrix Compare */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: "#111", border: "1px solid #333", height: "100%" }}>
                <Typography variant="subtitle1" color="#00e5ff" gutterBottom>
                  Matrix Compare (Saved vs Latest)
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="gray">
                      Saved on Server
                    </Typography>
                    {savedAffine ? (
                      <Box sx={{ mt: 1 }}>
                        <Typography variant="body2">
                          a: {savedAffine.params.a.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          b: {savedAffine.params.b.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          c: {savedAffine.params.c.toFixed(3)}
                        </Typography>
                        <Typography variant="body2">
                          d: {savedAffine.params.d.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          e: {savedAffine.params.e.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          f: {savedAffine.params.f.toFixed(3)}
                        </Typography>
                        <Typography variant="caption" color="orange">
                          residual: {savedAffine.residual.toFixed(3)} mm
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="body2" color="gray" sx={{ mt: 1 }}>
                        No matrix saved for this zone yet.
                      </Typography>
                    )}
                  </Grid>

                  <Grid item xs={6}>
                    <Typography variant="caption" color="gray">
                      Latest Computed (UI)
                    </Typography>
                    {affineResult ? (
                      <Box sx={{ mt: 1 }}>
                        <Typography variant="body2">
                          a: {affineResult.params.a.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          b: {affineResult.params.b.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          c: {affineResult.params.c.toFixed(3)}
                        </Typography>
                        <Typography variant="body2">
                          d: {affineResult.params.d.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          e: {affineResult.params.e.toFixed(6)}
                        </Typography>
                        <Typography variant="body2">
                          f: {affineResult.params.f.toFixed(3)}
                        </Typography>
                        <Typography variant="caption" color="orange">
                          residual: {affineResult.residual.toFixed(3)} mm
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="body2" color="gray" sx={{ mt: 1 }}>
                        No computation yet.
                      </Typography>
                    )}
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Residual mini-graph */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: "#111", border: "1px solid #333", height: "100%" }}>
                <Typography variant="subtitle1" color="#00e5ff" gutterBottom>
                  Residual Trend – Zone {selectedZoneId}
                </Typography>
                <Typography variant="caption" color="gray">
                  Last 10 measurements
                </Typography>

                <Box sx={{ mt: 1 }}>
                  {(zoneResiduals[selectedZoneId] || [])
                    .slice(-10)
                    .map((r, idx, arr) => {
                      const maxRes =
                        arr.length > 0 ? Math.max(...arr.map((x) => x.residual), 1) : 1;
                      const percent = Math.min(100, (r.residual / maxRes) * 100);
                      const level = getResidualStatus(r.residual);
                      return (
                        <Box key={`${r.timestamp}-${idx}`} sx={{ mb: 0.5 }}>
                          <Stack
                            direction="row"
                            justifyContent="space-between"
                            alignItems="center"
                            spacing={1}
                          >
                            <Typography variant="caption" color="gray">
                              {new Date(r.timestamp).toLocaleTimeString()}
                            </Typography>
                            <Typography variant="caption" color="gray">
                              {r.residual.toFixed(2)} mm
                            </Typography>
                          </Stack>
                          <LinearProgress
                            variant="determinate"
                            value={percent}
                            sx={{
                              height: 6,
                              borderRadius: 999,
                              mt: 0.5,
                              "& .MuiLinearProgress-bar": {
                                backgroundColor:
                                  level.color === "success"
                                    ? "#00e676"
                                    : level.color === "warning"
                                    ? "#ffca28"
                                    : "#f44336",
                              },
                            }}
                          />
                        </Box>
                      );
                    })}
                  {(zoneResiduals[selectedZoneId] || []).length === 0 && (
                    <Typography variant="body2" color="gray" sx={{ mt: 1 }}>
                      No residual history yet for this zone.
                    </Typography>
                  )}
                </Box>
              </Paper>
            </Grid>

            {/* Industrial dashboard – per zone overview */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: "#111", border: "1px solid #333", height: "100%" }}>
                <Typography variant="subtitle1" color="#00e5ff" gutterBottom>
                  Zone Error Overview
                </Typography>
                <Grid container spacing={1}>
                  {zones.map((z) => {
                    const saved = serverAffine[z.id];
                    const hist = zoneResiduals[z.id] || [];
                    const latest =
                      hist.length > 0 ? hist[hist.length - 1].residual : saved?.residual ?? null;
                    const st = getResidualStatus(latest);
                    return (
                      <Grid item xs={12} key={z.id}>
                        <Paper
                          sx={{
                            p: 1.5,
                            bgcolor: "#151515",
                            border: "1px solid #333",
                          }}
                          elevation={0}
                        >
                          <Typography variant="body2" color={z.color} fontWeight="bold">
                            {z.name}
                          </Typography>
                          <Typography variant="caption" color="gray">
                            Latest residual:
                          </Typography>
                          <Typography variant="body2">
                            {latest != null ? `${latest.toFixed(3)} mm` : "N/A"}
                          </Typography>
                          <Chip
                            size="small"
                            label={st.label}
                            color={st.color}
                            sx={{ mt: 0.5, fontSize: 11 }}
                          />
                        </Paper>
                      </Grid>
                    );
                  })}
                </Grid>
              </Paper>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CalibrationPage;
