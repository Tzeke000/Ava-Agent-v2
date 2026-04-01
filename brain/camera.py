from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from .camera_live import read_live_frame


@dataclass
class CameraState:
    frame: Any = None
    face_status: str = "No camera image"
    recognized_text: str = "No camera image"
    person_id: str | None = None
    source: str = "ui"
    live_used: bool = False


class CameraManager:
    def __init__(self, device_index: int = 0):
        self.device_index = device_index

    def resolve_frame(self, image=None):
        if image is not None:
            return image, 'ui', False
        frame = read_live_frame()
        if frame is not None:
            return frame, 'live', True
        return None, 'none', False

    def get_face_recognizer(self, g: dict):
        recognizer = g.get('face_recognizer')
        if recognizer is None:
            if hasattr(cv2, 'face') and hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                g['face_recognizer'] = recognizer
            else:
                return None
        return recognizer

    def load_face_labels(self, g: dict):
        path = g.get('FACE_LABELS_PATH')
        if not path:
            return {}
        labels = {}
        try:
            p = Path(path)
            if p.exists():
                import json
                raw = json.loads(p.read_text(encoding='utf-8'))
                labels = {int(k): v for k, v in raw.items()}
        except Exception as e:
            print(f'Face labels load error: {e}')
        g['face_labels'] = labels
        return labels

    def save_face_labels(self, g: dict):
        path = g.get('FACE_LABELS_PATH')
        labels = g.get('face_labels', {})
        if not path:
            return
        try:
            import json
            p = Path(path)
            p.write_text(json.dumps({str(k): v for k, v in labels.items()}, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            print(f'Face labels save error: {e}')

    def detect_face(self, image, g: dict):
        if image is None:
            return 'No camera image'
        try:
            cascade = g.get('face_cascade')
            if cascade is None:
                return 'Face detection unavailable'
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            return 'Face detected' if len(faces) > 0 else 'No face detected'
        except Exception as e:
            return f'Face detection error: {e}'

    def extract_face_crop(self, image, g: dict):
        if image is None:
            return None
        try:
            cascade = g.get('face_cascade')
            if cascade is None:
                return None
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) == 0:
                return None
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            crop = gray[y:y + h, x:x + w]
            return cv2.resize(crop, (200, 200))
        except Exception:
            return None

    def capture_face_sample(self, image, person_id: str, g: dict) -> str:
        crop = self.extract_face_crop(image, g)
        if crop is None:
            return '❌ No face detected in snapshot.'
        faces_dir = Path(g.get('FACES_DIR', 'faces'))
        person_dir = faces_dir / person_id
        person_dir.mkdir(parents=True, exist_ok=True)
        filename = person_dir / f"{int(__import__('time').time() * 1000)}.png"
        try:
            cv2.imwrite(str(filename), crop)
            return f'✅ Saved face sample for {person_id}: {filename.name}'
        except Exception as e:
            return f'❌ Failed to save face sample: {e}'

    def train_face_recognizer(self, g: dict) -> str:
        recognizer = self.get_face_recognizer(g)
        if recognizer is None:
            return '❌ OpenCV face recognizer is unavailable. Install opencv-contrib-python in this venv.'
        faces_dir = Path(g.get('FACES_DIR', 'faces'))
        face_labels = g.get('face_labels', {})
        images, labels, label_map = [], [], {}
        label_counter = 0
        for person_dir in sorted(faces_dir.iterdir()) if faces_dir.exists() else []:
            if not person_dir.is_dir():
                continue
            person_id = person_dir.name
            files = list(person_dir.glob('*.png')) + list(person_dir.glob('*.jpg')) + list(person_dir.glob('*.jpeg'))
            if not files:
                continue
            label_map[label_counter] = person_id
            for file in files:
                try:
                    img = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
                    if img is None:
                        continue
                    img = cv2.resize(img, (200, 200))
                    images.append(img)
                    labels.append(label_counter)
                except Exception:
                    continue
            label_counter += 1
        if not images:
            return '❌ No face samples found to train.'
        try:
            import numpy as np
            recognizer.train(images, np.array(labels))
            model_path = Path(g.get('FACE_MODEL_PATH', 'state/face_model.yml'))
            model_path.parent.mkdir(parents=True, exist_ok=True)
            recognizer.write(str(model_path))
            g['face_labels'] = label_map
            self.save_face_labels(g)
            return f'✅ Trained face recognizer on {len(images)} images across {len(label_map)} people.'
        except Exception as e:
            return f'❌ Face training failed: {e}'

    def recognize_face(self, image, g: dict):
        recognizer = self.get_face_recognizer(g)
        if recognizer is None:
            return 'Facial recognition unavailable in this OpenCV build', None
        model_path = Path(g.get('FACE_MODEL_PATH', 'state/face_model.yml'))
        if not model_path.exists():
            return 'Face model not trained', None
        crop = self.extract_face_crop(image, g)
        if crop is None:
            return 'No face detected', None
        try:
            recognizer.read(str(model_path))
        except Exception:
            pass
        face_labels = g.get('face_labels') or self.load_face_labels(g)
        threshold = float(g.get('FACE_RECOGNITION_THRESHOLD', 80.0))
        try:
            label, confidence = recognizer.predict(crop)
            person_id = face_labels.get(int(label))
            if person_id is None:
                return f'Unknown face ({confidence:.1f})', None
            if confidence <= threshold:
                load_profile_by_id = g.get('load_profile_by_id')
                if callable(load_profile_by_id):
                    try:
                        profile = load_profile_by_id(person_id)
                        return f"Recognized: {profile.get('name', person_id)} ({confidence:.1f})", person_id
                    except Exception:
                        pass
                return f'Recognized: {person_id} ({confidence:.1f})', person_id
            return f'Unknown face ({confidence:.1f})', None
        except Exception as e:
            return f'Recognition error: {e}', None

    def analyze(self, image, g: dict) -> CameraState:
        frame, source, live_used = self.resolve_frame(image)
        state = CameraState(frame=frame, source=source, live_used=live_used)
        if frame is None:
            return state
        state.face_status = self.detect_face(frame, g)
        state.recognized_text, state.person_id = self.recognize_face(frame, g)
        return state
