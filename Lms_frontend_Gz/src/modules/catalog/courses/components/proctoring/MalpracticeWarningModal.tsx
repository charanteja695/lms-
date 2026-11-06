import React from 'react';
import {
  AlertOctagon,
  Maximize2,
  ShieldAlert,
  ArrowRight,
  Smartphone,
  Headphones,
  FileText,
  Users,
  UserX,
} from 'lucide-react';
import { MalpracticeIncident } from './types';

interface MalpracticeWarningModalProps {
  incident: MalpracticeIncident | null;
  warningCount: number;
  maxWarnings: number;
  onResume: () => void;
}

export const MalpracticeWarningModal: React.FC<MalpracticeWarningModalProps> = ({
  incident,
  warningCount,
  maxWarnings,
  onResume,
}) => {
  if (!incident) return null;

  const isLastWarning = warningCount === maxWarnings - 1;
  const remaining = Math.max(0, maxWarnings - warningCount);
  const isObjectDetection =
    incident.type === 'prohibited_object' ||
    incident.type === 'multiple_faces' ||
    incident.type === 'no_face';

  const getObjectIcon = () => {
    const obj = incident.detectedObject?.toLowerCase() || '';
    if (obj.includes('phone') || obj.includes('mobile')) return <Smartphone className="w-5 h-5 text-red-600" />;
    if (obj.includes('ear') || obj.includes('headphone')) return <Headphones className="w-5 h-5 text-red-600" />;
    if (obj.includes('note') || obj.includes('paper') || obj.includes('book')) return <FileText className="w-5 h-5 text-red-600" />;
    if (obj.includes('person') || obj.includes('face')) return <Users className="w-5 h-5 text-red-600" />;
    if (incident.type === 'no_face') return <UserX className="w-5 h-5 text-red-600" />;
    return <ShieldAlert className="w-5 h-5 text-red-600" />;
  };

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in"
    >
      <div className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl border-2 border-red-500">
        {/* Urgent Header */}
        <div className="bg-red-600 px-6 py-4 text-white flex items-center gap-3">
          <div className="p-2 rounded-xl bg-white/20">
            <AlertOctagon className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold tracking-tight">
              Malpractice Warning #{warningCount} of {maxWarnings}
            </h3>
            <p className="text-xs text-red-100 font-medium">
              {isObjectDetection ? 'AI Camera Visual Prohibited Detection' : 'Proctored Environment Integrity Alert'}
            </p>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          {/* Main violation card */}
          <div className="p-4 rounded-xl bg-red-50 border border-red-200">
            <div className="flex items-start gap-3">
              <div className="p-1.5 rounded-lg bg-red-100 shrink-0 mt-0.5">
                {getObjectIcon()}
              </div>
              <div className="flex-1">
                <p className="text-sm font-bold text-red-900">
                  {incident.title}
                </p>
                <p className="text-xs text-red-700 mt-1 leading-relaxed">
                  {incident.description}
                </p>

                {/* Detected Item Details if object detected */}
                {incident.detectedObject && (
                  <div className="mt-2.5 p-2 rounded-lg bg-white border border-red-200 flex items-center justify-between text-xs">
                    <span className="font-bold text-red-800 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                      Detected Item: {incident.detectedObject}
                    </span>
                    {incident.confidence && (
                      <span className="text-[11px] font-mono text-red-600 font-semibold">
                        {incident.confidence}% AI Confidence
                      </span>
                    )}
                  </div>
                )}

                <div className="mt-2 text-[11px] text-red-600 font-mono">
                  Recorded at {incident.timestamp}
                </div>
              </div>
            </div>
          </div>

          {/* Actionable instructions if object was detected */}
          {isObjectDetection && (
            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
              <strong className="block font-bold">Required Candidate Action:</strong>
              <p>
                Remove any mobile phones, secondary notes, headphones, or unpermitted materials from your camera view immediately. The proctoring system continuously scans the camera frame.
              </p>
            </div>
          )}

          {/* Warning Counter Card */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-500 block font-medium">
                Total Warnings Allowed
              </span>
              <span className="text-sm font-semibold text-slate-800">
                Course Setting: {maxWarnings} Warnings Max
              </span>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block font-medium">
                Remaining Chances
              </span>
              <span
                className={`text-sm font-bold ${
                  isLastWarning ? 'text-red-600' : 'text-amber-600'
                }`}
              >
                {remaining} {remaining === 1 ? 'chance' : 'chances'} left
              </span>
            </div>
          </div>

          {isLastWarning && (
            <div className="p-3 rounded-lg bg-red-100 border border-red-300 text-xs text-red-900 font-bold flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-red-600 shrink-0" />
              <span>Critical Notice: Your next violation will result in immediate disqualification and exam lock!</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3">
          <button
            onClick={onResume}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Maximize2 className="w-4 h-4" />
            <span>I Have Cleared the Workspace & Resume Exam</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
