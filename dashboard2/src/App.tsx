import React, { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useBuildingConfig, useTestHvac } from './hooks/useTwin';
import { GlobalHeader } from './components/GlobalHeader';
import { ZoneSelector } from './components/ZoneSelector';
import { MainTwinPanel } from './components/MainTwinPanel';
import { HistoryLog } from './components/HistoryLog';
import { BuildingConfigModal } from './components/BuildingConfigModal';
import { ApiConfigModal } from './components/ApiConfigModal';
import { Activity, LayoutDashboard, History, SlidersHorizontal, AlertCircle } from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const DashboardContent: React.FC = () => {
  const { data: config, isLoading, isError } = useBuildingConfig();
  const testHvacMutation = useTestHvac();

  const [activeZoneId, setActiveZoneId] = useState<string>('room_0');
  const [activeTab, setActiveTab] = useState<'control' | 'history'>('control');
  const [isBuildingConfigOpen, setIsBuildingConfigOpen] = useState(false);
  const [isApiConfigOpen, setIsApiConfigOpen] = useState(false);

  const rooms = config?.rooms || [
    {
      room_id: 'room_0',
      area_m2: 30.0,
      height_m: 3.0,
      window_area_m2: 5.0,
      R: 2.0,
      C: 156000.0,
      shading_coefficient: 0.5,
      ventilation_ach: 1.5,
      hvac_capacity_w: 2000.0,
      cop: 3.5,
      initial_temp_c: 24.0,
      initial_rh_pct: 50.0,
      initial_co2_ppm: 420.0,
      initial_occupancy: 0,
    },
  ];

  // Set default active zone if invalid
  useEffect(() => {
    if (rooms.length > 0 && !rooms.some((r) => r.room_id === activeZoneId)) {
      setActiveZoneId(rooms[0].room_id);
    }
  }, [rooms, activeZoneId]);

  const activeRoom = rooms.find((r) => r.room_id === activeZoneId) || rooms[0];

  const handleManualStep = () => {
    testHvacMutation.mutate({
      zoneId: activeZoneId,
      hvacPowerW: 1500.0, // Manual cooling drive test step
    });
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#080c14] text-slate-100 font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* 1. Global Operational Header */}
      <GlobalHeader
        activeZoneId={activeZoneId}
        onOpenBuildingConfig={() => setIsBuildingConfigOpen(true)}
        onOpenApiConfig={() => setIsApiConfigOpen(true)}
        onManualStep={handleManualStep}
        isStepping={testHvacMutation.isPending}
      />

      {/* View Mode Navigation Bar */}
      <div className="bg-[#0b111e] border-b border-slate-800 px-4 py-1.5 flex items-center justify-between text-xs font-mono select-none">
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setActiveTab('control')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded transition-all ${
              activeTab === 'control'
                ? 'bg-cyan-950 text-cyan-300 font-bold border border-cyan-700/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5 text-cyan-400" />
            <span>CONTROL ROOM TWIN</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded transition-all ${
              activeTab === 'history'
                ? 'bg-cyan-950 text-cyan-300 font-bold border border-cyan-700/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <History className="w-3.5 h-3.5 text-cyan-400" />
            <span>GLOBAL AUDIT LOG</span>
          </button>
        </div>

        <div className="hidden sm:flex items-center space-x-3 text-[11px] text-slate-400">
          <span>ACTIVE ZONE: <strong className="text-cyan-400">{activeZoneId.toUpperCase()}</strong></span>
          <span className="text-slate-600">|</span>
          <span>LOCATION: <strong className="text-slate-200">{config?.location?.name || 'CHENNAI'}</strong></span>
        </div>
      </div>

      {/* 2. Main Dashboard Layout (Zone Selector + Main Twin Panel) */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Persistent Zone Selector */}
        <ZoneSelector
          rooms={rooms}
          activeZoneId={activeZoneId}
          onSelectZone={(id) => setActiveZoneId(id)}
        />

        {/* Right Main Content Area */}
        <div className="flex-1 flex flex-col overflow-y-auto">
          {activeTab === 'control' ? (
            <>
              <MainTwinPanel room={activeRoom} />
              <div className="p-4 lg:p-6 pt-0 bg-[#080c14]">
                <HistoryLog rooms={rooms} />
              </div>
            </>
          ) : (
            <div className="p-6 bg-[#080c14] flex-1">
              <HistoryLog rooms={rooms} />
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <BuildingConfigModal
        isOpen={isBuildingConfigOpen}
        onClose={() => setIsBuildingConfigOpen(false)}
        currentConfig={config}
      />

      <ApiConfigModal
        isOpen={isApiConfigOpen}
        onClose={() => setIsApiConfigOpen(false)}
      />
    </div>
  );
};

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  );
}
