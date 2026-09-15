import React, { useState } from 'react';
import type{ HistoryEntry, RoomConfig } from '../types';
import { useHistory } from '../hooks/useTwin';
import { History, Filter, Zap, ArrowRight, ShieldCheck, Tag } from 'lucide-react';

interface HistoryLogProps {
  rooms: RoomConfig[];
}

export const HistoryLog: React.FC<HistoryLogProps> = ({ rooms }) => {
  const { data: history = [], isLoading } = useHistory();
  const [selectedZone, setSelectedZone] = useState<string>('ALL');

  const filteredLogs = selectedZone === 'ALL'
    ? history
    : history.filter((h) => h.zone_id === selectedZone);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col space-y-4 select-none">
      {/* Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            OPTIMIZATION & TELEMETRY AUDIT LOG
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            {filteredLogs.length} EVENTS
          </span>
        </div>

        {/* Zone Filter Dropdown */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 uppercase">Filter Zone:</span>
          <select
            value={selectedZone}
            onChange={(e) => setSelectedZone(e.target.value)}
            className="bg-[#080c14] border border-slate-800 rounded px-2.5 py-1 text-cyan-400 focus:outline-none cursor-pointer"
          >
            <option value="ALL">ALL ZONES ({history.length})</option>
            {rooms.map((r) => (
              <option key={r.room_id} value={r.room_id}>
                {r.room_id.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Log Feed Table / List */}
      <div className="max-h-[320px] overflow-y-auto pr-1 space-y-2 custom-scrollbar">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-8 text-xs font-mono text-slate-500">
            No optimization event logs recorded yet. Submit a comfort complaint to begin logging.
          </div>
        ) : (
          filteredLogs.map((log, idx) => {
            const timeStr = log.timestamp
              ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
              : `LOG #${filteredLogs.length - idx}`;

            const constraint = log.constraint;
            const action = log.action;
            const newState = log.new_state;

            return (
              <div
                key={idx}
                className="bg-[#080c14] border border-slate-800/80 hover:border-slate-700 rounded-lg p-3 text-xs font-mono space-y-2 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] text-slate-500">{timeStr}</span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-cyan-400 font-bold text-[10px]">
                      {log.zone_id.toUpperCase()}
                    </span>
                    {log.type === 'manual_test' && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 text-[9px] border border-amber-800">
                        MANUAL TEST
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-3 text-[11px] text-slate-400">
                    <span title="HVAC Power Drive">
                      ⚡ {(Math.abs(log.hvac_power_w ?? 0) / 1000).toFixed(2)} kW
                    </span>
                    <span title="Energy Consumed">
                      🔋 {(log.energy_draw_kwh ?? 0).toFixed(3)} kWh
                    </span>
                  </div>
                </div>

                {/* Complaint Text & Action details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 bg-slate-900/60 p-2 rounded border border-slate-800">
                  {constraint ? (
                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">COMPLAINT SIGNAL</span>
                      <span className="text-slate-300">"{constraint.raw_text}"</span>
                      <span className="text-[10px] text-purple-400 block mt-0.5">
                        [{constraint.parameter} → {constraint.direction} ({constraint.intensity})]
                      </span>
                    </div>
                  ) : (
                    <div className="text-slate-500 italic">No NLP constraint attached</div>
                  )}

                  {action ? (
                    <div className="md:text-right">
                      <span className="text-[9px] text-slate-500 uppercase block">SETPOINT ADJUSTMENT</span>
                      <span className="font-bold text-emerald-400">
                        Δ {action.setpoint_delta_c > 0 ? `+${action.setpoint_delta_c}` : action.setpoint_delta_c}°C
                      </span>
                      <span className="text-slate-400 block text-[10px]">
                        NEW TARGET: <strong>{action.new_setpoint_c}°C</strong>
                      </span>
                    </div>
                  ) : log.old_state && log.new_state ? (
                    <div className="md:text-right text-slate-400">
                      <span>Temp: {log.old_state.indoor_temp_c}°C → {log.new_state.indoor_temp_c}°C</span>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
