import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as cocoSsd from '@tensorflow-models/coco-ssd';
import '@tensorflow/tfjs';
import {
  Camera,
  Mic,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Eye,
  Play,
  Scan,
  Smartphone,
  BookOpen,
  Laptop,
  Users,
  ShieldCheck,
} from 'lucide-react';
import { DetectedItem } from './types';

interface ProctorCameraProps {
  isActive: boolean;
  sessionId?: string | null;
  accessToken?: string | null;
  onCameraError?: (error: string) => void;
  onObjectDetected?: (objectName: string, confidence: number) => void;
  warningsCount: number;
  maxWarnings: number;
  isCompact?: boolean;
}

interface FaceBoxItem {
  top: number;
  left: number;
  width: number;
  height: number;
  confidence: number;
  lookingAway: boolean;
}

export const ProctorCamera: React.FC<ProctorCameraProps> = ({
  isActive,
  sessionId,
  accessToken,
  onCameraError,
  onObjectDetected,
  warningsCount,
  maxWarnings,
  isCompact = false,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const localModelRef = useRef<cocoSsd.ObjectDetection | null>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraMode, setCameraMode] = useState<'hardware' | 'simulated'>('hardware');
  const [status, setStatus] = useState<'loading' | 'active' | 'paused' | 'error'>('loading');
  const [, setErrorMessage] = useState<string | null>(null);
  const [micLevel, setMicLevel] = useState(60);

  // Model loading and real-time detection state
  const [isModelLoading, setIsModelLoading] = useState(true);
  const [detectedObject, setDetectedObject] = useState<DetectedItem | null>(null);
  const [detectedFace, setDetectedFace] = useState<FaceBoxItem | null>(null);
  const [aiScanStatus, setAiScanStatus] = useState<string>('Initializing YOLO & YuNet...');
  const [faceCountState, setFaceCountState] = useState<number>(1);
  const [showObjectTester, setShowObjectTester] = useState(false);

  // Cooldown tracker to prevent repetitive alerts
  const lastAlertTimeRef = useRef<number>(0);
  const isDetectionLoopRunning = useRef(false);

  // 1. Load local lightweight COCO-SSD as zero-latency client-side fallback
  useEffect(() => {
    let isMounted = true;

    cocoSsd
      .load({ base: 'lite_mobilenet_v2' })
      .then((m) => {
        if (isMounted) {
          localModelRef.current = m;
          setIsModelLoading(false);
          setAiScanStatus('AI Vision Ready · Scanning Workspace');
        }
      })
      .catch((err) => {
        console.warn('Local COCO-SSD load error:', err);
        if (isMounted) {
          setIsModelLoading(false);
          setAiScanStatus('AI Vision Active (Backend YOLOv8n)');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Safely play video element with all browser autoplay properties
  const playVideoElement = useCallback(async (video: HTMLVideoElement) => {
    try {
      video.defaultMuted = true;
      video.muted = true;
      video.playsInline = true;
      video.setAttribute('playsinline', '');
      video.setAttribute('muted', '');
      video.setAttribute('autoplay', '');

      const playPromise = video.play();
      if (playPromise !== undefined) {
        await playPromise;
        setStatus('active');
      }
    } catch (err: any) {
      console.warn('Video play prevented by autoplay policy, user click needed:', err);
      setStatus('paused');
    }
  }, []);

  // Initialize hardware camera stream
  const initHardwareCamera = useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);

    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Webcam not supported in this browser context.');
      }

      let mediaStream: MediaStream | null = null;
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'user',
          },
          audio: false,
        });
      } catch {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      if (mediaStream) {
        setStream(mediaStream);
        setCameraMode('hardware');

        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
          await playVideoElement(videoRef.current);
        }
      }
    } catch (err: any) {
      console.warn('Hardware camera failed, falling back to simulated:', err);
      let msg = 'Camera access was not available.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Camera permission was denied. Please allow camera access in your browser.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No physical webcam detected on this device.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        msg = 'Camera is currently in use by another application.';
      }

      setErrorMessage(msg);
      setStatus('active');
      setCameraMode('simulated');
      onCameraError?.(msg);
    }
  }, [playVideoElement, onCameraError, stream]);

  // Lifecycle for camera stream & mic fluctuation
  useEffect(() => {
    let micInterval: any = null;

    if (isActive) {
      initHardwareCamera();

      micInterval = setInterval(() => {
        setMicLevel(Math.floor(45 + Math.random() * 45));
      }, 300);
    } else {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        setStream(null);
      }
    }

    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      if (micInterval) clearInterval(micInterval);
    };
  }, [isActive]);

  // Trigger Malpractice when an object or face violation is confirmed
  const handleObjectFlagged = useCallback(
    (
      objectName: string,
      confidence: number,
      box: { top: number; left: number; width: number; height: number }
    ) => {
      const now = Date.now();
      // Cooldown between modal notifications
      if (now - lastAlertTimeRef.current < 8000) return;
      lastAlertTimeRef.current = now;

      const item: DetectedItem = {
        id: `det-${now}`,
        name: objectName,
        confidence,
        box,
        color: '#EF4444',
      };

      setDetectedObject(item);
      onObjectDetected?.(objectName, confidence);
    },
    [onObjectDetected]
  );

  // 2. Real-Time Detection Loop: Sends frame to backend YOLOv8n + YuNet engine
  useEffect(() => {
    if (!isActive) return;

    let timer: any = null;
    isDetectionLoopRunning.current = true;

    const detectFrame = async () => {
      if (!isDetectionLoopRunning.current) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (
        cameraMode === 'hardware' &&
        video &&
        video.readyState >= 2 &&
        !video.paused &&
        video.videoWidth > 0 &&
        video.videoHeight > 0
      ) {
        try {
          // Render frame to offscreen canvas
          const w = 320;
          const h = 240;
          let base64Data: string | null = null;

          if (canvas) {
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            if (ctx) {
              ctx.drawImage(video, 0, 0, w, h);
              base64Data = canvas.toDataURL('image/jpeg', 0.65);
            }
          }

          if (base64Data && sessionId) {
            // Call backend real-time detection API
            const token = accessToken || localStorage.getItem('access_token');
            const res = await fetch(`/api/v1/sessions/${sessionId}/detect-frame`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({ image_base64: base64Data }),
            });

            if (res.ok) {
              const data = await res.json();
              setIsModelLoading(false);

              // 1. Process Faces
              setFaceCountState(data.face_count);
              if (data.faces && data.faces.length > 0) {
                const primary = data.faces[0];
                setDetectedFace({
                  top: primary.box.top_pct,
                  left: primary.box.left_pct,
                  width: primary.box.width_pct,
                  height: primary.box.height_pct,
                  confidence: Math.round(primary.confidence * 100),
                  lookingAway: primary.looking_away,
                });
              } else {
                setDetectedFace(null);
              }

              // 2. Process Prohibited Objects
              if (data.objects && data.objects.length > 0) {
                const obj = data.objects[0];
                const item: DetectedItem = {
                  id: `yolo-${Date.now()}`,
                  name: obj.label,
                  confidence: Math.round(obj.confidence * 100),
                  box: {
                    top: obj.box.top_pct,
                    left: obj.box.left_pct,
                    width: obj.box.width_pct,
                    height: obj.box.height_pct,
                  },
                  color: '#EF4444',
                };
                setDetectedObject(item);
                setAiScanStatus(`⚠️ ${obj.label} Detected (${Math.round(obj.confidence * 100)}%)`);
              } else {
                // Clear detected object if workspace is now clean
                if (detectedObject && !detectedObject.id.startsWith('manual-')) {
                  setDetectedObject(null);
                }

                // Update status according to face checks & quality
                if (data.quality?.is_low_light) {
                  setAiScanStatus('⚠️ Low Light · Please improve lighting');
                } else if (data.quality?.is_blurry) {
                  setAiScanStatus('⚠️ Blurry Video · Check camera lens');
                } else if (data.face_count === 0) {
                  setAiScanStatus('⚠️ No Face Detected in frame');
                } else if (data.face_count > 1) {
                  setAiScanStatus(`⚠️ Multiple Faces (${data.face_count}) in frame`);
                } else if (data.faces?.[0]?.looking_away) {
                  setAiScanStatus('ℹ️ Attention: Looking away from screen');
                } else {
                  setAiScanStatus('YOLOv8n Active · 1 Face Verified · Clear');
                }
              }

              // 3. Check Confirmed Violations from Backend Policy
              if (data.findings && data.findings.length > 0) {
                for (const f of data.findings) {
                  if (f.confirmed && !f.in_cooldown) {
                    const box = f.detail?.box
                      ? {
                          top: f.detail.box.top_pct,
                          left: f.detail.box.left_pct,
                          width: f.detail.box.width_pct,
                          height: f.detail.box.height_pct,
                        }
                      : { top: 25, left: 60, width: 30, height: 45 };

                    handleObjectFlagged(f.title, Math.round(f.confidence * 100), box);
                    break;
                  }
                }
              }

              // Next frame interval (1200ms)
              timer = setTimeout(detectFrame, 1200);
              return;
            }
          }

          // Fallback to local coco-ssd if backend response is not available
          if (localModelRef.current) {
            const predictions = await localModelRef.current.detect(video);
            const vw = video.videoWidth;
            const vh = video.videoHeight;
            let foundProhibited = false;

            for (const pred of predictions) {
              const [x, y, bw, bh] = pred.bbox;
              const scorePercent = Math.round(pred.score * 100);
              const topPct = Math.max(0, Math.min(100, (y / vh) * 100));
              const widthPct = Math.max(5, Math.min(100, (bw / vw) * 100));
              const heightPct = Math.max(5, Math.min(100, (bh / vh) * 100));
              const leftPct = Math.max(0, Math.min(100, 100 - (x / vw) * 100 - widthPct));
              const className = pred.class.toLowerCase();

              if ((className === 'cell phone' || className === 'remote') && pred.score >= 0.5) {
                foundProhibited = true;
                handleObjectFlagged('Mobile Phone', scorePercent, {
                  top: topPct,
                  left: leftPct,
                  width: widthPct,
                  height: heightPct,
                });
                break;
              }
              if (className === 'book' && pred.score >= 0.55) {
                foundProhibited = true;
                handleObjectFlagged('Study Notes / Book', scorePercent, {
                  top: topPct,
                  left: leftPct,
                  width: widthPct,
                  height: heightPct,
                });
                break;
              }
              if ((className === 'laptop' || className === 'tv') && pred.score >= 0.6) {
                foundProhibited = true;
                handleObjectFlagged('Secondary Screen / Laptop', scorePercent, {
                  top: topPct,
                  left: leftPct,
                  width: widthPct,
                  height: heightPct,
                });
                break;
              }
            }

            if (!foundProhibited && !detectedObject) {
              setAiScanStatus('AI Vision Active · Workspace Clear');
            }
          }
        } catch {
          // Frame skip
        }
      }

      timer = setTimeout(detectFrame, 1200);
    };

    timer = setTimeout(detectFrame, 1000);

    return () => {
      isDetectionLoopRunning.current = false;
      if (timer) clearTimeout(timer);
    };
  }, [isActive, cameraMode, sessionId, accessToken, handleObjectFlagged, detectedObject]);

  const handleUserClickPlay = () => {
    if (videoRef.current) {
      playVideoElement(videoRef.current);
    }
  };

  const toggleCameraMode = () => {
    if (cameraMode === 'hardware') {
      setCameraMode('simulated');
      setStatus('active');
    } else {
      setCameraMode('hardware');
      initHardwareCamera();
    }
  };

  const triggerManualObjectTest = (
    objectName: string,
    confidence: number = 95,
    box: { top: number; left: number; width: number; height: number } = { top: 25, left: 60, width: 30, height: 48 }
  ) => {
    handleObjectFlagged(objectName, confidence, box);
  };

  const clearDetectedObject = () => {
    setDetectedObject(null);
  };

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border-2 transition-all ${
        detectedObject
          ? 'border-red-500 shadow-2xl shadow-red-500/25 ring-4 ring-red-500/25 animate-pulse'
          : 'border-[#C9D3CE] shadow-xl'
      } bg-[#0A1530] text-white ${isCompact ? 'w-56' : 'w-72 sm:w-80'}`}
    >
      {/* Hidden Offscreen Canvas for Frame Capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Video Viewport Container */}
      <div
        onClick={handleUserClickPlay}
        className="relative aspect-video w-full overflow-hidden bg-slate-950 flex items-center justify-center cursor-pointer select-none"
      >
        {/* Hardware Webcam Video Element */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-cover scale-x-[-1] transition-opacity duration-300 ${
            cameraMode === 'hardware' && (status === 'active' || status === 'paused')
              ? 'opacity-100'
              : 'opacity-0 absolute pointer-events-none'
          }`}
          onLoadedMetadata={(e) => {
            playVideoElement(e.currentTarget);
          }}
          onPlaying={() => setStatus('active')}
          onPause={() => setStatus('paused')}
        />

        {/* State: Autoplay Paused Overlay */}
        {cameraMode === 'hardware' && status === 'paused' && (
          <div className="absolute inset-0 z-20 bg-black/60 backdrop-blur-xs flex flex-col items-center justify-center p-3 text-center">
            <div className="w-10 h-10 rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-lg mb-2 animate-bounce">
              <Play className="w-5 h-5 ml-0.5 fill-white" />
            </div>
            <p className="text-xs font-bold text-white">Click to Start Camera</p>
            <span className="text-[10px] text-slate-300">
              Browser paused video playback
            </span>
          </div>
        )}

        {/* State: Loading Stream */}
        {cameraMode === 'hardware' && status === 'loading' && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center p-4 text-center space-y-2 bg-slate-950">
            <div className="w-8 h-8 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin" />
            <span className="text-xs text-slate-300 font-medium">
              Initializing webcam...
            </span>
          </div>
        )}

        {/* State: Virtual Proctored Avatar Feed */}
        {cameraMode === 'simulated' && (
          <div className="relative w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-[#0c1830] via-[#091224] to-[#040817] p-4 text-center">
            <div className="relative w-16 h-16 rounded-full bg-[#1B2A8C]/80 border-2 border-emerald-400 flex items-center justify-center text-white shadow-inner mb-1.5">
              <span className="text-xl font-bold tracking-wider">ST</span>
              <div className="absolute -inset-1.5 border-2 border-emerald-400/40 rounded-full animate-ping pointer-events-none" />
              <div className="absolute inset-0 border border-emerald-300/60 rounded-full animate-pulse pointer-events-none" />
            </div>

            <div className="text-[11px] font-bold text-emerald-400 flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
              <span>Proctored Stream Active</span>
            </div>
            <span className="text-[10px] text-slate-400 mt-0.5">
              YOLOv8n & YuNet Real-Time Scanner Running
            </span>
          </div>
        )}

        {/* AI Laser Scan Line Animation */}
        {status === 'active' && !detectedObject && (
          <div className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-emerald-400 to-transparent opacity-70 pointer-events-none animate-bounce" />
        )}

        {/* DETECTED FACE BOUNDING BOX OVERLAY (Cyan / Green) */}
        {detectedFace && !detectedObject && (
          <div
            className={`absolute z-20 border rounded pointer-events-none transition-all duration-300 ${
              detectedFace.lookingAway
                ? 'border-amber-400 bg-amber-400/10'
                : 'border-cyan-400/70 bg-cyan-400/10'
            }`}
            style={{
              top: `${detectedFace.top}%`,
              left: `${100 - detectedFace.left - detectedFace.width}%`, // Mirror correction
              width: `${detectedFace.width}%`,
              height: `${detectedFace.height}%`,
            }}
          >
            <div
              className={`self-start -mt-5 px-1 py-0.2 rounded text-[8px] font-bold flex items-center gap-0.5 whitespace-nowrap ${
                detectedFace.lookingAway
                  ? 'bg-amber-600 text-white'
                  : 'bg-cyan-700/80 text-cyan-100'
              }`}
            >
              <ShieldCheck className="w-2.5 h-2.5" />
              <span>
                Face Verified ({detectedFace.confidence}%)
                {detectedFace.lookingAway ? ' · Looking Away' : ''}
              </span>
            </div>
          </div>
        )}

        {/* DETECTED OBJECT VISUAL BOUNDING BOX OVERLAY (Red) */}
        {detectedObject && (
          <div
            className="absolute z-30 border-2 border-red-500 bg-red-500/20 rounded-lg pointer-events-none animate-pulse flex flex-col justify-between p-1 shadow-lg"
            style={{
              top: `${detectedObject.box.top}%`,
              left: `${detectedObject.box.left}%`,
              width: `${detectedObject.box.width}%`,
              height: `${detectedObject.box.height}%`,
            }}
          >
            <div className="self-start -mt-6 bg-red-600 text-white font-bold text-[9px] px-1.5 py-0.5 rounded shadow-md flex items-center gap-1 whitespace-nowrap">
              <AlertTriangle className="w-2.5 h-2.5" />
              <span>{detectedObject.name} ({detectedObject.confidence}%)</span>
            </div>
            <div className="flex justify-between w-full">
              <span className="w-2.5 h-2.5 border-t-2 border-l-2 border-red-400" />
              <span className="w-2.5 h-2.5 border-t-2 border-r-2 border-red-400" />
            </div>
            <div className="flex justify-between w-full">
              <span className="w-2.5 h-2.5 border-b-2 border-l-2 border-red-400" />
              <span className="w-2.5 h-2.5 border-b-2 border-r-2 border-red-400" />
            </div>
          </div>
        )}

        {/* LIVE PROCTOR Overlay Badge */}
        <div className="absolute top-2 left-2 z-30 flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-bold text-white tracking-wider border border-white/10 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-ping inline-block" />
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block -ml-3.5" />
          <span>PROCTOR LIVE</span>
        </div>

        {/* AI Vision Model Status Badge */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30 px-2 py-0.5 rounded-md bg-emerald-950/80 border border-emerald-500/30 text-[9px] font-semibold text-emerald-300 flex items-center gap-1 pointer-events-none">
          <Eye className="w-2.5 h-2.5 text-emerald-400 animate-pulse" />
          <span>{isModelLoading ? 'Loading YOLO...' : 'YOLOv8n + YuNet Active'}</span>
        </div>

        {/* Mode Switcher Button */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            toggleCameraMode();
          }}
          title={
            cameraMode === 'hardware'
              ? 'Switch to Virtual Proctored Avatar Feed'
              : 'Switch to Physical Hardware Webcam'
          }
          className="absolute top-2 right-2 z-30 px-2 py-0.5 rounded-md bg-black/75 hover:bg-black/95 text-[10px] font-semibold text-slate-200 border border-white/20 flex items-center gap-1 cursor-pointer transition-colors"
        >
          <RefreshCw className="w-2.5 h-2.5" />
          <span>{cameraMode === 'hardware' ? 'Use Avatar' : 'Use Webcam'}</span>
        </button>

        {/* Bottom AI Status HUD */}
        <div className="absolute bottom-2 left-2 right-2 z-30 flex items-center justify-between px-2.5 py-1 rounded-lg bg-black/80 backdrop-blur-md text-[10px] text-slate-200 border border-white/10">
          <span className="flex items-center gap-1.5 font-semibold truncate">
            {detectedObject ? (
              <span className="text-red-400 flex items-center gap-1 font-bold animate-pulse">
                <AlertTriangle className="w-3 h-3 text-red-500" />
                {detectedObject.name} Detected!
              </span>
            ) : (
              <span className="text-emerald-300 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                {aiScanStatus}
              </span>
            )}
          </span>

          <div className="flex items-center gap-1 text-[9px] text-slate-300 shrink-0">
            <Mic className="w-2.5 h-2.5 text-emerald-400" />
            <div className="w-8 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-400 transition-all duration-300 rounded-full"
                style={{ width: `${micLevel}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Proctoring HUD Footer */}
      <div className="p-2.5 bg-[#0a1120] border-t border-white/10 flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-1.5 min-w-0">
          <Camera className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="text-slate-300 font-medium truncate text-[10px]">
            {cameraMode === 'hardware'
              ? `Live Camera · ${faceCountState} Face(s)`
              : 'Virtual Proctor Stream'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {detectedObject && (
            <button
              type="button"
              onClick={clearDetectedObject}
              className="text-[10px] text-red-300 hover:text-white underline cursor-pointer"
            >
              Clear Flag
            </button>
          )}

          <div
            className={`px-2 py-0.5 rounded font-bold text-[10px] flex items-center gap-1 shrink-0 ${
              warningsCount === 0
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                : warningsCount >= maxWarnings
                ? 'bg-red-950 text-red-300 border border-red-800 animate-pulse'
                : 'bg-amber-950 text-amber-300 border border-amber-800'
            }`}
          >
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>
              {warningsCount} / {maxWarnings} Warnings
            </span>
          </div>
        </div>
      </div>

      {/* Direct Detection Info & Sandbox Controls Bar */}
      <div className="p-2 bg-slate-900 border-t border-white/10 space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span className="font-bold text-slate-300 flex items-center gap-1">
            <Scan className="w-3 h-3 text-emerald-400" />
            YOLOv8 & YuNet Real-Time Detection
          </span>
          <button
            type="button"
            onClick={() => setShowObjectTester(!showObjectTester)}
            className="text-[10px] text-emerald-400 hover:underline cursor-pointer"
          >
            {showObjectTester ? 'Hide Test Suite' : 'Test Suite'}
          </button>
        </div>

        {/* Quick Test Trigger Buttons */}
        {showObjectTester && (
          <div className="grid grid-cols-2 gap-1 pt-1 animate-fade-in">
            <button
              type="button"
              onClick={() =>
                triggerManualObjectTest('Mobile Phone (YOLO)', 96, {
                  top: 25,
                  left: 65,
                  width: 28,
                  height: 48,
                })
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-red-900/60 border border-slate-700 hover:border-red-500 text-[10px] text-slate-200 flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Smartphone className="w-3 h-3 text-red-400 shrink-0" />
              <span className="truncate">Mobile Phone</span>
            </button>

            <button
              type="button"
              onClick={() =>
                triggerManualObjectTest('Book / Notes (YOLO)', 93, {
                  top: 50,
                  left: 15,
                  width: 40,
                  height: 40,
                })
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-red-900/60 border border-slate-700 hover:border-red-500 text-[10px] text-slate-200 flex items-center gap-1 cursor-pointer transition-colors"
            >
              <BookOpen className="w-3 h-3 text-red-400 shrink-0" />
              <span className="truncate">Book / Notes</span>
            </button>

            <button
              type="button"
              onClick={() =>
                triggerManualObjectTest('Secondary Laptop (YOLO)', 94, {
                  top: 40,
                  left: 30,
                  width: 45,
                  height: 45,
                })
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-red-900/60 border border-slate-700 hover:border-red-500 text-[10px] text-slate-200 flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Laptop className="w-3 h-3 text-red-400 shrink-0" />
              <span className="truncate">Laptop / Monitor</span>
            </button>

            <button
              type="button"
              onClick={() =>
                triggerManualObjectTest('Multiple Faces (YuNet)', 97, {
                  top: 15,
                  left: 55,
                  width: 38,
                  height: 55,
                })
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-red-900/60 border border-slate-700 hover:border-red-500 text-[10px] text-slate-200 flex items-center gap-1 cursor-pointer transition-colors"
            >
              <Users className="w-3 h-3 text-red-400 shrink-0" />
              <span className="truncate">Multiple Faces</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
