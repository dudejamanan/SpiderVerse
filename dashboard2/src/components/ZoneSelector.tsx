import React from 'react';
import type { RoomConfig } from '../types';
import { useTwinState } from '../hooks/useTwin';
import { getThermalColor, formatTemp } from '../lib/thermal';
import { Thermometer, Zap, Users, ShieldAlert, Cpu } from 'lucide-react';

interface ZoneSelectorProps {
  rooms: RoomConfig[];
  activeZoneId: string;
  onSelectZone: (zoneId: string) => void;
}

const RoomCard: React.FC<{
  room: RoomConfig;
  isActive: boolean;
  onSelect: () => void;
}> = ({ room, isActive, onSelect }) => {
  const { data: state, isLoading } = useTwinState(room.room_id);

  const temp = state?.indoor_temp_c ?? room.initial_temp_c;
  const setpoint = state?.current_setpoint_c ?? 24.0;
  const energy = state?.energy_draw_kw ?? 1.0;
  const occupancy = state?.occupancy_count ?? room.initial_occupancy;

  const thermal = getThermalColor(temp);
  const delta = temp - setpoint;
  const absDelta = Math.abs(delta);

  return (
    <button
      onClick={onSelect}
      className={`group w-full text-left p-3.5 rounded-lg border transition-all relative overflow-hidden select-none ${
        isActive
          ? 'bg-slate-900 border-cyan-500/80 shadow-[0_0_15px_rgba(6,182,212,0.15)] ring-1 ring-cyan-500/30'
          : 'bg-[#0e1626]/80 hover:bg-slate-900/90 border-slate-800 hover:border-slate-700'
      }`}
    >
      {/* Active Indicator Left Accent Bar */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1 transition-colors"
        style={{ backgroundColor: thermal.hex }}
      />

      <div className="flex items-center justify-between mb-1.5 pl-1.5">
        <div className="flex items-center space-x-2">
          <Cpu className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
            {room.room_id.replace(/_/g, ' ')}
          </span>
        </div>

        {/* Status Badge */}
        <span
          className={`text-[10px] font-mono px-1.5 py-0.5 rounded border font-semibold ${thermal.badgeBg} ${thermal.badgeText} ${thermal.badgeBorder}`}
        >
          {thermal.label}
        </span>
      </div>

      {/* Main Temperature & Telemetry Strip */}
      <div className="grid grid-cols-2 gap-2 pl-1.5 mt-2">
        <div>
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block">TELEMETRY</span>
          <div className="flex items-baseline space-x-1.5">
            <span
              className="text-xl font-mono font-bold tracking-tight"
              style={{ color: thermal.hex }}
            >
              {formatTemp(temp)}
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              / {formatTemp(setpoint)}
            </span>
          </div>
        </div>

        <div className="text-right">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block">DEVIATION</span>
          <div className="flex items-center justify-end space-x-1">
            <span
              className={`text-xs font-mono font-semibold ${
                delta > 0.5
                  ? 'text-amber-400'
                  : delta < -0.5
                  ? 'text-cyan-400'
                  : 'text-emerald-400'
              }`}
            >
              {delta >= 0 ? `+${delta.toFixed(1)}°` : `${delta.toFixed(1)}°`}
            </span>
          </div>
        </div>
      </div>

      {/* Secondary Metrics Bar */}
      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mt-2.5 pt-2 border-t border-slate-800/80 pl-1.5">
        <div className="flex items-center space-x-1" title="Power Draw">
          <Zap className="w-3 h-3 text-amber-500" />
          <span>{energy.toFixed(2)} kW</span>
        </div>

        <div className="flex items-center space-x-1" title="Occupants">
          <Users className="w-3 h-3 text-cyan-400" />
          <span>{occupancy} pers</span>
        </div>

        <div className="text-[10px] text-slate-500">
          {room.area_m2}m²
        </div>
      </div>
    </button>
  );
};

export const ZoneSelector: React.FC<ZoneSelectorProps> = ({
  rooms,
  activeZoneId,
  onSelectZone,
}) => {
  return (
    <aside className="w-full lg:w-72 flex-shrink-0 bg-[#0b111e] border-b lg:border-b-0 lg:border-r border-slate-800 p-4 space-y-3">
      <div className="flex items-center justify-between mb-1 px-1">
        <div className="flex items-center space-x-2">
          <Thermometer className="w-4 h-4 text-cyan-400" />
          <h2 className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            ZONE CONTROL MATRIX
          </h2>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">
          {rooms.length} ZONES
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2.5 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
        {rooms.map((room) => (
          <RoomCard
            key={room.room_id}
            room={room}
            isActive={room.room_id === activeZoneId}
            onSelect={() => onSelectZone(room.room_id)}
          />
        ))}
      </div>
    </aside>
  );
};
