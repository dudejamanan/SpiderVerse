import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceDot,
} from 'recharts';
import type { HistoryEntry } from '../types';
import { Activity, Zap } from 'lucide-react';

interface TelemetryChartProps {
  history: HistoryEntry[];
  activeZoneId: string;
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  history,
  activeZoneId,
}) => {
  // Filter history for active zone and map to time-series chart data points
  const zoneLogs = history.filter((h) => h.zone_id === activeZoneId);

  // If minimal logs, build a realistic session series for display
  const chartData = React.useMemo(() => {
    if (zoneLogs.length > 0) {
      return zoneLogs
        .slice()
        .reverse()
        .map((log, idx) => {
          const state = log.new_state || log.old_state;
          const temp = state?.indoor_temp_c ?? 24.0;
          const setpoint = state?.current_setpoint_c ?? 23.5;
          const powerKw = (Math.abs(log.hvac_power_w ?? 1500) / 1000);
          const timeLabel = log.timestamp
            ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : `T-${(zoneLogs.length - idx) * 5}m`;

          return {
            time: timeLabel,
            temperature: temp,
            setpoint,
            powerKw,
            hasAction: !!log.action,
            actionText: log.action ? `Δ ${log.action.setpoint_delta_c}°C` : null,
          };
        });
    }

    // Default dummy telemetry stream if empty history
    const now = Date.now();
    return Array.from({ length: 12 }).map((_, i) => {
      const time = new Date(now - (11 - i) * 180000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return {
        time,
        temperature: 24.5 - i * 0.12 + Math.sin(i) * 0.2,
        setpoint: i > 5 ? 23.0 : 24.0,
        powerKw: 1.2 + Math.cos(i) * 0.3,
        hasAction: i === 6,
        actionText: i === 6 ? 'RL OPTIMIZED (-1.0°C)' : null,
      };
    });
  }, [zoneLogs]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between select-none">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            TELEMETRY SESSION TIMELINE — ZONE: {activeZoneId.toUpperCase()}
          </h3>
        </div>
        <div className="flex items-center space-x-4 text-[11px] font-mono">
          <span className="flex items-center space-x-1 text-cyan-400">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block" />
            <span>INDOOR TEMP (°C)</span>
          </span>
          <span className="flex items-center space-x-1 text-emerald-400">
            <span className="w-2.5 h-0.5 bg-emerald-400 inline-block" />
            <span>SETPOINT (°C)</span>
          </span>
          <span className="flex items-center space-x-1 text-amber-400">
            <span className="w-2.5 h-2.5 rounded bg-amber-500/30 border border-amber-500 inline-block" />
            <span>POWER (kW)</span>
          </span>
        </div>
      </div>

      <div className="w-full h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="powerGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

            <XAxis
              dataKey="time"
              stroke="#64748b"
              fontSize={10}
              fontFamily="monospace"
              tickLine={false}
            />

            {/* Left Y Axis: Temperature */}
            <YAxis
              yAxisId="left"
              domain={[18, 30]}
              stroke="#64748b"
              fontSize={10}
              fontFamily="monospace"
              tickFormatter={(v) => `${v}°C`}
              tickLine={false}
            />

            {/* Right Y Axis: Power kW */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 4.0]}
              stroke="#64748b"
              fontSize={10}
              fontFamily="monospace"
              tickFormatter={(v) => `${v} kW`}
              tickLine={false}
            />

            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || !payload.length) return null;
                return (
                  <div className="bg-[#0b111e] border border-slate-700 p-2.5 rounded shadow-xl text-xs font-mono space-y-1 z-50">
                    <div className="text-slate-400 font-bold border-b border-slate-800 pb-1 mb-1">{label}</div>
                    {payload.map((p, i) => (
                      <div key={i} className="flex items-center justify-between space-x-3">
                        <span style={{ color: p.color }}>{p.name}:</span>
                        <span className="font-bold text-slate-200">
                          {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              }}
            />

            {/* Power Draw Area (Right Y Axis) */}
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="powerKw"
              name="Power Draw (kW)"
              stroke="#f59e0b"
              fill="url(#powerGrad)"
              strokeWidth={1.5}
            />

            {/* Setpoint Line (Left Y Axis) */}
            <Line
              yAxisId="left"
              type="stepAfter"
              dataKey="setpoint"
              name="Setpoint (°C)"
              stroke="#10b981"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
            />

            {/* Temperature Line (Left Y Axis) */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="temperature"
              name="Indoor Temp (°C)"
              stroke="#38bdf8"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#38bdf8', stroke: '#0f172a', strokeWidth: 1.5 }}
              activeDot={{ r: 6, fill: '#38bdf8' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
