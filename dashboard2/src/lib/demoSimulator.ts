import type{
  BuildingConfig,
  Location,
  TwinState,
  LLMConstraint,
  OptimizeResponse,
  ConfirmResponse,
  HistoryEntry,
  FeedbackResponse,
} from '../types';

// Default Demo Locations
export const DEMO_LOCATIONS: Location[] = [
  { location_id: 'chennai', name: 'Chennai', country: 'India', latitude: 13.0827, longitude: 80.2707 },
  { location_id: 'singapore', name: 'Singapore', country: 'Singapore', latitude: 1.3521, longitude: 103.8198 },
  { location_id: 'tokyo', name: 'Tokyo', country: 'Japan', latitude: 35.6762, longitude: 139.6503 },
  { location_id: 'berlin', name: 'Berlin', country: 'Germany', latitude: 52.5200, longitude: 13.4050 },
  { location_id: 'san_francisco', name: 'San Francisco', country: 'USA', latitude: 37.7749, longitude: -122.4194 },
];

export class DemoTwinSimulator {
  private locationId = 'chennai';
  private region = 'Asia/South';

  private roomsConfig: BuildingConfig = {
    building_id: 'twin_nexus_hq',
    latitude: 13.0827,
    longitude: 80.2707,
    location: DEMO_LOCATIONS[0],
    rooms: [
      {
        room_id: 'room_0',
        area_m2: 35.0,
        height_m: 3.2,
        window_area_m2: 6.0,
        R: 2.1,
        C: 160000.0,
        shading_coefficient: 0.45,
        ventilation_ach: 1.4,
        hvac_capacity_w: 2400.0,
        cop: 3.6,
        initial_temp_c: 25.4,
        initial_rh_pct: 54.0,
        initial_co2_ppm: 510.0,
        initial_occupancy: 4,
      },
      {
        room_id: 'server_lab_1',
        area_m2: 24.0,
        height_m: 2.8,
        window_area_m2: 2.0,
        R: 1.8,
        C: 130000.0,
        shading_coefficient: 0.2,
        ventilation_ach: 2.5,
        hvac_capacity_w: 3500.0,
        cop: 3.2,
        initial_temp_c: 22.1,
        initial_rh_pct: 42.0,
        initial_co2_ppm: 430.0,
        initial_occupancy: 1,
      },
      {
        room_id: 'executive_suite',
        area_m2: 45.0,
        height_m: 3.5,
        window_area_m2: 12.0,
        R: 2.5,
        C: 210000.0,
        shading_coefficient: 0.6,
        ventilation_ach: 1.2,
        hvac_capacity_w: 3000.0,
        cop: 3.8,
        initial_temp_c: 23.8,
        initial_rh_pct: 48.0,
        initial_co2_ppm: 460.0,
        initial_occupancy: 2,
      },
    ],
  };

  private twinStates: Record<string, TwinState> = {};
  private constraints: Record<string, LLMConstraint> = {};
  private conversations: Record<string, { active: boolean; iteration: number }> = {};
  private history: HistoryEntry[] = [];

  constructor() {
    this.resetStates();
  }

  private resetStates() {
    this.twinStates = {};
    this.roomsConfig.rooms.forEach((r) => {
      this.twinStates[r.room_id] = {
        indoor_temp_c: r.initial_temp_c,
        rh_pct: r.initial_rh_pct,
        co2_ppm: r.initial_co2_ppm,
        occupancy_count: r.initial_occupancy,
        energy_draw_kw: 1.15,
        current_setpoint_c: 23.5,
        timestamp: new Date().toISOString(),
        zone_id: r.room_id,
      };
      this.conversations[r.room_id] = { active: false, iteration: 1 };
    });

    // Initial dummy history entry
    this.history = [
      {
        zone_id: 'room_0',
        constraint: {
          zone_id: 'room_0',
          parameter: 'temperature',
          direction: 'decrease',
          intensity: 'high',
          confidence: 0.94,
          raw_text: 'It is way too hot in room_0, please cool it down!',
        },
        action: {
          zone_id: 'room_0',
          setpoint_delta_c: -1.5,
          new_setpoint_c: 23.5,
        },
        hvac_power_w: 1850.0,
        hvac_capacity_w: 2400.0,
        simulation_dt_seconds: 300,
        energy_draw_kwh: 0.154,
        new_state: { ...this.twinStates['room_0'] },
        timestamp: new Date(Date.now() - 3600000).toISOString(),
      },
    ];
  }

