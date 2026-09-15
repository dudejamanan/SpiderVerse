import React from 'react';
import { getThermalColor, formatTemp } from '../lib/thermal';
import { Thermometer, Target, Wind, Zap } from 'lucide-react';

interface ThermalGaugeProps {
  currentTempC: number;
  setpointC: number;
  hvacPowerW: number;
  minTemp?: number;
  maxTemp?: number;
}

export const ThermalGauge: React.FC<ThermalGaugeProps> = ({
  currentTempC,
  setpointC,
  hvacPowerW,
  minTemp = 16.0,
  maxTemp = 32.0,
}) => {
  const thermal = getThermalColor(currentTempC);

  // SVG Gauge calculations
  const size = 260;
  const strokeWidth = 14;
  const center = size / 2;
  const radius = (size - strokeWidth * 2) / 2;
  
  // Angle arc from -210deg to +30deg (240 deg total arc)
  const startAngle = -210;
  const totalAngle = 240;

  const tempToAngle = (temp: number) => {
    const clamped = Math.max(minTemp, Math.min(maxTemp, temp));
    const ratio = (clamped - minTemp) / (maxTemp - minTemp);
    return startAngle + ratio * totalAngle;
  };

  const polarToCartesian = (cx: number, cy: number, r: number, angleInDegrees: number) => {
    const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
    return {
      x: cx + r * Math.cos(angleInRadians),
      y: cy + r * Math.sin(angleInRadians),
    };
  };

  const describeArc = (cx: number, cy: number, r: number, startA: number, endA: number) => {
    const start = polarToCartesian(cx, cy, r, endA);
    const end = polarToCartesian(cx, cy, r, startA);
    const largeArcFlag = endA - startA <= 180 ? '0' : '1';
    return ['M', start.x, start.y, 'A', r, r, 0, largeArcFlag, 0, end.x, end.y].join(' ');
  };

  // Current Needle Angle
  const currentAngle = tempToAngle(currentTempC);
  const currentPos = polarToCartesian(center, center, radius, currentAngle);

  // Setpoint Marker Position
  const setpointAngle = tempToAngle(setpointC);
  const setpointPos = polarToCartesian(center, center, radius + 4, setpointAngle);
  const setpointInner = polarToCartesian(center, center, radius - 14, setpointAngle);

  // Comfort Band Arc (21°C to 24°C)
  const comfortStartAngle = tempToAngle(21.0);
  const comfortEndAngle = tempToAngle(24.0);
  const comfortArcPath = describeArc(center, center, radius, comfortStartAngle, comfortEndAngle);

  // Background Arc Path
  const bgArcPath = describeArc(center, center, radius, startAngle, startAngle + totalAngle);

  // Deviation
  const delta = currentTempC - setpointC;

  // HVAC mode
  const isCooling = hvacPowerW < -50;
  const isHeating = hvacPowerW > 50;
  const hvacMode = isCooling ? 'COOLING DRIVE' : isHeating ? 'HEATING DRIVE' : 'THERMAL EQUILIBRIUM';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col items-center justify-center relative overflow-hidden select-none">
      {/* Top Header Badge */}
      <div className="w-full flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <Thermometer className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            THERMAL TELEMETRY GAUGE
          </span>
        </div>
        <span
          className={`text-[10px] font-mono px-2 py-0.5 rounded border font-semibold ${thermal.badgeBg} ${thermal.badgeText} ${thermal.badgeBorder}`}
        >
          {thermal.label}
        </span>
      </div>

      {/* SVG Arc Instrument Dial */}
      <div className="relative my-2">
        <svg width={size} height={size - 25} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
          <defs>
            {/* Thermal Gradient Arc */}
            <linearGradient id="thermalArcGrad" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" />    {/* Cryo cyan */}
              <stop offset="35%" stopColor="#10b981" />   {/* Emerald comfort */}
              <stop offset="70%" stopColor="#f59e0b" />   {/* Amber */}
              <stop offset="100%" stopColor="#ef4444" />  {/* Red inferno */}
            </linearGradient>

            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Track Arc */}
          <path
            d={bgArcPath}
            fill="none"
            stroke="#1e293b"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Comfort Band Highlight Glow (21°C - 24°C) */}
          <path
            d={comfortArcPath}
            fill="none"
            stroke="#10b981"
            strokeWidth={strokeWidth + 4}
            strokeOpacity="0.25"
            strokeLinecap="round"
          />

          {/* Active Gradient Arc Track */}
          <path
            d={bgArcPath}
            fill="none"
            stroke="url(#thermalArcGrad)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            opacity="0.85"
          />

          {/* Tick Marks along arc */}
          {[16, 18, 20, 22, 24, 26, 28, 30, 32].map((t) => {
            const angle = tempToAngle(t);
            const outer = polarToCartesian(center, center, radius + 10, angle);
            const inner = polarToCartesian(center, center, radius + 4, angle);
            return (
              <g key={t}>
                <line
                  x1={inner.x}
                  y1={inner.y}
                  x2={outer.x}
                  y2={outer.y}
                  stroke="#475569"
                  strokeWidth={1.5}
                />
                <text
                  x={polarToCartesian(center, center, radius + 22, angle).x}
                  y={polarToCartesian(center, center, radius + 22, angle).y}
                  fill="#64748b"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="middle"
                  alignmentBaseline="middle"
                >
                  {t}°
                </text>
              </g>
            );
          })}

          {/* Setpoint Target Marker Line */}
          <line
            x1={setpointInner.x}
            y1={setpointInner.y}
            x2={setpointPos.x}
            y2={setpointPos.y}
            stroke="#38bdf8"
            strokeWidth="3.5"
            strokeLinecap="round"
            filter="url(#glow)"
          />
          <circle
            cx={setpointPos.x}
            cy={setpointPos.y}
            r="4.5"
            fill="#38bdf8"
            stroke="#0f172a"
            strokeWidth="1.5"
          />

          {/* Current Needle / Indicator Dot */}
          <circle
            cx={currentPos.x}
            cy={currentPos.y}
            r="8"
            fill={thermal.hex}
            stroke="#0f172a"
            strokeWidth="2.5"
            filter="url(#glow)"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center Readout Text Overlay */}
        <div className="absolute inset-0 top-6 flex flex-col items-center justify-center text-center pointer-events-none select-none">
          <span className="text-[10px] font-mono text-slate-400 tracking-widest uppercase mb-0.5">
            INDOOR TEMPERATURE
          </span>
          <div
            className="text-4xl font-mono font-bold tracking-tight transition-all duration-500"
            style={{ color: thermal.hex }}
          >
            {formatTemp(currentTempC)}
          </div>

          {/* Target Setpoint Badge */}
          <div className="flex items-center space-x-1.5 mt-1.5 px-2.5 py-0.5 rounded-full bg-slate-950/80 border border-slate-800 text-xs font-mono text-slate-300">
            <Target className="w-3 h-3 text-cyan-400" />
            <span>SETPOINT: </span>
            <span className="font-bold text-cyan-300">{formatTemp(setpointC)}</span>
          </div>
        </div>
      </div>

      {/* Bottom Telemetry Footer Strip */}
      <div className="w-full grid grid-cols-2 gap-2 mt-1 pt-3 border-t border-slate-800 text-xs font-mono">
        <div className="flex items-center space-x-2 bg-slate-950/60 p-2 rounded border border-slate-800">
          <Wind className={`w-4 h-4 ${isCooling ? 'text-cyan-400 animate-spin' : 'text-slate-500'}`} />
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">HVAC MODE</span>
            <span className={`font-semibold ${isCooling ? 'text-cyan-400' : isHeating ? 'text-amber-400' : 'text-slate-400'}`}>
              {hvacMode}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2 bg-slate-950/60 p-2 rounded border border-slate-800">
          <Zap className="w-4 h-4 text-amber-400" />
          <div>
            <span className="text-[10px] text-slate-500 uppercase block">THERMAL DELTA</span>
            <span
              className={`font-semibold ${
                delta > 0.5 ? 'text-amber-400' : delta < -0.5 ? 'text-cyan-400' : 'text-emerald-400'
              }`}
            >
              {delta >= 0 ? `+${delta.toFixed(2)}°C` : `${delta.toFixed(2)}°C`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
