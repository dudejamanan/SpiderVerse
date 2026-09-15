import type{
  BuildingConfig,
  BuildingConfigRequest,
  Location,
  TwinState,
  LLMConstraint,
  OptimizeResponse,
  ConfirmResponse,
  HistoryEntry,
  RegionResponse,
  TestHvacResponse,
  HealthResponse,
  FeedbackResponse,
} from '../types';
import { demoSimulator } from './demoSimulator';

const getStoredApiUrl = () => {
  return localStorage.getItem('hvac_api_base_url') || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

const getStoredDemoMode = (): boolean => {
  const stored = localStorage.getItem('hvac_demo_mode');
  if (stored !== null) return stored === 'true';
  return false; // default to attempting real backend first
};

export let apiBaseUrl = getStoredApiUrl();
export let isDemoMode = getStoredDemoMode();

export const setApiBaseUrl = (url: string) => {
  apiBaseUrl = url.replace(/\/$/, '');
  localStorage.setItem('hvac_api_base_url', apiBaseUrl);
};

export const setDemoMode = (demo: boolean) => {
  isDemoMode = demo;
  localStorage.setItem('hvac_demo_mode', String(demo));
};

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${apiBaseUrl}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`API Error [${res.status}]: ${errText || res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    throw err;
  }
}

export const api = {
  // Health
  checkHealth: async (): Promise<HealthResponse> => {
    if (isDemoMode) {
      return { status: 'healthy (demo mode)' };
    }
    try {
      return await fetchJson<HealthResponse>('/health');
    } catch {
      return { status: 'offline' };
    }
  },

  // Building & Locations
  getBuildingConfig: async (): Promise<BuildingConfig> => {
    if (isDemoMode) return demoSimulator.getBuildingConfig();
    try {
      return await fetchJson<BuildingConfig>('/building_config');
    } catch {
      return demoSimulator.getBuildingConfig();
    }
  },

  getLocations: async (): Promise<Location[]> => {
    if (isDemoMode) return demoSimulator.getLocations();

    try {
      const data = await fetchJson<{
        india: Location[];
        outside_india: Location[];
      }>('/locations');

      return [...data.india, ...data.outside_india];
    } catch {
      return demoSimulator.getLocations();
    }
  },
  configureBuilding: async (req: BuildingConfigRequest): Promise<BuildingConfig> => {
    if (isDemoMode) return demoSimulator.configureBuilding(req);
    try {
      return await fetchJson<BuildingConfig>('/building_config', {
        method: 'POST',
        body: JSON.stringify(req),
      });
    } catch {
      return demoSimulator.configureBuilding(req);
    }
  },

  // Region
  getRegion: async (): Promise<RegionResponse> => {
    if (isDemoMode) return demoSimulator.getRegion();
    try {
      return await fetchJson<RegionResponse>('/region');
    } catch {
      return demoSimulator.getRegion();
    }
  },

  setRegion: async (region: string): Promise<RegionResponse> => {
    if (isDemoMode) return demoSimulator.setRegion(region);
    try {
      return await fetchJson<RegionResponse>('/region', {
        method: 'POST',
        body: JSON.stringify({ region }),
      });
    } catch {
      return demoSimulator.setRegion(region);
    }
  },

  // Twin State
  getTwinState: async (zoneId: string): Promise<TwinState> => {
    if (isDemoMode) return demoSimulator.getTwinState(zoneId);
    try {
      return await fetchJson<TwinState>(`/twin_state/${zoneId}`);
    } catch {
      return demoSimulator.getTwinState(zoneId);
    }
  },

  testHvac: async (zoneId: string, hvacPowerW: number): Promise<TestHvacResponse> => {
    if (isDemoMode) return demoSimulator.testHvac(zoneId, hvacPowerW);
    try {
      return await fetchJson<TestHvacResponse>(`/test_hvac/${zoneId}?hvac_power_w=${hvacPowerW}`, {
        method: 'POST',
      });
    } catch {
      return demoSimulator.testHvac(zoneId, hvacPowerW);
    }
  },

  // Feedback & Optimization Loop
  submitFeedback: async (zoneId: string, text: string): Promise<FeedbackResponse> => {
    if (isDemoMode) return demoSimulator.submitFeedback(zoneId, text);
    try {
      return await fetchJson<FeedbackResponse>('/submit_feedback', {
        method: 'POST',
        body: JSON.stringify({ zone_id: zoneId, text }),
      });
    } catch {
      return demoSimulator.submitFeedback(zoneId, text);
    }
  },

  testConstraint: async (zoneId: string): Promise<{ message: string; constraint: LLMConstraint }> => {
    if (isDemoMode) return demoSimulator.testConstraint(zoneId);
    try {
      return await fetchJson<{ message: string; constraint: LLMConstraint }>(`/test_constraint/${zoneId}`, {
        method: 'POST',
      });
    } catch {
      return demoSimulator.testConstraint(zoneId);
    }
  },

  optimize: async (zoneId: string): Promise<OptimizeResponse> => {
    if (isDemoMode) return demoSimulator.optimize(zoneId, false);
    try {
      return await fetchJson<OptimizeResponse>(`/optimize/${zoneId}`, {
        method: 'POST',
      });
    } catch {
      return demoSimulator.optimize(zoneId, false);
    }
  },

  testOptimize: async (zoneId: string): Promise<OptimizeResponse> => {
    if (isDemoMode) return demoSimulator.optimize(zoneId, true);
    try {
      return await fetchJson<OptimizeResponse>(`/test_optimize/${zoneId}`, {
        method: 'POST',
      });
    } catch {
      return demoSimulator.optimize(zoneId, true);
    }
  },

  confirmComfort: async (zoneId: string, comfortable: boolean): Promise<ConfirmResponse> => {
    if (isDemoMode) return demoSimulator.confirm(zoneId, comfortable);
    try {
      return await fetchJson<ConfirmResponse>(`/confirm/${zoneId}`, {
        method: 'POST',
        body: JSON.stringify({ comfortable }),
      });
    } catch {
      return demoSimulator.confirm(zoneId, comfortable);
    }
  },

  // History
  getHistory: async (): Promise<HistoryEntry[]> => {
    if (isDemoMode) return demoSimulator.getHistory();
    try {
      return await fetchJson<HistoryEntry[]>('/history');
    } catch {
      return demoSimulator.getHistory();
    }
  },
};
