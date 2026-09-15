import React, { useState } from 'react';
import { apiBaseUrl, setApiBaseUrl } from '../lib/api';
import { Server, Save, X } from 'lucide-react';

interface ApiConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ApiConfigModal: React.FC<ApiConfigModalProps> = ({ isOpen, onClose }) => {
  const [url, setUrl] = useState(apiBaseUrl);

  if (!isOpen) return null;

  const handleSave = () => {
    setApiBaseUrl(url);
    window.location.reload();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 select-none">
      <div className="bg-[#0b111e] border border-slate-800 rounded-xl w-full max-w-md p-5 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Server className="w-5 h-5 text-cyan-400" />
            <h3 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider">
              FASTAPI BACKEND CONNECTION
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-2 text-xs font-mono">
          <label className="text-slate-400 uppercase block">BACKEND BASE URL</label>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8000"
            className="w-full bg-[#080c14] border border-slate-800 rounded px-3 py-2 text-slate-100 font-mono focus:outline-none focus:border-cyan-500"
          />
          <p className="text-[11px] text-slate-500">
            Default: <code className="text-cyan-400">http://localhost:8000</code>. Updates will reload the connection status.
          </p>
        </div>

        <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs"
          >
            CANCEL
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono text-xs font-bold flex items-center space-x-1"
          >
            <Save className="w-4 h-4" />
            <span>UPDATE BASE URL</span>
          </button>
        </div>
      </div>
    </div>
  );
};
