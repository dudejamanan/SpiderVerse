import React, { useState, useEffect } from 'react';
import type { BuildingConfig, RoomConfig, Location } from '../types';
import { useConfigureBuilding, useLocations } from '../hooks/useTwin';
import { X, Plus, Trash2, Save, Building2, SlidersHorizontal } from 'lucide-react';

interface BuildingConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentConfig?: BuildingConfig;
}

export const BuildingConfigModal: React.FC<BuildingConfigModalProps> = ({
  isOpen,
  onClose,
  currentConfig,
}) => {
  const { data: locations = [] } = useLocations();
  const configureMutation = useConfigureBuilding();

  const [locationId, setLocationId] = useState('chennai');
  const [buildingId, setBuildingId] = useState('default_building');
  const [rooms, setRooms] = useState<RoomConfig[]>([]);

  useEffect(() => {
    if (currentConfig) {
      setBuildingId(currentConfig.building_id || 'default_building');
      if (currentConfig.location?.location_id) {
        setLocationId(currentConfig.location.location_id);
      }
      setRooms(currentConfig.rooms || []);
    }
  }, [currentConfig]);

  if (!isOpen) return null;

  const handleAddRoom = () => {
    const newId = `room_${rooms.length}`;
    const newRoom: RoomConfig = {
      room_id: newId,
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
    };
    setRooms([...rooms, newRoom]);
  };

  const handleRemoveRoom = (index: number) => {
    if (rooms.length <= 1) return; // Keep at least 1 room
    setRooms(rooms.filter((_, i) => i !== index));
  };

  const handleRoomChange = (index: number, field: keyof RoomConfig, value: any) => {
    const updated = [...rooms];
    updated[index] = { ...updated[index], [field]: value };
    setRooms(updated);
  };

  const handleSave = () => {
    configureMutation.mutate(
      {
        location_id: locationId,
        building_id: buildingId,
        rooms,
      },
      {
        onSuccess: () => {
          onClose();
        },
      }
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 select-none">
      <div className="bg-[#0b111e] border border-slate-800 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Building2 className="w-5 h-5 text-cyan-400" />
            <h2 className="text-sm font-mono font-bold text-slate-100 uppercase tracking-wider">
              BUILDING & ROOM TWIN CONFIGURATION
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded bg-slate-900 text-slate-400 hover:text-slate-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-6 custom-scrollbar">
          {/* Location & Building Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-900/60 p-4 rounded-lg border border-slate-800">
            <div>
              <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
                BUILDING ID
              </label>
              <input
                type="text"
                value={buildingId}
                onChange={(e) => setBuildingId(e.target.value)}
                className="w-full bg-[#080c14] border border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
                LOCATION / GEOGRAPHY
              </label>
              <select
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
                className="w-full bg-[#080c14] border border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-cyan-400 focus:outline-none"
              >
                {locations.map((loc) => (
                  <option key={loc.location_id} value={loc.location_id}>
                    {loc.name}, {loc.country} ({loc.latitude}°, {loc.longitude}°)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Rooms List Configuration */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                ROOMS & THERMAL PHYSICS PARAMETERS ({rooms.length})
              </h3>
              <button
                onClick={handleAddRoom}
                className="px-3 py-1 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 hover:bg-cyan-900 text-xs font-mono flex items-center space-x-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>ADD ROOM</span>
              </button>
            </div>

            <div className="space-y-4">
              {rooms.map((room, idx) => (
                <div
                  key={idx}
                  className="bg-[#080c14] border border-slate-800 rounded-lg p-4 space-y-3 relative"
                >
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div className="flex items-center space-x-2">
                      <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
                      <input
                        type="text"
                        value={room.room_id}
                        onChange={(e) => handleRoomChange(idx, 'room_id', e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs font-mono font-bold text-cyan-400 focus:outline-none"
                      />
                    </div>
                    {rooms.length > 1 && (
                      <button
                        onClick={() => handleRemoveRoom(idx)}
                        className="p-1 rounded text-red-400 hover:bg-red-950"
                        title="Remove room"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Room Parameter Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">AREA (m²)</span>
                      <input
                        type="number"
                        value={room.area_m2}
                        onChange={(e) => handleRoomChange(idx, 'area_m2', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">HEIGHT (m)</span>
                      <input
                        type="number"
                        value={room.height_m}
                        onChange={(e) => handleRoomChange(idx, 'height_m', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">WINDOW AREA (m²)</span>
                      <input
                        type="number"
                        value={room.window_area_m2}
                        onChange={(e) => handleRoomChange(idx, 'window_area_m2', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">HVAC CAP (W)</span>
                      <input
                        type="number"
                        value={room.hvac_capacity_w}
                        onChange={(e) => handleRoomChange(idx, 'hvac_capacity_w', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">THERMAL R</span>
                      <input
                        type="number"
                        step="0.1"
                        value={room.R}
                        onChange={(e) => handleRoomChange(idx, 'R', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">THERMAL C</span>
                      <input
                        type="number"
                        value={room.C}
                        onChange={(e) => handleRoomChange(idx, 'C', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">COP RATING</span>
                      <input
                        type="number"
                        step="0.1"
                        value={room.cop}
                        onChange={(e) => handleRoomChange(idx, 'cop', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>

                    <div>
                      <span className="text-[9px] text-slate-500 uppercase block">INITIAL TEMP (°C)</span>
                      <input
                        type="number"
                        step="0.5"
                        value={room.initial_temp_c}
                        onChange={(e) => handleRoomChange(idx, 'initial_temp_c', parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-slate-800 bg-[#080c14] flex items-center justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs"
          >
            CANCEL
          </button>
          <button
            onClick={handleSave}
            disabled={configureMutation.isPending}
            className="px-4 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono text-xs font-bold flex items-center space-x-1.5"
          >
            <Save className="w-4 h-4" />
            <span>SAVE BUILDING CONFIG</span>
          </button>
        </div>
      </div>
    </div>
  );
};
