"""LSL marker outlet for LabRecorder event logging."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import time


class LSLMarkerOutlet:
    """Publishes experiment events as a single-channel LSL marker stream."""

    def __init__(
        self,
        name: str = "MindBridgeEvents",
        stream_type: str = "Markers",
        source_id: str = "mindbridge_chess_events",
    ) -> None:
        self.enabled = False
        self.last_error: str | None = None
        self._outlet = None
        self.csv_path = self._create_csv_log()

        try:
            from pylsl import StreamInfo, StreamOutlet
        except Exception as exc:
            self.last_error = f"pylsl import failed: {exc}"
            print(f"[LSL] Marker stream disabled ({self.last_error}).")
            return

        try:
            info = StreamInfo(name, stream_type, 1, 0, "string", source_id)
            channels = info.desc().append_child("channels")
            channels.append_child("channel").append_child_value("label", "event")
            self._outlet = StreamOutlet(info)
            self.enabled = True
            print(f"[LSL] Marker stream available: {name} ({stream_type})")
        except Exception as exc:
            self.last_error = str(exc)
            print(f"[LSL] Marker stream disabled ({exc}).")

    def push(self, marker: str) -> None:
        """Send one marker sample to LabRecorder and append it to the CSV log."""
        timestamp = time.time()
        self._write_csv_marker(timestamp, marker)
        if self.enabled and self._outlet is not None:
            self._outlet.push_sample([marker])

    def _create_csv_log(self) -> Path:
        logs_dir = Path(__file__).resolve().parents[2] / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = logs_dir / f"mindbridge_events_{timestamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["timestamp_unix", "timestamp_iso", "marker"])
        print(f"[CSV] Marker log: {path}")
        return path

    def _write_csv_marker(self, timestamp: float, marker: str) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    f"{timestamp:.6f}",
                    datetime.fromtimestamp(timestamp).isoformat(timespec="milliseconds"),
                    marker,
                ]
            )
