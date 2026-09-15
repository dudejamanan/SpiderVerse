import React from 'react';
import type{ RoomConfig, TwinState } from '../types';
import { getThermalColor } from '../lib/thermal';
import { Users, Wind, Sun, Box, Cpu } from 'lucide-react';

interface RoomSchematicProps {
  room: RoomConfig;
  state?: TwinState;
  hvacPowerW: number;
}

export const RoomSchematic: React.FC<RoomSchematicProps> = ({
  room,
  state,
  hvacPowerW,
}) => {
  const temp = state?.indoor_temp_c ?? room.initial_temp_c;
  const thermal = getThermalColor(temp);
  const occupancy = state?.occupancy_count ?? room.initial_occupancy;

  const isCooling = hvacPowerW < -50;
  const isHeating = hvacPowerW > 50;
  const isActive = isCooling || isHeating;

  const vectorColor = isCooling ? '#38bdf8' : isHeating ? '#f59e0b' : '#64748b';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between select-none relative overflow-hidden">
      {/* Top Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Box className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            2D DIGITAL TWIN SCHEMATIC
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
          ZONE: {room.room_id.toUpperCase()}
        </span>
      </div>

      {/* SVG Architectural Floorplan Schematic */}
      <div className="relative w-full h-[220px] bg-[#070b12] border border-slate-800/80 rounded-lg p-2 overflow-hidden flex items-center justify-center">
        {/* Subtle Blueprint Grid Background */}
        <div
          className="absolute inset-0 opacity-15 pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(#38bdf8 1px, transparent 1px)`,
            backgroundSize: '16px 16px',
          }}
        />

        <svg width="100%" height="100%" viewBox="0 0 360 200" className="overflow-visible">
          <defs>
            {/* Airflow Particles / Vector Gradient */}
            <linearGradient id="flowGradCool" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.1" />
            </linearGradient>

            <linearGradient id="flowGradHeat" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.1" />
            </linearGradient>
          </defs>

          {/* Outer Wall Boundary */}
          <rect
            x="20"
            y="15"
            width="320"
            height="170"
            rx="6"
            fill="#0b111e"
            stroke="#334155"
            strokeWidth="3"
          />

          {/* Inner Wall Architectural Line */}
          <rect
            x="26"
            y="21"
            width="308"
            height="158"
            rx="4"
            fill="none"
            stroke="#1e293b"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />

          {/* Glass Window Segment (Top Edge) */}
          <line x1="120" y1="15" x2="240" y2="15" stroke="#38bdf8" strokeWidth="5" />
          <text x="180" y="11" fill="#38bdf8" fontSize="8" fontFamily="monospace" textAnchor="middle">
            WINDOW ({room.window_area_m2}m²)
          </text>

          {/* Door Segment (Bottom Left Edge) */}
          <line x1="50" y1="185" x2="90" y2="185" stroke="#10b981" strokeWidth="4" />
          <path d="M 50 185 A 40 40 0 0 1 90 145" fill="none" stroke="#10b981" strokeWidth="1" strokeDasharray="2 2" />
          <text x="70" y="196" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">
            ENTRY DOOR
          </text>

          {/* HVAC Supply Diffuser / Vent (Top Right) */}
          <rect x="270" y="30" width="40" height="24" rx="3" fill="#1e293b" stroke={vectorColor} strokeWidth="1.5" />
          <text x="290" y="45" fill={vectorColor} fontSize="8" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
            HVAC VENT
          </text>

          {/* Return Air Register (Bottom Right) */}
          <rect x="270" y="140" width="40" height="24" rx="3" fill="#1e293b" stroke="#475569" strokeWidth="1.5" />
          <text x="290" y="155" fill="#94a3b8" fontSize="8" fontFamily="monospace" textAnchor="middle">
            RETURN
          </text>

          {/* Occupants Representation */}
          {Array.from({ length: Math.min(occupancy, 6) }).map((_, i) => {
            const cx = 80 + (i % 3) * 35;
            const cy = 80 + Math.floor(i / 3) * 40;
            return (
              <g key={i}>
                <circle cx={cx} cy={cy} r="7" fill="#162032" stroke="#38bdf8" strokeWidth="1.5" />
                <circle cx={cx} cy={cy - 2} r="3" fill="#38bdf8" />
                <path d={`M ${cx - 5} ${cy + 5} Q ${cx} ${cy + 2} ${cx + 5} ${cy + 5}`} fill="none" stroke="#38bdf8" strokeWidth="1" />
              </g>
            );
          })}

          {/* Central Room Thermal Sensor Node */}
          <circle cx="180" cy="100" r="14" fill="#0f172a" stroke={thermal.hex} strokeWidth="2" />
          <circle cx="180" cy="100" r="4" fill={thermal.hex} />
          <text x="180" y="124" fill={thermal.hex} fontSize="10" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
            {temp.toFixed(1)}°C
          </text>

          {/* ANIMATED HEAT/COOL FLOW VECTOR LINES (Delighter) */}
          {isActive && (
            <g className="opacity-80">
              {/* Flow Vectors from Vent to Room Center */}
              <path
                d="M 270 42 C 220 50, 200 80, 180 100"
                fill="none"
                stroke={vectorColor}
                strokeWidth="3"
                strokeDasharray="8 6"
                className="animate-flow-dash"
              />
              <path
                d="M 270 42 C 240 90, 220 120, 180 100"
                fill="none"
                stroke={vectorColor}
                strokeWidth="2"
                strokeDasharray="6 4"
                className="animate-flow-dash"
              />
              <path
                d="M 180 100 C 220 120, 250 140, 270 152"
                fill="none"
                stroke="#475569"
                strokeWidth="2"
                strokeDasharray="6 4"
                className="animate-flow-dash"
              />
            </g>
          )}
        </svg>
      </div>

      {/* Room Physical Parameters Footer */}
      <div className="grid grid-cols-4 gap-2 mt-3 pt-2.5 border-t border-slate-800 text-[11px] font-mono text-slate-400 text-center">
        <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800">
          <span className="text-[9px] text-slate-500 uppercase block">AREA / HT</span>
          <span className="text-slate-200 font-semibold">{room.area_m2}m² / {room.height_m}m</span>
        </div>
        <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800">
          <span className="text-[9px] text-slate-500 uppercase block">THERMAL R/C</span>
          <span className="text-slate-200 font-semibold">{room.R} / {(room.C / 1000).toFixed(0)}k</span>
        </div>
        <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800">
          <span className="text-[9px] text-slate-500 uppercase block">HVAC CAP</span>
          <span className="text-cyan-400 font-semibold">{(room.hvac_capacity_w / 1000).toFixed(1)} kW</span>
        </div>
        <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800">
          <span className="text-[9px] text-slate-500 uppercase block">COP RATING</span>
          <span className="text-emerald-400 font-semibold">{room.cop}x</span>
        </div>
      </div>
    </div>
  );
};