  getBuildingConfig(): BuildingConfig {
    const loc = DEMO_LOCATIONS.find((l) => l.location_id === this.locationId) || DEMO_LOCATIONS[0];
    return {
      ...this.roomsConfig,
      location: loc,
    };
  }

  configureBuilding(config: { location_id: string; building_id: string; rooms: any[] }): BuildingConfig {
    this.locationId = config.location_id;
    const loc = DEMO_LOCATIONS.find((l) => l.location_id === config.location_id) || DEMO_LOCATIONS[0];

    this.roomsConfig = {
      building_id: config.building_id || 'custom_building',
      latitude: loc.latitude,
      longitude: loc.longitude,
      location: loc,
      rooms: config.rooms.map((r, i) => ({
        room_id: r.room_id || `room_${i}`,
        area_m2: r.area_m2 || 30.0,
        height_m: r.height_m || 3.0,
        window_area_m2: r.window_area_m2 || 5.0,
        R: r.R || 2.0,
        C: r.C || 156000.0,
        shading_coefficient: r.shading_coefficient || 0.5,
        ventilation_ach: r.ventilation_ach || 1.5,
        hvac_capacity_w: r.hvac_capacity_w || 2000.0,
        cop: r.cop || 3.5,
        initial_temp_c: r.initial_temp_c || 24.0,
        initial_rh_pct: r.initial_rh_pct || 50.0,
        initial_co2_ppm: r.initial_co2_ppm || 420.0,
        initial_occupancy: r.initial_occupancy || 0,
      })),
    };

    this.resetStates();
    return this.getBuildingConfig();
  }

  getLocations(): Location[] {
    return DEMO_LOCATIONS;
  }

  getRegion(): { region: string } {
    return { region: this.region };
  }

  setRegion(region: string): { message: string; region: string } {
    this.region = region;
    return { message: 'Region updated', region: this.region };
  }

  getTwinState(zoneId: string): TwinState {
    let state = this.twinStates[zoneId];
    if (!state) {
      const room = this.roomsConfig.rooms.find((r) => r.room_id === zoneId) || this.roomsConfig.rooms[0];
      state = {
        indoor_temp_c: room.initial_temp_c,
        rh_pct: room.initial_rh_pct,
        co2_ppm: room.initial_co2_ppm,
        occupancy_count: room.initial_occupancy,
        energy_draw_kw: 1.0,
        current_setpoint_c: 24.0,
        timestamp: new Date().toISOString(),
        zone_id: zoneId,
      };
      this.twinStates[zoneId] = state;
    }

    // Thermal drift simulation on poll step
    const targetTemp = state.current_setpoint_c;
    const tempDiff = state.indoor_temp_c - targetTemp;

    // Small ambient thermal drift toward setpoint or heat load
    const heatLoad = (state.occupancy_count * 0.08); // occupancy adds heat
    const coolingDrive = Math.abs(tempDiff) > 0.1 ? (tempDiff > 0 ? -0.12 : 0.10) : 0;
    
    let newTemp = state.indoor_temp_c + coolingDrive + (Math.random() * 0.06 - 0.03) + heatLoad * 0.01;
    newTemp = Math.round(newTemp * 100) / 100;

    let newRh = state.rh_pct + (Math.random() * 0.4 - 0.2);
    newRh = Math.max(30, Math.min(80, Math.round(newRh * 10) / 10));

    let newCo2 = state.co2_ppm + (state.occupancy_count > 0 ? Math.random() * 5 : -Math.random() * 3);
    newCo2 = Math.max(400, Math.min(1800, Math.round(newCo2)));

    const isCoolingActive = tempDiff > 0.3;
    const baseEnergy = isCoolingActive ? 1.4 + Math.abs(tempDiff) * 0.3 : 0.3;
    const newEnergy = Math.round((baseEnergy + Math.random() * 0.1) * 100) / 100;

    const updatedState: TwinState = {
      ...state,
      indoor_temp_c: newTemp,
      rh_pct: newRh,
      co2_ppm: newCo2,
      energy_draw_kw: newEnergy,
      timestamp: new Date().toISOString(),
    };

    this.twinStates[zoneId] = updatedState;
    return updatedState;
  }

