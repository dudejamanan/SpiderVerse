import React from 'react';
import type { RoomConfig, TwinState } from '../types';
import { getCo2Status } from '../lib/thermal';
import { Droplets, Wind, Users, Zap, Gauge } from 'lucide-react';

interface TelemetryGridProps {
  room: RoomConfig;
  state?: TwinState;
  hvacPowerW: number;
}

export const TelemetryGrid: React.FC<TelemetryGridProps> = ({
  room,
  state,
  hvacPowerW,
}) => {
  const rh = state?.rh_pct ?? room.initial_rh_pct;
  const co2 = state?.co2_ppm ?? room.initial_co2_ppm;
  const occupancy = state?.occupancy_count ?? room.initial_occupancy;
  const energyKw = state?.energy_draw_kw ?? 1.0;

  const co2Status = getCo2Status(co2);
  const utilizationPct = Math.min(100, Math.round((Math.abs(hvacPowerW) / room.hvac_capacity_w) * 100));

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 select-none">
      {/* 1. Relative Humidity Tile */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[10px] font-mono tracking-widest uppercase text-slate-400">HUMIDITY</span>
          <Droplets className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="my-1">
          <div className="text-2xl font-mono font-bold text-slate-100 tracking-tight">
            {rh.toFixed(1)}<span className="text-sm font-normal text-slate-400">% RH</span>
          </div>
        </div>
        <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800 mt-1">
          <div
            className="bg-cyan-400 h-full transition-all duration-500"
            style={{ width: `${Math.min(100, rh)}%` }}
          />
        </div>
        <span className="text-[10px] font-mono text-slate-500 mt-1.5 block">
          {rh < 35 ? 'DRY AIR' : rh <= 60 ? 'OPTIMAL MOISTURE' : 'HIGH HUMIDITY'}
        </span>
      </div>

      {/* 2. CO2 Concentration Tile */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[10px] font-mono tracking-widest uppercase text-slate-400">CO₂ LEVEL</span>
          <Wind className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="my-1">
          <div className="text-2xl font-mono font-bold tracking-tight" style={{ color: co2Status.color }}>
            {co2.toFixed(0)} <span className="text-sm font-normal text-slate-400">PPM</span>
          </div>
        </div>
        <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800 mt-1">
          <div
            className="h-full transition-all duration-500"
            style={{
              width: `${Math.min(100, (co2 / 1600) * 100)}%`,
              backgroundColor: co2Status.color,
            }}
          />
        </div>
        <span className="text-[10px] font-mono font-semibold truncate mt-1.5 block" style={{ color: co2Status.color }}>
          {co2Status.label}
        </span>
      </div>

      {/* 3. Occupancy Tile */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[10px] font-mono tracking-widest uppercase text-slate-400">OCCUPANCY</span>
          <Users className="w-4 h-4 text-purple-400" />
        </div>
        <div className="my-1">
          <div className="text-2xl font-mono font-bold text-slate-100 tracking-tight">
            {occupancy} <span className="text-sm font-normal text-slate-400">PERS</span>
          </div>
        </div>
        <div className="text-[10px] font-mono text-slate-400 mt-2">
          LOAD: <span className="text-purple-300 font-semibold">+{(occupancy * 80).toFixed(0)} W HEAT</span>
        </div>
      </div>

      {/* 4. Instant Energy Draw Tile */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[10px] font-mono tracking-widest uppercase text-slate-400">POWER DRAW</span>
          <Zap className="w-4 h-4 text-amber-400" />
        </div>
        <div className="my-1">
          <div className="text-2xl font-mono font-bold text-amber-400 tracking-tight">
            {energyKw.toFixed(2)} <span className="text-sm font-normal text-slate-400">kW</span>
          </div>
        </div>
        <div className="text-[10px] font-mono text-slate-400 mt-2">
          EST. COST: <span className="text-slate-300 font-semibold">${(energyKw * 0.14).toFixed(3)}/hr</span>
        </div>
      </div>

      {/* 5. HVAC Capacity Utilization Tile */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 flex flex-col justify-between col-span-2 sm:col-span-1">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[10px] font-mono tracking-widest uppercase text-slate-400">HVAC UTIL</span>
          <Gauge className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="my-1">
          <div className="text-2xl font-mono font-bold text-cyan-400 tracking-tight">
            {utilizationPct}<span className="text-sm font-normal text-slate-400">%</span>
          </div>
        </div>
        <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800 mt-1">
          <div
            className="bg-cyan-400 h-full transition-all duration-500"
            style={{ width: `${utilizationPct}%` }}
          />
        </div>
        <span className="text-[10px] font-mono text-slate-400 mt-1.5 block">
          CAP: {(room.hvac_capacity_w / 1000).toFixed(1)} kW
        </span>
      </div>
    </div>
  );
};
