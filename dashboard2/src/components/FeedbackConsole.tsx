import React, { useState } from 'react';
import type{
  LLMConstraint,
  FeedbackResponse,
  OptimizeResponse,
} from '../types';
import {
  useSubmitFeedback,
  useOptimize,
  useTestOptimize,
  useTestConstraint,
} from '../hooks/useTwin';
import {
  Cpu,
  Send,
  Zap,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  TrendingUp,
  Sliders,
  Sparkles,
  Bot,
  Layers,
  ArrowRight,
} from 'lucide-react';

interface FeedbackConsoleProps {
  activeZoneId: string;
  onOptimizationDone: (res: OptimizeResponse) => void;
}

const PRESET_COMPLAINTS = [
  "It's too hot in here, please cool down the room!",
  "It is suffocating, stuffy, and warm in this room.",
  "It's freezing cold in here, turn up the heat.",
  "It's way too humid and sticky.",
];

export const FeedbackConsole: React.FC<FeedbackConsoleProps> = ({
  activeZoneId,
  onOptimizationDone,
}) => {
  const [complaintText, setComplaintText] = useState('');
  const [lastConstraint, setLastConstraint] = useState<LLMConstraint | null>(null);
  const [clarificationMsg, setClarificationMsg] = useState<string | null>(null);

  const feedbackMutation = useSubmitFeedback();
  const optimizeMutation = useOptimize();
  const testOptimizeMutation = useTestOptimize();
  const testConstraintMutation = useTestConstraint();

  const handleSubmitComplaint = (textToSubmit?: string) => {
    const text = textToSubmit || complaintText;
    if (!text.trim()) return;

    setClarificationMsg(null);
    feedbackMutation.mutate(
      { zoneId: activeZoneId, text },
      {
        onSuccess: (res: FeedbackResponse) => {
          if (res.clarification_needed) {
            setClarificationMsg(res.message);
            setLastConstraint(null);
          } else if (res.constraint) {
            setLastConstraint(res.constraint);
            setClarificationMsg(null);
          }
        },
      }
    );
  };

  const handleRunRlOptimize = () => {
    optimizeMutation.mutate(activeZoneId, {
      onSuccess: (res) => {
        onOptimizationDone(res);
      },
    });
  };

  const handleRunMockOptimize = () => {
    testOptimizeMutation.mutate(activeZoneId, {
      onSuccess: (res) => {
        onOptimizationDone(res);
      },
    });
  };

  const handleInjectTestConstraint = () => {
    testConstraintMutation.mutate(activeZoneId, {
      onSuccess: (res) => {
        if (res.constraint) {
          setLastConstraint(res.constraint);
          setClarificationMsg(null);
        }
      },
    });
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col space-y-4 select-none">
      {/* Console Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-mono font-bold tracking-widest text-slate-300 uppercase">
            NLP CONSTRAINT EXTRACTION PIPELINE
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
          SIGNAL PARSER READY
        </span>
      </div>

      {/* Signal Input Input Bar */}
      <div className="space-y-2">
        <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
          <span>Natural Language Comfort Feedback Input</span>
          <span className="text-slate-500 text-[10px]">ZONE: {activeZoneId.toUpperCase()}</span>
        </label>

        <div className="relative flex items-center">
          <input
            type="text"
            value={complaintText}
            onChange={(e) => setComplaintText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmitComplaint()}
            placeholder={`Enter complaint e.g., "It is too hot in ${activeZoneId}"...`}
            className="w-full bg-[#080c14] border border-slate-800 focus:border-cyan-500/80 rounded-lg px-3.5 py-2.5 pr-28 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 transition-all"
          />
          <button
            onClick={() => handleSubmitComplaint()}
            disabled={feedbackMutation.isPending || !complaintText.trim()}
            className="absolute right-1.5 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono text-xs font-bold flex items-center space-x-1.5 transition-all disabled:opacity-40"
          >
            {feedbackMutation.isPending ? (
              <Cpu className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            <span>EXTRACT</span>
          </button>
        </div>

        {/* Preset Chips for quick interactive testing */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          <span className="text-[10px] font-mono text-slate-500 py-0.5">Quick Signals:</span>
          {PRESET_COMPLAINTS.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => {
                setComplaintText(preset);
                handleSubmitComplaint(preset);
              }}
              className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800 transition-all hover:border-cyan-500/40"
            >
              "{preset}"
            </button>
          ))}
        </div>
      </div>

      {/* Clarification Alert Inline */}
      {clarificationMsg && (
        <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs font-mono flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Clarification Required: </span>
            <span>{clarificationMsg}</span>
          </div>
        </div>
      )}

      {/* Structured Constraint Extraction Pipeline Visualizer */}
      {lastConstraint && (
        <div className="bg-[#080c14] border border-cyan-500/30 rounded-lg p-3.5 space-y-3 relative overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                DECODED STRUCTURED CONSTRAINT
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              CONFIDENCE: <strong className="text-emerald-400">{(lastConstraint.confidence * 100).toFixed(0)}%</strong>
            </span>
          </div>

          {/* Pipeline Parameter Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">PARAMETER</span>
              <span className="font-bold text-cyan-400 uppercase">{lastConstraint.parameter}</span>
            </div>

            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">DIRECTION</span>
              <div className="flex items-center space-x-1">
                {lastConstraint.direction === 'decrease' ? (
                  <TrendingDown className="w-3.5 h-3.5 text-cyan-400" />
                ) : (
                  <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                )}
                <span className={`font-bold uppercase ${lastConstraint.direction === 'decrease' ? 'text-cyan-400' : 'text-amber-400'}`}>
                  {lastConstraint.direction}
                </span>
              </div>
            </div>

            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">INTENSITY</span>
              <span className="font-bold text-purple-400 uppercase">{lastConstraint.intensity}</span>
            </div>

            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-[9px] text-slate-500 uppercase block">TARGET ZONE</span>
              <span className="font-bold text-slate-200 uppercase">{lastConstraint.zone_id}</span>
            </div>
          </div>

          {/* Raw Signal Text readout */}
          <div className="text-[11px] font-mono text-slate-400 bg-slate-900/60 p-2 rounded border border-slate-800/80">
            <span className="text-slate-500">RAW SIGNAL: </span>
            <span className="text-slate-300">"{lastConstraint.raw_text}"</span>
          </div>
        </div>
      )}

      {/* Action Triggers: RL Optimizer vs Mock Controller */}
      <div className="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleRunRlOptimize}
            disabled={optimizeMutation.isPending}
            className="px-4 py-2 rounded bg-gradient-to-r from-cyan-600 to-emerald-600 hover:from-cyan-500 hover:to-emerald-500 text-slate-950 font-mono text-xs font-bold flex items-center space-x-2 shadow-lg transition-all active:scale-95 disabled:opacity-50"
          >
            {optimizeMutation.isPending ? (
              <Cpu className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4 fill-current" />
            )}
            <span>EXECUTE RL POLICY OPTIMIZATION</span>
          </button>

          <button
            onClick={handleRunMockOptimize}
            disabled={testOptimizeMutation.isPending}
            className="px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs font-semibold flex items-center space-x-1.5 border border-slate-700 transition-all disabled:opacity-50"
            title="Run rule-based mock controller (±1.0°C step)"
          >
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            <span>MOCK OPTIMIZE (±1°C)</span>
          </button>
        </div>

        <button
          onClick={handleInjectTestConstraint}
          disabled={testConstraintMutation.isPending}
          className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline underline-offset-2 flex items-center space-x-1 cursor-pointer"
        >
          <span>Inject Test Constraint</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