  testHvac(zoneId: string, hvacPowerW: number) {
    const oldState = this.getTwinState(zoneId);
    const room = this.roomsConfig.rooms.find((r) => r.room_id === zoneId);
    const maxPower = room ? room.hvac_capacity_w : 2000.0;

    // Heating (positive power) or Cooling (negative power)
    const deltaT = (hvacPowerW / maxPower) * 0.8;
    const newTemp = Math.round((oldState.indoor_temp_c + deltaT) * 100) / 100;

    const newState: TwinState = {
      ...oldState,
      indoor_temp_c: newTemp,
      energy_draw_kw: Math.abs(hvacPowerW) / 1000.0,
      timestamp: new Date().toISOString(),
    };

    this.twinStates[zoneId] = newState;

    const entry: HistoryEntry = {
      zone_id: zoneId,
      type: 'manual_test',
      hvac_power_w: hvacPowerW,
      simulation_dt_seconds: 300,
      energy_draw_kwh: (Math.abs(hvacPowerW) / 1000.0) * (300 / 3600),
      old_state: oldState,
      new_state: newState,
      timestamp: new Date().toISOString(),
    };

    this.history.unshift(entry);

    return {
      hvac_power_w: hvacPowerW,
      old_state: oldState,
      new_state: newState,
    };
  }

  submitFeedback(zoneId: string, text: string): FeedbackResponse {
    const lower = text.toLowerCase();
    
    // Check if clarification needed
    if (lower.length < 3) {
      return {
        clarification_needed: true,
        message: 'Please provide a clearer comfort complaint (e.g., "it is too hot", "too humid", "stuffy air").',
      };
    }

    let parameter = 'temperature';
    let direction: 'increase' | 'decrease' = 'decrease';
    let intensity: 'low' | 'moderate' | 'high' = 'moderate';
    let confidence = 0.88;

    if (lower.includes('hot') || lower.includes('warm') || lower.includes('sweating') || lower.includes('boiling')) {
      parameter = 'temperature';
      direction = 'decrease';
      intensity = lower.includes('very') || lower.includes('too') || lower.includes('boiling') ? 'high' : 'moderate';
      confidence = 0.95;
    } else if (lower.includes('cold') || lower.includes('freezing') || lower.includes('chilly')) {
      parameter = 'temperature';
      direction = 'increase';
      intensity = lower.includes('freezing') ? 'high' : 'moderate';
      confidence = 0.92;
    } else if (lower.includes('humid') || lower.includes('sticky') || lower.includes('muggy')) {
      parameter = 'humidity';
      direction = 'decrease';
      intensity = 'moderate';
      confidence = 0.89;
    } else if (lower.includes('dry') || lower.includes('parched')) {
      parameter = 'humidity';
      direction = 'increase';
      intensity = 'low';
      confidence = 0.85;
    } else if (lower.includes('stuffy') || lower.includes('co2') || lower.includes('suffocating')) {
      parameter = 'co2';
      direction = 'decrease';
      intensity = 'high';
      confidence = 0.91;
    }

    const constraint: LLMConstraint = {
      zone_id: zoneId,
      parameter,
      direction,
      intensity,
      confidence,
      raw_text: text,
    };

    this.constraints[zoneId] = constraint;
    this.conversations[zoneId] = { active: true, iteration: 1 };

    return {
      message: 'Feedback parsed successfully',
      clarification_needed: false,
      ready_for_optimization: true,
      constraint,
    };
  }

