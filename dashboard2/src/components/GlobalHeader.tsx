import React, { useState } from 'react';
import {
  Activity,
  Globe,
  SlidersHorizontal,
  Server,
  ToggleLeft,
  ToggleRight,
  Zap,
  Building2,
  RefreshCw,
} from 'lucide-react';
import { useBuildingConfig, useHealth, useRegion, useSetRegion } from '../hooks/useTwin';
import { isDemoMode, setDemoMode, apiBaseUrl } from '../lib/api';

interface GlobalHeaderProps {
  activeZoneId: string;
  onOpenBuildingConfig: () => void;
  onOpenApiConfig: () => void;
  onManualStep: () => void;
  isStepping?: boolean;
}

export const GlobalHeader: React.FC<GlobalHeaderProps> = ({
  activeZoneId,
  onOpenBuildingConfig,
  onOpenApiConfig,
  onManualStep,
  isStepping = false,
}) => {
  const { data: health } = useHealth();
  const { data: config } = useBuildingConfig();
  const { data: regionData } = useRegion();
  const setRegionMutation = useSetRegion();

  const [demoState, setDemoState] = useState(isDemoMode);

  const toggleDemo = () => {
    const next = !demoState;
    setDemoState(next);
    setDemoMode(next);
    window.location.reload(); // Quick refresh to re-init queries with new mode
  };

  const handleRegionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setRegionMutation.mutate(e.target.value);
  };

  const isHealthy = health?.status?.includes('healthy');
  const isDemo = demoState || health?.status?.includes('demo');

  const loc = config?.location;
  const buildingName = config?.building_id ? config.building_id.toUpperCase().replace(/_/g, ' ') : 'BUILDING TWIN';

  return (
    <header className="bg-[#0b111e] border-b border-slate-800 px-4 py-3 flex flex-wrap items-center justify-between gap-4 select-none">
      {/* Left: Building ID & Location Metadata */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-400">
            <Building2 className="w-5 h-5 animate-pulse-subtle" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono tracking-widest text-cyan-500 font-bold uppercase">DIGITAL TWIN HVAC</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                v1.0.0
              </span>
            </div>
            <h1 className="text-sm font-semibold text-slate-100 tracking-wide font-mono flex items-center gap-2">
              {buildingName}
            </h1>
          </div>
        </div>

        {/* Location Readout */}
        {loc && (
          <div className="hidden md:flex items-center space-x-2 pl-4 border-l border-slate-800 text-xs font-mono text-slate-400">
            <Globe className="w-3.5 h-3.5 text-cyan-500" />
            <span className="text-slate-200 font-medium">{loc.name}, {loc.country}</span>
            <span className="text-slate-500 text-[11px]">
              ({loc.latitude.toFixed(2)}°N, {loc.longitude.toFixed(2)}°E)
            </span>
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center flex-wrap gap-2.5">
        {/* Region Selector */}
        <div className="flex items-center space-x-1.5 bg-slate-900 border border-slate-800 rounded px-2.5 py-1">
          <span className="text-[11px] font-mono text-slate-400 uppercase">Region:</span>
          <select
            value={regionData?.region || 'Asia/South'}
            onChange={handleRegionChange}
            className="bg-transparent text-xs font-mono text-cyan-400 focus:outline-none cursor-pointer"
          >
            <option value="Asia/South" className="bg-slate-900 text-slate-200">Asia/South (IN)</option>
            <option value="Asia/East" className="bg-slate-900 text-slate-200">Asia/East (JP/SG)</option>
            <option value="US/East" className="bg-slate-900 text-slate-200">US/East (NY/VA)</option>
            <option value="Europe/Central" className="bg-slate-900 text-slate-200">Europe/Central (DE)</option>
          </select>
        </div>

        {/* Manual Step Simulation Button */}
        <button
          onClick={onManualStep}
          disabled={isStepping}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-cyan-950/80 hover:bg-cyan-900/90 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-medium transition-all shadow-sm active:scale-95 disabled:opacity-50"
          title="Manually trigger 1 simulation step (+1.5 kW test HVAC)"
        >
          {isStepping ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-cyan-400" />}
          <span>SIMULATE STEP</span>
        </button>

        {/* Demo Mode Toggle */}
        <button
          onClick={toggleDemo}
          className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded text-xs font-mono transition-all border ${
            demoState
              ? 'bg-amber-950/40 text-amber-300 border-amber-500/40'
              : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
          }`}
          title="Toggle between Live API and Offline Demo Simulator"
        >
          {demoState ? <ToggleRight className="w-4 h-4 text-amber-400" /> : <ToggleLeft className="w-4 h-4 text-slate-500" />}
          <span>DEMO MODE</span>
        </button>

        {/* Building Config Button */}
        <button
          onClick={onOpenBuildingConfig}
          className="p-1.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-mono flex items-center space-x-1 transition-all"
          title="Configure Building & Rooms"
        >
          <SlidersHorizontal className="w-4 h-4 text-slate-400" />
          <span className="hidden lg:inline text-[11px]">CONFIG</span>
        </button>

        {/* API Endpoint Button */}
        <button
          onClick={onOpenApiConfig}
          className="p-1.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-mono flex items-center space-x-1 transition-all"
          title={`API Base: ${apiBaseUrl}`}
        >
          <Server className="w-4 h-4 text-slate-400" />
        </button>

        {/* Connection Health Indicator */}
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-xs font-mono">
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isDemo ? 'bg-amber-400' : isHealthy ? 'bg-emerald-400' : 'bg-red-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isDemo ? 'bg-amber-500' : isHealthy ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            />
          </span>
          <span className="text-[11px] font-semibold text-slate-300 tracking-wider">
            {isDemo ? 'DEMO MODE' : isHealthy ? 'LIVE CONNECTED' : 'BACKEND DISCONNECTED'}
          </span>
        </div>
      </div>
    </header>
  );
};
