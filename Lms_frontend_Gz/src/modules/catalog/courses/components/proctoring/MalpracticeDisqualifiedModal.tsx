import React from 'react';
import { Home, AlertTriangle, ShieldAlert } from 'lucide-react';
import { MalpracticeIncident } from './types';

interface MalpracticeDisqualifiedModalProps {
  incidents: MalpracticeIncident[];
  maxWarnings: number;
  onExit: () => void;
}

export const MalpracticeDisqualifiedModal: React.FC<MalpracticeDisqualifiedModalProps> = ({
  incidents,
  maxWarnings,
  onExit,
}) => {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in"
    >
      <div className="w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl border-2 border-red-600">
        {/* Disqualified Banner */}
        <div className="bg-red-700 px-6 py-5 text-white flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-white/20">
            <ShieldAlert className="w-8 h-8 text-white" />
          </div>
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-red-200">
              Proctored Examination Terminated
            </span>
            <h2 className="text-xl font-bold tracking-tight">
              Exam Disqualified: Max Warnings Exceeded
            </h2>
          </div>
        </div>

        {/* Details & Incident Log */}
        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-900 leading-relaxed">
            You exceeded the course limit of <strong>{maxWarnings} malpractice warnings</strong>. Your exam session has been locked and marked as failed due to proctoring policy non-compliance.
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              Recorded Malpractice Incidents Log ({incidents.length})
            </h4>

            <div className="space-y-2">
              {incidents.map((incident, idx) => (
                <div
                  key={incident.id || idx}
                  className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs flex items-start justify-between gap-3"
                >
                  <div>
                    <span className="font-semibold text-red-700 block">
                      #{incident.warningNumber}: {incident.title}
                    </span>
                    <span className="text-slate-600 mt-0.5 block">
                      {incident.description}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500 whitespace-nowrap bg-white px-2 py-0.5 rounded border border-slate-200">
                    {incident.timestamp}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={onExit}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs flex items-center justify-center gap-2 cursor-pointer transition-colors shadow-sm"
          >
            <Home className="w-4 h-4" />
            <span>Return to Course Dashboard</span>
          </button>
        </div>
      </div>
    </div>
  );
};