  testConstraint(zoneId: string) {
    const constraint: LLMConstraint = {
      zone_id: zoneId,
      parameter: 'temperature',
      direction: 'decrease',
      intensity: 'moderate',
      confidence: 0.95,
      raw_text: 'It is too hot in this room',
    };
    this.constraints[zoneId] = constraint;
    return {
      message: 'Test constraint created',
      constraint,
    };
  }

  optimize(zoneId: string, isMock: boolean = false): OptimizeResponse {
    let constraint = this.constraints[zoneId];
    if (!constraint) {
      constraint = {
        zone_id: zoneId,
        parameter: 'temperature',
        direction: 'decrease',
        intensity: 'moderate',
        confidence: 0.92,
        raw_text: 'Default thermal adjustment request',
      };
      this.constraints[zoneId] = constraint;
    }

    const twinState = this.getTwinState(zoneId);
    const room = this.roomsConfig.rooms.find((r) => r.room_id === zoneId);
    const hvacCapacity = room ? room.hvac_capacity_w : 2000.0;

    let delta = constraint.direction === 'decrease' ? -1.5 : 1.5;
    if (constraint.intensity === 'high') delta *= 1.33;
    if (constraint.intensity === 'low') delta *= 0.66;
    if (isMock) delta = constraint.direction === 'decrease' ? -1.0 : 1.0;

    const currentSetpoint = twinState.current_setpoint_c;
    const newSetpoint = Math.max(17.0, Math.min(29.0, Math.round((currentSetpoint + delta) * 10) / 10));
    const actualDelta = Math.round((newSetpoint - currentSetpoint) * 10) / 10;

    const hvacPowerW = actualDelta < 0 ? -hvacCapacity * 0.85 : hvacCapacity * 0.7;

    // Apply change to twin state
    const newTemp = Math.round((twinState.indoor_temp_c + actualDelta * 0.6) * 100) / 100;
    const newState: TwinState = {
      ...twinState,
      current_setpoint_c: newSetpoint,
      indoor_temp_c: newTemp,
      energy_draw_kw: Math.round((Math.abs(hvacPowerW) / 1000.0 + 0.3) * 100) / 100,
      timestamp: new Date().toISOString(),
    };

    this.twinStates[zoneId] = newState;

    const action = {
      zone_id: zoneId,
      setpoint_delta_c: actualDelta,
      new_setpoint_c: newSetpoint,
    };

    const energyDrawKwh = Math.round(((Math.abs(hvacPowerW) / 1000.0) * (300 / 3600)) * 1000) / 1000;

    const historyEntry: HistoryEntry = {
      zone_id: zoneId,
      constraint,
      action,
      hvac_power_w: hvacPowerW,
      hvac_capacity_w: hvacCapacity,
      simulation_dt_seconds: 300,
      energy_draw_kwh: energyDrawKwh,
      new_state: newState,
      timestamp: new Date().toISOString(),
    };

    this.history.unshift(historyEntry);

    return {
      constraint,
      action,
      hvac_power_w: hvacPowerW,
      hvac_capacity_w: hvacCapacity,
      simulation_dt_seconds: 300,
      energy_draw_kwh: energyDrawKwh,
      new_state: newState,
      ask_confirmation: true,
      confirmation_question: `Adjusted setpoint to ${newSetpoint.toFixed(1)}°C. Is the room comfortable now?`,
    };
  }

  confirm(zoneId: string, comfortable: boolean): ConfirmResponse {
    const conv = this.conversations[zoneId] || { active: true, iteration: 1 };

    if (comfortable) {
      this.conversations[zoneId] = { active: false, iteration: 1 };
      return {
        message: 'Comfort achieved. HVAC optimization complete.',
        conversation_active: false,
      };
    } else {
      const nextIteration = conv.iteration + 1;
      this.conversations[zoneId] = { active: true, iteration: nextIteration };
      return {
        message: 'Please provide additional feedback to refine setpoints.',
        conversation_active: true,
        iteration: nextIteration,
        ask_feedback: true,
      };
    }
  }

  getHistory(): HistoryEntry[] {
    return this.history;
  }
}

export const demoSimulator = new DemoTwinSimulator();
