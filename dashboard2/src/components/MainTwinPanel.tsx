import React, { useState } from 'react';
import type{ RoomConfig, OptimizeResponse } from '../types';
import { useTwinState, useHistory } from '../hooks/useTwin';
import { ThermalGauge } from './ThermalGauge';
import { RoomSchematic } from './RoomSchematic';
import { TelemetryGrid } from './TelemetryGrid';
import { TelemetryChart } from './TelemetryChart';
import { FeedbackConsole } from './FeedbackConsole';
import { ConfirmationLoop } from './ConfirmationLoop';

interface MainTwinPanelProps {
  room: RoomConfig;
}

export const MainTwinPanel: React.FC<MainTwinPanelProps> = ({ room }) => {
  const { data: state, isLoading, error } = useTwinState(room.room_id);
  const { data: history = [] } = useHistory();

  const [activeOptimization, setActiveOptimization] = useState<OptimizeResponse | null>(null);

  const currentTemp = state?.indoor_temp_c ?? room.initial_temp_c;
  const setpoint = state?.current_setpoint_c ?? 24.0;
  
  // Calculate HVAC power from latest history or state
  const latestLog = history.find((h) => h.zone_id === room.room_id);
  const hvacPowerW = activeOptimization?.hvac_power_w ?? latestLog?.hvac_power_w ?? 0;

  return (
    <div className="flex-1 p-4 lg:p-6 space-y-5 overflow-y-auto custom-scrollbar bg-[#080c14]">
      {/* 1. Top Section: Thermal Gauge Centerpiece + 2D Room Schematic */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ThermalGauge
          currentTempC={currentTemp}
          setpointC={setpoint}
          hvacPowerW={hvacPowerW}
        />
        <RoomSchematic
          room={room}
          state={state}
          hvacPowerW={hvacPowerW}
        />
      </div>

      {/* 2. Instrument Telemetry Grid (RH%, CO2, Occupancy, Power kW, HVAC Util%) */}
      <TelemetryGrid
        room={room}
        state={state}
        hvacPowerW={hvacPowerW}
      />

      {/* 3. Time Series Telemetry Timeline Strip */}
      <TelemetryChart
        history={history}
        activeZoneId={room.room_id}
      />

      {/* 4. Natural-Language Comfort Feedback & Signal Processing Console */}
      <FeedbackConsole
        activeZoneId={room.room_id}
        onOptimizationDone={(optRes) => setActiveOptimization(optRes)}
      />

      {/* 5. Comfort Confirmation Loop (Active when optimization returns ask_confirmation) */}
      <ConfirmationLoop
        activeZoneId={room.room_id}
        optimizationResult={activeOptimization}
        onConfirmDone={() => setActiveOptimization(null)}
        onRequireMoreFeedback={() => {
          // Focus back on feedback console for next iteration
        }}
      />
    </div>
  );
};
