"""Nature Documentary client for dispatching motion events to TerrariumPI"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

from src.detection_filter import DetectionFilter

logger = logging.getLogger(__name__)


@dataclass
class PublishedEvent:
    """Tracks when an event was last published for cooldown enforcement."""

    timestamp: datetime
    track_id: Optional[int]


class NatureDocumentaryClient:
    """Publishes rich motion events from Nocturnal Eye to TerrariumPI."""

    def __init__(self, config: dict):
        integration_cfg = config.get("nature_documentary", {})
        self.enabled = integration_cfg.get("enabled", False)
        base_url = integration_cfg.get("terrariumpi_url", "http://localhost:8090").rstrip("/")
        endpoint = integration_cfg.get("event_endpoint", "/api/nature-doc/events") or "/api/nature-doc/events"
        self.event_url = f"{base_url}{endpoint}" if endpoint.startswith("/") else endpoint
        self.api_key = integration_cfg.get("api_key") or None
        self.camera_id = integration_cfg.get("camera_id", "terrarium_cam")
        self.min_confidence = float(integration_cfg.get("min_confidence", 0.35))
        self.cooldown = timedelta(seconds=int(integration_cfg.get("cooldown_seconds", 45)))
        self.track_cooldown = timedelta(seconds=int(integration_cfg.get("track_cooldown_seconds", 25)))
        self.max_batch_size = max(1, int(integration_cfg.get("max_batch_size", 5)))
        self.send_full_frame_events = integration_cfg.get("send_full_frame_events", False)

        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_global_event: Optional[datetime] = None
        self._track_last_event: Dict[int, datetime] = {}

        self._session = requests.Session()
        self._detection_filter = DetectionFilter(config)

    def set_frame_size(self, frame_size: Tuple[int, int]):
        self._frame_size = frame_size

    def publish_events(self, annotated_events: List[Dict], current_time: datetime):
        if not self.enabled:
            return

        if not annotated_events:
            return

        if not self._frame_size:
            logger.debug("Skipping event publish - frame size unknown")
            return

        if not self._detection_filter.should_publish_detection(current_time):
            logger.debug("Skipping event publish - outside publishing window")
            return

        payloads = []
        for item in annotated_events[: self.max_batch_size]:
            event = item["event"]
            zone = item.get("zone")

            if event.confidence < self.min_confidence:
                continue

            if self._is_suppressed(event.timestamp, event.track_id):
                continue

            payload = self._build_payload(event, zone)
            payloads.append(payload)
            self._register_emit(event.timestamp, event.track_id)

        if not payloads:
            return

        body = {"camera_id": self.camera_id, "events": payloads}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Nature-Doc-Key"] = self.api_key

        try:
            response = self._session.post(self.event_url, json=body, headers=headers, timeout=5)
            if response.status_code not in (200, 201, 202):
                logger.warning("NatureDoc POST failed (%s): %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logger.warning("NatureDoc POST error: %s", exc)

    def _is_suppressed(self, timestamp: datetime, track_id: Optional[int]) -> bool:
        # Global cooldown
        if self._last_global_event and (timestamp - self._last_global_event) < self.cooldown:
            if not track_id:
                return True

        if track_id is not None:
            last = self._track_last_event.get(track_id)
            if last and (timestamp - last) < self.track_cooldown:
                return True

        return False

    def _register_emit(self, timestamp: datetime, track_id: Optional[int]):
        self._last_global_event = timestamp
        if track_id is not None:
            self._track_last_event[track_id] = timestamp

    def _build_payload(self, event, zone: Optional[str]) -> Dict:
        width, height = self._frame_size
        bbox_norm = self._normalize_bbox(event.bounding_box, width, height)
        centroid_norm = self._normalize_point(event.centroid, width, height)

        payload = {
            "event_type": "gecko_motion",
            "timestamp": event.timestamp.isoformat(),
            "confidence": round(float(event.confidence), 4),
            "area": int(event.area),
            "camera_id": self.camera_id,
            "track_id": event.track_id,
            "bounding_box": bbox_norm,
            "centroid": centroid_norm,
        }
        if zone:
            payload["zone"] = zone

        if self.send_full_frame_events:
            payload["frame_bbox"] = {
                "x": 0.0,
                "y": 0.0,
                "w": 1.0,
                "h": 1.0,
            }

        return payload

    def _normalize_bbox(self, bbox: Tuple[int, int, int, int], width: int, height: int) -> Dict[str, float]:
        x, y, w, h = bbox
        width = max(1, width)
        height = max(1, height)
        return {
            "x": round(x / width, 6),
            "y": round(y / height, 6),
            "w": round(w / width, 6),
            "h": round(h / height, 6),
        }

    def _normalize_point(self, centroid: Tuple[int, int], width: int, height: int) -> Dict[str, float]:
        cx, cy = centroid
        width = max(1, width)
        height = max(1, height)
        return {
            "x": round(cx / width, 6),
            "y": round(cy / height, 6),
        }
