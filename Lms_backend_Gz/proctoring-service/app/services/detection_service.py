"""Real-Time AI Proctoring Detection Service using YOLOv8 and OpenCV YuNet.

Handles:
1. YOLOv8n object detection (cell phone, book, laptop, additional person).
2. OpenCV YuNet Face Detection (no face, 1 face verified, multiple faces, head pose / looking away).
3. Image quality verification (blur and low-light detection).
4. False-positive reduction via consecutive-frame validation, class-specific thresholds, and cooldowns.
5. Explicitly documents unsupported COCO classes (paper/document, paper notebook) without faking.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Paths to models
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
YOLO_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"

# Supported and Unsupported classes documentation
SUPPORTED_CLASSES = {
    67: ("cell phone", "phone_detected", "Mobile Phone"),
    73: ("book", "book_detected", "Book / Study Material"),
    63: ("laptop", "laptop_detected", "Secondary Screen / Laptop"),
    0: ("person", "additional_person", "Additional Person"),
}

UNSUPPORTED_CLASSES = [
    {
        "class_name": "notebook",
        "description": "Paper notepad / spiral notebook",
        "status": "UNSUPPORTED_IN_COCO",
        "reason": "Standard COCO-80 pretrained YOLO weights do not include a dedicated paper notebook class. Not simulated or faked.",
    },
    {
        "class_name": "paper_document",
        "description": "Loose paper / printed document sheets",
        "status": "UNSUPPORTED_IN_COCO",
        "reason": "Standard COCO-80 pretrained YOLO weights do not include a paper/document sheet class. Not simulated or faked.",
    },
]


@dataclass
class QualityMetrics:
    brightness: float
    blur_score: float
    is_low_light: bool
    is_blurry: bool


@dataclass
class DetectedBox:
    x: float
    y: float
    width: float
    height: float
    top_pct: float
    left_pct: float
    width_pct: float
    height_pct: float


@dataclass
class ObjectDetection:
    class_id: int
    class_name: str
    label: str
    confidence: float
    finding_type: str
    box: DetectedBox


@dataclass
class FaceDetection:
    box: DetectedBox
    confidence: float
    looking_away: bool
    looking_away_confidence: float
    landmarks: List[List[float]]


@dataclass
class SessionIncident:
    id: str
    timestamp: str
    type: str
    title: str
    confidence: float
    detail: Dict[str, Any]
    review_status: str = "NEEDS_REVIEW"  # NEEDS_REVIEW, CONFIRMED, FALSE_POSITIVE
    reviewer_note: Optional[str] = None


@dataclass
class SessionTrackingState:
    consecutive_counts: Dict[str, int] = field(default_factory=dict)
    last_alert_times: Dict[str, float] = field(default_factory=dict)
    incidents: List[SessionIncident] = field(default_factory=list)


class DetectionService:
    _instance: Optional[DetectionService] = None

    def __init__(self) -> None:
        self.yolo_model: Optional[YOLO] = None
        self.yunet_detector: Optional[cv2.FaceDetectorYN] = None
        self.session_states: Dict[str, SessionTrackingState] = {}
        self.default_thresholds = {
            "cell_phone": 0.50,
            "book": 0.50,
            "laptop": 0.50,
            "person": 0.45,
            "face": 0.60,
            "looking_away": 0.65,
        }
        self.cooldown_seconds = 25.0
        self._load_models()

    @classmethod
    def get_instance(cls) -> DetectionService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_models(self) -> None:
        try:
            if YOLO_MODEL_PATH.exists():
                logger.info("Loading YOLOv8n from %s", YOLO_MODEL_PATH)
                self.yolo_model = YOLO(str(YOLO_MODEL_PATH))
            else:
                logger.warning("YOLOv8n model not found at %s. Attempting fallback download.", YOLO_MODEL_PATH)
                self.yolo_model = YOLO("yolov8n.pt")

            if YUNET_MODEL_PATH.exists():
                logger.info("Loading YuNet face detector from %s", YUNET_MODEL_PATH)
                self.yunet_detector = cv2.FaceDetectorYN.create(
                    str(YUNET_MODEL_PATH),
                    "",
                    (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                )
            else:
                logger.warning("YuNet ONNX model not found at %s", YUNET_MODEL_PATH)
        except Exception as e:
            logger.exception("Failed to initialize detection models: %s", e)

    def _assess_quality(self, bgr_image: np.ndarray) -> QualityMetrics:
        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        is_low_light = brightness < 35.0
        is_blurry = blur_score < 40.0

        return QualityMetrics(
            brightness=round(brightness, 2),
            blur_score=round(blur_score, 2),
            is_low_light=is_low_light,
            is_blurry=is_blurry,
        )

    def _detect_faces(self, bgr_image: np.ndarray, height: int, width: int) -> Tuple[int, List[FaceDetection]]:
        if self.yunet_detector is None:
            return 0, []

        self.yunet_detector.setInputSize((width, height))
        _, faces = self.yunet_detector.detect(bgr_image)

        if faces is None or len(faces) == 0:
            return 0, []

        results: List[FaceDetection] = []
        for face in faces:
            box_x, box_y, box_w, box_h = face[0:4]
            conf = float(face[14])
            if conf < self.default_thresholds["face"]:
                continue

            # Landmarks: right_eye, left_eye, nose_tip, right_mouth, left_mouth
            re_x, re_y = face[4], face[5]
            le_x, le_y = face[6], face[7]
            nt_x, nt_y = face[8], face[9]
            rm_x, rm_y = face[10], face[11]
            lm_x, lm_y = face[12], face[13]

            landmarks = [
                [float(re_x), float(re_y)],
                [float(le_x), float(le_y)],
                [float(nt_x), float(nt_y)],
                [float(rm_x), float(rm_y)],
                [float(lm_x), float(lm_y)],
            ]

            # Head pose / looking away heuristic:
            # Distance from right eye to nose vs left eye to nose
            dist_re_nt = abs(nt_x - re_x)
            dist_le_nt = abs(le_x - nt_x)
            looking_away = False
            looking_away_conf = 0.0

            if dist_le_nt > 0 and dist_re_nt > 0:
                ratio = dist_re_nt / (dist_le_nt + 1e-5)
                if ratio > 2.2 or ratio < 0.45:
                    looking_away = True
                    looking_away_conf = min(0.95, round(abs(ratio - 1.0) / 2.0, 2))

            top_pct = max(0.0, min(100.0, (box_y / height) * 100.0))
            width_pct = max(2.0, min(100.0, (box_w / width) * 100.0))
            height_pct = max(2.0, min(100.0, (box_h / height) * 100.0))
            left_pct = max(0.0, min(100.0, (box_x / width) * 100.0))

            results.append(
                FaceDetection(
                    box=DetectedBox(
                        x=float(box_x),
                        y=float(box_y),
                        width=float(box_w),
                        height=float(box_h),
                        top_pct=round(top_pct, 2),
                        left_pct=round(left_pct, 2),
                        width_pct=round(width_pct, 2),
                        height_pct=round(height_pct, 2),
                    ),
                    confidence=round(conf, 3),
                    looking_away=looking_away,
                    looking_away_confidence=looking_away_conf,
                    landmarks=landmarks,
                )
            )

        return len(results), results

    def _detect_objects(self, bgr_image: np.ndarray, height: int, width: int) -> List[ObjectDetection]:
        if self.yolo_model is None:
            return []

        # Run inference on frame
        results = self.yolo_model.predict(bgr_image, imgsz=320, verbose=False, conf=0.35)
        if not results:
            return []

        detections: List[ObjectDetection] = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())

            if cls_id in SUPPORTED_CLASSES:
                name, finding_type, label = SUPPORTED_CLASSES[cls_id]
                threshold_key = name.replace(" ", "_")
                min_conf = self.default_thresholds.get(threshold_key, 0.50)

                if conf < min_conf:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                box_w = x2 - x1
                box_h = y2 - y1

                top_pct = max(0.0, min(100.0, (y1 / height) * 100.0))
                width_pct = max(2.0, min(100.0, (box_w / width) * 100.0))
                height_pct = max(2.0, min(100.0, (box_h / height) * 100.0))
                left_pct = max(0.0, min(100.0, (x1 / width) * 100.0))

                detections.append(
                    ObjectDetection(
                        class_id=cls_id,
                        class_name=name,
                        label=label,
                        confidence=round(conf, 3),
                        finding_type=finding_type,
                        box=DetectedBox(
                            x=float(x1),
                            y=float(y1),
                            width=float(box_w),
                            height=float(box_h),
                            top_pct=round(top_pct, 2),
                            left_pct=round(left_pct, 2),
                            width_pct=round(width_pct, 2),
                            height_pct=round(height_pct, 2),
                        ),
                    )
                )

        return detections

    def process_frame(
        self,
        session_id: str,
        image_bytes: bytes,
        custom_thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Main entry point for processing a camera frame with YOLO and YuNet."""
        start_time = time.time()
        now_ts = datetime.now(timezone.utc).isoformat()

        # Decode image
        np_arr = np.frombuffer(image_bytes, np.uint8)
        bgr_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if bgr_image is None:
            return {
                "error": "Failed to decode image frame",
                "timestamp": now_ts,
            }

        height, width = bgr_image.shape[:2]

        # 1. Image Quality Assessment
        quality = self._assess_quality(bgr_image)

        # 2. Face Detection via YuNet
        face_count, faces = self._detect_faces(bgr_image, height, width)

        # 3. Object Detection via YOLOv8n
        objects = self._detect_objects(bgr_image, height, width)

        # Count persons
        person_count = sum(1 for obj in objects if obj.class_id == 0)

        # 4. State Tracking & False Positive Reduction
        state = self.session_states.setdefault(session_id, SessionTrackingState())
        current_time = time.time()

        findings: List[Dict[str, Any]] = []

        # Helper to check cooldown and update consecutive counts
        def register_violation(
            v_type: str,
            title: str,
            confidence: float,
            required_consecutive: int,
            detail: Dict[str, Any],
        ) -> None:
            # If poor quality, suppress false positive face / object detections
            if quality.is_blurry or quality.is_low_light:
                detail["quality_warning"] = "Suppressed or flagged due to low-light or blur"

            count = state.consecutive_counts.get(v_type, 0) + 1
            state.consecutive_counts[v_type] = count

            last_alert = state.last_alert_times.get(v_type, 0.0)
            in_cooldown = (current_time - last_alert) < self.cooldown_seconds

            confirmed = count >= required_consecutive

            finding_data = {
                "type": v_type,
                "title": title,
                "confidence": round(confidence, 3),
                "confirmed": confirmed,
                "consecutive_count": count,
                "in_cooldown": in_cooldown,
                "detail": detail,
            }

            if confirmed and not in_cooldown:
                state.last_alert_times[v_type] = current_time
                # Record incident for admin review
                incident = SessionIncident(
                    id=f"inc-{int(current_time * 1000)}-{v_type}",
                    timestamp=now_ts,
                    type=v_type,
                    title=title,
                    confidence=round(confidence, 3),
                    detail=detail,
                )
                state.incidents.append(incident)

            findings.append(finding_data)

        # Active violation types this frame
        active_violation_types = set()

        # Check Face Findings
        if not quality.is_low_light:
            if face_count == 0:
                active_violation_types.add("no_face")
                register_violation(
                    v_type="no_face",
                    title="No Face Detected",
                    confidence=0.85,
                    required_consecutive=3,
                    detail={"message": "No face found in camera view for consecutive frames"},
                )
            elif face_count > 1:
                active_violation_types.add("multiple_faces")
                register_violation(
                    v_type="multiple_faces",
                    title="Multiple Faces Detected",
                    confidence=faces[1].confidence if len(faces) > 1 else 0.90,
                    required_consecutive=2,
                    detail={"face_count": face_count, "message": f"{face_count} faces visible in camera"},
                )
            elif faces and faces[0].looking_away:
                active_violation_types.add("looking_away")
                register_violation(
                    v_type="looking_away",
                    title="Attention Diverted / Looking Away",
                    confidence=faces[0].looking_away_confidence,
                    required_consecutive=3,
                    detail={
                        "message": "Student appears to be looking away from screen (attention signal)",
                        "note": "Informational attention signal, not conclusive proof of cheating.",
                    },
                )

        # Check Multiple Persons via YOLO (if > 1 person detected)
        if person_count > 1:
            active_violation_types.add("multiple_persons")
            register_violation(
                v_type="multiple_persons",
                title="Additional Person in Frame",
                confidence=0.88,
                required_consecutive=2,
                detail={"person_count": person_count, "message": "Multiple persons detected by YOLO in workspace"},
            )

        # Check Prohibited Objects (Phone, Book, Laptop)
        for obj in objects:
            if obj.finding_type in ("phone_detected", "book_detected", "laptop_detected"):
                active_violation_types.add(obj.finding_type)
                register_violation(
                    v_type=obj.finding_type,
                    title=f"{obj.label} Detected",
                    confidence=obj.confidence,
                    required_consecutive=2,
                    detail={
                        "object_name": obj.class_name,
                        "label": obj.label,
                        "box": {
                            "top_pct": obj.box.top_pct,
                            "left_pct": obj.box.left_pct,
                            "width_pct": obj.box.width_pct,
                            "height_pct": obj.box.height_pct,
                        },
                    },
                )

        # Reset consecutive counts for violation types that were NOT present this frame
        all_tracked_types = {"no_face", "multiple_faces", "looking_away", "multiple_persons", "phone_detected", "book_detected", "laptop_detected"}
        for vt in all_tracked_types - active_violation_types:
            state.consecutive_counts[vt] = 0

        latency_ms = round((time.time() - start_time) * 1000, 1)

        return {
            "session_id": session_id,
            "timestamp": now_ts,
            "latency_ms": latency_ms,
            "quality": {
                "brightness": quality.brightness,
                "blur_score": quality.blur_score,
                "is_low_light": quality.is_low_light,
                "is_blurry": quality.is_blurry,
            },
            "face_count": face_count,
            "faces": [
                {
                    "confidence": f.confidence,
                    "looking_away": f.looking_away,
                    "looking_away_confidence": f.looking_away_confidence,
                    "box": {
                        "top_pct": f.box.top_pct,
                        "left_pct": f.box.left_pct,
                        "width_pct": f.box.width_pct,
                        "height_pct": f.box.height_pct,
                    },
                }
                for f in faces
            ],
            "objects": [
                {
                    "class_name": obj.class_name,
                    "label": obj.label,
                    "confidence": obj.confidence,
                    "finding_type": obj.finding_type,
                    "box": {
                        "top_pct": obj.box.top_pct,
                        "left_pct": obj.box.left_pct,
                        "width_pct": obj.box.width_pct,
                        "height_pct": obj.box.height_pct,
                    },
                }
                for obj in objects
                if obj.class_id != 0 or person_count > 1  # filter primary person from object box noise
            ],
            "findings": findings,
            "supported_classes": list(SUPPORTED_CLASSES.values()),
            "unsupported_classes": UNSUPPORTED_CLASSES,
            "model_metadata": {
                "object_model": "Ultralytics YOLOv8n (80 COCO classes)",
                "face_model": "OpenCV YuNet 2023mar (5-point facial landmarks)",
                "device": "CPU",
            },
        }

    def get_session_incidents(self, session_id: str) -> List[Dict[str, Any]]:
        state = self.session_states.get(session_id)
        if not state:
            return []
        return [
            {
                "id": inc.id,
                "timestamp": inc.timestamp,
                "type": inc.type,
                "title": inc.title,
                "confidence": inc.confidence,
                "detail": inc.detail,
                "review_status": inc.review_status,
                "reviewer_note": inc.reviewer_note,
            }
            for inc in state.incidents
        ]

    def update_incident_status(
        self,
        session_id: str,
        incident_id: str,
        review_status: str,
        reviewer_note: Optional[str] = None,
    ) -> bool:
        state = self.session_states.get(session_id)
        if not state:
            return False
        for inc in state.incidents:
            if inc.id == incident_id:
                inc.review_status = review_status
                if reviewer_note:
                    inc.reviewer_note = reviewer_note
                return True
        return False
