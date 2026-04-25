"""EEG acquisition and trigger timestamp handling for Unicorn Hybrid Black."""

from dataclasses import dataclass
import threading
import time

import numpy as np

try:
    import UnicornPy
    _UNICORN_AVAILABLE = True
except ImportError:
    _UNICORN_AVAILABLE = False


@dataclass(frozen=True)
class EEGStatus:
    """Runtime status for the EEG acquisition backend."""

    mode: str
    simulated: bool
    sample_rate: int
    device_name: str | None = None
    last_error: str | None = None


class EEGAcquisition:
    """
    Streams EEG from Unicorn Hybrid Black into a rolling numpy buffer.

    When UnicornPy is not installed or no device is paired, falls back to a
    simulation mode that generates Gaussian noise at 250 Hz so the full visual
    and detection pipeline can be exercised without hardware.
    """

    # Unicorn Hybrid Black: 8 EEG + 3 accel + 3 gyro + battery + counter + validation
    _TOTAL_CH       = 17
    _EEG_CH         = 8
    _SCANS_PER_READ = 1

    def __init__(self, config=None):
        cfg = config or {}
        self.sample_rate = cfg.get("sample_rate", 250)
        self.allow_simulation = cfg.get("allow_simulation", True)
        self.force_simulation = cfg.get("force_simulation", False)
        self.device_index = cfg.get("device_index", 0)
        self.simulated = False
        self.mode = "stopped"
        self.device_name: str | None = None
        self.last_error: str | None = None
        self._device = None
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._chunks: list = []
        self._sample_count = 0
        self.t_start: float = 0.0  # wall-clock time of last clear()

    # ------------------------------------------------------------------
    @staticmethod
    def unicorn_sdk_available() -> bool:
        """Return whether the Unicorn Python SDK can be imported."""
        return _UNICORN_AVAILABLE

    @staticmethod
    def available_devices() -> list:
        """Return paired Unicorn device names, or an empty list if unavailable."""
        if not _UNICORN_AVAILABLE:
            return []
        try:
            return list(UnicornPy.GetAvailableDevices(True))
        except Exception:
            return []

    def start(self) -> None:
        if self.force_simulation:
            self.last_error = "Simulation forced by configuration."
        elif _UNICORN_AVAILABLE:
            try:
                devices = UnicornPy.GetAvailableDevices(True)
                if not devices:
                    raise RuntimeError("No paired Unicorn device found.")
                if self.device_index >= len(devices):
                    raise RuntimeError(
                        f"Device index {self.device_index} is unavailable; found {len(devices)} device(s)."
                    )
                self.device_name = str(devices[self.device_index])
                self._device = UnicornPy.Unicorn(devices[self.device_index])
                self._device.StartAcquisition(False)
                self.simulated = False
                self.mode = "hardware"
                self._running = True
                self._thread  = threading.Thread(target=self._acquire_loop, daemon=True)
                self._thread.start()
                print(f"[EEG] Streaming from Unicorn device: {self.device_name}")
                return
            except Exception as exc:
                self.last_error = str(exc)
                print(f"[EEG] Hardware init failed ({exc}).")
        elif not self.force_simulation:
            self.last_error = "UnicornPy SDK is not installed."

        if not self.allow_simulation:
            raise RuntimeError(self.last_error or "Unicorn hardware is unavailable.")

        # --- simulation fallback ---
        self.simulated = True
        self.mode = "simulation"
        self._running  = True
        self._thread   = threading.Thread(target=self._simulate_loop, daemon=True)
        self._thread.start()
        print("[EEG] Running in simulation mode (no Unicorn device).")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._device:
            try:
                self._device.StopAcquisition()
            except Exception:
                pass
        self.mode = "stopped"

    @property
    def status(self) -> EEGStatus:
        return EEGStatus(
            mode=self.mode,
            simulated=self.simulated,
            sample_rate=self.sample_rate,
            device_name=self.device_name,
            last_error=self.last_error,
        )

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the buffer and record t_start for timestamp alignment."""
        with self._lock:
            self._chunks = []
            self._sample_count = 0
            self.t_start = time.time()

    def read_buffer(self) -> np.ndarray:
        """Return all buffered EEG data as (n_samples, 8) float32."""
        with self._lock:
            if not self._chunks:
                return np.zeros((0, self._EEG_CH), dtype=np.float32)
            return np.concatenate(self._chunks, axis=0)

    # ------------------------------------------------------------------
    def _acquire_loop(self) -> None:
        frame_bytes = self._TOTAL_CH * self._SCANS_PER_READ * 4  # float32
        buf = bytearray(frame_bytes)
        while self._running:
            try:
                self._device.GetData(self._SCANS_PER_READ, buf, frame_bytes)
                frame = np.frombuffer(buf, dtype=np.float32).reshape(
                    self._SCANS_PER_READ, self._TOTAL_CH
                )
                eeg = frame[:, : self._EEG_CH].copy()
                with self._lock:
                    self._chunks.append(eeg)
                    self._sample_count += self._SCANS_PER_READ
            except Exception:
                break

    def _simulate_loop(self) -> None:
        interval = 1.0 / self.sample_rate
        rng = np.random.default_rng()
        while self._running:
            sample = rng.standard_normal((1, self._EEG_CH)).astype(np.float32)
            with self._lock:
                self._chunks.append(sample)
                self._sample_count += 1
            time.sleep(interval)
