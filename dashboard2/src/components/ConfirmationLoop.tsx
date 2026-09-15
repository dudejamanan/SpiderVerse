import React, { useState } from 'react';
import type{ OptimizeResponse } from '../types';
import { useConfirmComfort } from '../hooks/useTwin';
import { MessageSquare, Check, X, RefreshCw, Cpu, CheckCircle } from 'lucide-react';

interface ConfirmationLoopProps {
  activeZoneId: string;
  optimizationResult: OptimizeResponse | null;
  onConfirmDone: () => void;
  onRequireMoreFeedback: () => void;
}

export const ConfirmationLoop: React.FC<ConfirmationLoopProps> = ({
  activeZoneId,
  optimizationResult,
  onConfirmDone,
  onRequireMoreFeedback,
}) => {
  const [iteration, setIteration] = useState(1);
  const [isResolved, setIsResolved] = useState(false);
  const confirmMutation = useConfirmComfort();

  if (!optimizationResult || !optimizationResult.ask_confirmation) {
    return null;
  }

  const { action, hvac_power_w, energy_draw_kwh, confirmation_question } = optimizationResult;

  const handleConfirm = (comfortable: boolean) => {
    confirmMutation.mutate(
      { zoneId: activeZoneId, comfortable },
      {
        onSuccess: (res) => {
          if (!res.conversation_active) {
            setIsResolved(true);
            setTimeout(() => {
              onConfirmDone();
              setIsResolved(false);
            }, 2500);
          } else {
            setIteration(res.iteration || iteration + 1);
            onRequireMoreFeedback();
          }
        },
      }
    );
  };

  if (isResolved) {
    return (
      <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-4 flex items-center justify-between text-emerald-300 font-mono text-xs select-none">
        <div className="flex items-center space-x-2">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          <span className="font-bold">Comfort Target Confirmed & Optimization Cycle Closed!</span>
        </div>
        <span className="text-[10px] text-emerald-400/80">ZONE: {activeZoneId}</span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-cyan-500/40 rounded-xl p-4 space-y-3 select-none shadow-[0_0_20px_rgba(6,182,212,0.1)]">
      {/* Header with Iteration Counter */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2">
          <MessageSquare className="w-4 h-4 text-cyan-400" />
          <h4 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
            COMFORT CONFIRMATION LOOP
          </h4>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
          ITERATION #{iteration}
        </span>
      </div>

      {/* Optimization Impact Summary */}
      <div className="grid grid-cols-3 gap-2 text-xs font-mono bg-[#080c14] p-2.5 rounded border border-slate-800">
        <div>
          <span className="text-[9px] text-slate-500 uppercase block">SETPOINT DELTA</span>
          <span className="font-bold text-cyan-400">
            {action?.setpoint_delta_c ? (action.setpoint_delta_c > 0 ? `+${action.setpoint_delta_c}°C` : `${action.setpoint_delta_c}°C`) : '0.0°C'}
          </span>
          <span className="text-[10px] text-slate-400 block">→ {action?.new_setpoint_c}°C</span>
        </div>

        <div>
          <span className="text-[9px] text-slate-500 uppercase block">HVAC DRIVE</span>
          <span className="font-bold text-amber-400">{(hvac_power_w / 1000).toFixed(2)} kW</span>
        </div>

        <div>
          <span className="text-[9px] text-slate-500 uppercase block">ENERGY COST</span>
          <span className="font-bold text-emerald-400">{(energy_draw_kwh).toFixed(3)} kWh</span>
        </div>
      </div>

      {/* Confirmation Question & Action Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <p className="text-xs font-mono text-slate-200">
          ❓ {confirmation_question || `Adjusted setpoint to ${action?.new_setpoint_c}°C. Is the room comfortable now?`}
        </p>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleConfirm(true)}
            disabled={confirmMutation.isPending}
            className="px-4 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-mono text-xs font-bold flex items-center space-x-1.5 transition-all shadow active:scale-95 disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            <span>YES — COMFORTABLE</span>
          </button>

          <button
            onClick={() => handleConfirm(false)}
            disabled={confirmMutation.isPending}
            className="px-4 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-mono text-xs font-semibold flex items-center space-x-1.5 border border-slate-700 transition-all active:scale-95 disabled:opacity-50"
          >
            <X className="w-4 h-4 text-red-400" />
            <span>NO — NEEDS ADJUSTMENT</span>
          </button>
        </div>
      </div>
    </div>
  );
};
