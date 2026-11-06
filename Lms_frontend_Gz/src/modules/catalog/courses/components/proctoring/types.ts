export interface MalpracticeIncident {
  id: string;
  type:
    | 'fullscreen_exit'
    | 'tab_switch'
    | 'devtools_attempt'
    | 'copy_paste'
    | 'prohibited_object'
    | 'multiple_faces'
    | 'no_face';
  title: string;
  description: string;
  timestamp: string;
  warningNumber: number;
  detectedObject?: string;
  confidence?: number;
}

export interface DetectedItem {
  id: string;
  name: string;
  confidence: number;
  box: { top: number; left: number; width: number; height: number };
  color: string;
}
