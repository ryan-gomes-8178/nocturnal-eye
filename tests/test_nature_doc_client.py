import sys
import types
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

if "requests" not in sys.modules:
    requests_stub = types.SimpleNamespace(Session=lambda: MagicMock(), RequestException=Exception)
    sys.modules["requests"] = requests_stub

from src.nature_doc_client import NatureDocumentaryClient


def _base_config():
    return {
        "nature_documentary": {
            "enabled": True,
            "terrariumpi_url": "http://localhost:8090",
            "event_endpoint": "/api/nature-doc/events",
            "camera_id": "cam_a",
            "min_confidence": 0.25,
            "cooldown_seconds": 60,
            "track_cooldown_seconds": 10,
        },
        "detection_publishing": {"enabled": False},
    }


class NatureDocClientTests(unittest.TestCase):
    def test_client_normalizes_bbox_and_posts(self):
        config = _base_config()
        client = NatureDocumentaryClient(config)
        client.set_frame_size((1920, 1080))

        now = datetime(2026, 2, 9, 12, 0, 0)
        event = SimpleNamespace(
            timestamp=now,
            confidence=0.8,
            area=1500,
            bounding_box=(960, 540, 320, 160),
            centroid=(1120, 640),
            track_id=7,
        )

        mocked = MagicMock()
        mocked.return_value.status_code = 202
        client._session.post = mocked  # type: ignore[attr-defined]

        client.publish_events([{ "event": event, "zone": "Feeding" }], now)

        mocked.assert_called_once()
        body = mocked.call_args.kwargs["json"]
        self.assertEqual(body["camera_id"], "cam_a")
        self.assertEqual(len(body["events"]), 1)
        payload = body["events"][0]
        self.assertEqual(payload["bounding_box"], {"x": 0.5, "y": 0.5, "w": 0.166667, "h": 0.148148})
        self.assertEqual(payload["centroid"], {"x": 0.583333, "y": 0.592593})
        self.assertEqual(payload["zone"], "Feeding")

    def test_client_respects_cooldown(self):
        config = _base_config()
        config["nature_documentary"]["cooldown_seconds"] = 120
        client = NatureDocumentaryClient(config)
        client.set_frame_size((640, 480))

        now = datetime.utcnow()
        event = SimpleNamespace(
            timestamp=now,
            confidence=0.9,
            area=2000,
            bounding_box=(0, 0, 100, 100),
            centroid=(50, 50),
            track_id=1,
        )

        mocked = MagicMock()
        mocked.return_value.status_code = 202
        client._session.post = mocked  # type: ignore[attr-defined]

        client.publish_events([{ "event": event, "zone": None }], now)
        client.publish_events([{ "event": event, "zone": None }], now + timedelta(seconds=30))

        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
