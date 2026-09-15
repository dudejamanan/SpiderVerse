export type Location = {
  location_id: string;
  name: string;
  country: string;
  latitude: number;
  longitude: number;
}

export type RoomConfig = {
  room_id: string;
  area_m2: number;
  height_m: number;
  window_area_m2: number;
  R: number;
  C: number;
  shading_coefficient: number;
  ventilation_ach: number;
  hvac_capacity_w: number;
  cop: number;
  initial_temp_c: number;
  initial_rh_pct: number;
  initial_co2_ppm: number;
  initial_occupancy: number;
}

export type BuildingConfig ={
  building_id: string;
  latitude: number;
  longitude: number;
  rooms: RoomConfig[];
  location?: Location;
}

export type BuildingConfigRequest = {
  location_id: string;
  building_id: string;
  rooms: RoomConfig[];
}

export type TwinState = {
  indoor_temp_c: number;
  rh_pct: number;
  co2_ppm: number;
  occupancy_count: number;
  energy_draw_kw: number;
  current_setpoint_c: number;
  timestamp?: string | number;
  zone_id?: string;
}

export type LLMConstraint = {
  zone_id: string;
  parameter: string; // "temperature" | "humidity" | "co2"
  direction: 'increase' | 'decrease' | string;
  intensity: 'low' | 'moderate' | 'high' | string;
  confidence: number; // 0.0 to 1.0
  raw_text: string;
}

export type RLAction = {
  zone_id?: string;
  setpoint_delta_c: number;
  new_setpoint_c: number;
}

export type FeedbackRequest = {
  zone_id: string;
  text: string;
}

export type FeedbackResponse = {
  clarification_needed: boolean;
  message: string;
  ready_for_optimization?: boolean;
  constraint?: LLMConstraint;
}

export type OptimizeResponse = {
  constraint: LLMConstraint;
  action: RLAction;
  hvac_power_w: number;
  hvac_capacity_w: number;
  simulation_dt_seconds: number;
  energy_draw_kwh: number;
  new_state: TwinState;
  ask_confirmation: boolean;
  confirmation_question: string;
}

export type ConfirmRequest = {
  comfortable: boolean;
}

export type ConfirmResponse = {
  message: string;
  conversation_active: boolean;
  iteration?: number;
  ask_feedback?: boolean;
}

export type HistoryEntry = {
  zone_id: string;
  type?: string;
  constraint?: LLMConstraint;
  action?: RLAction;
  hvac_power_w?: number;
  hvac_capacity_w?: number;
  simulation_dt_seconds?: number;
  energy_draw_kwh?: number;
  old_state?: TwinState;
  new_state?: TwinState;
  timestamp?: string;
}

export type RegionResponse = {
  region: string;
}

export type TestHvacResponse = {
  hvac_power_w: number;
  old_state: TwinState;
  new_state: TwinState;
}

export type HealthResponse = {
  status: string;
  message?: string;
}
