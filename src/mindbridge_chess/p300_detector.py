"""Detect P300 responses in EEG epochs."""

import numpy as np


class P300Detector:
    """
    Epochs EEG data around stimulus flash onsets, baseline-corrects on Pz,
    averages across cycles, and returns the index of the highest P300.
    """

    def __init__(self, config=None):
        cfg = config or {}
        self._sr       = cfg.get('sample_rate', 250)
        pz_ch          = cfg.get('pz_channel_index', 4)
        self._channels = cfg.get('channels', [pz_ch])
        self._smooth_ms = cfg.get('smooth_ms', 40)
        p300_win       = cfg.get('p300_window_ms',   [250, 500])
        baseline_win   = cfg.get('baseline_window_ms', [-100, 0])

        # 100 ms pre-stimulus baseline window
        self._pre   = self._ms(100)
        # 600 ms post-stimulus (epoch end)
        self._post  = self._ms(600)

        # indices within the epoch array (epoch[0] = trigger - 100 ms)
        self._bl_start  = 0
        self._bl_end    = self._ms(abs(baseline_win[0]))          # 0 → 25
        self._p3_start  = self._pre + self._ms(p300_win[0])       # 25 + 62 = 87
        self._p3_end    = self._pre + self._ms(p300_win[1])       # 25 + 125 = 150
        self.last_scores = np.array([], dtype=np.float64)
        self.last_counts = np.array([], dtype=np.int32)
        self.last_confidence = 0.0
        self.calibrated = False
        self.calibration_summary = {}
        self._calibration_weights = None

    # ------------------------------------------------------------------
    def detect(
        self,
        eeg_data:  np.ndarray,   # (n_samples, n_channels)
        triggers:  list,         # [(stim_index, sample_index), ...]
        n_stimuli: int,
    ) -> int:
        """Return 0-based index of the stimulus with the strongest P300."""
        scores = np.zeros(n_stimuli, dtype=np.float64)
        counts = np.zeros(n_stimuli, dtype=np.int32)

        if n_stimuli <= 0 or eeg_data.size == 0:
            self._store_result(scores, counts)
            return 0

        for stim_i, sample_idx in triggers:
            start = sample_idx - self._pre
            end   = sample_idx + self._post
            if stim_i < 0 or stim_i >= n_stimuli or start < 0 or end > len(eeg_data):
                continue

            features = self._extract_features(eeg_data[start:end, :])
            if features is None:
                continue

            scores[stim_i] += self._score_features(features)
            counts[stim_i] += 1

        valid = counts > 0
        if valid.any():
            scores[valid] /= counts[valid]

        self._store_result(scores, counts)
        return int(np.argmax(scores))

    def fit_calibration(self, eeg_data: np.ndarray, triggers: list) -> bool:
        """
        Learn target-vs-non-target channel weights from calibration epochs.

        Triggers are tuples of (stim_index, sample_index, is_target).
        """
        target_features = []
        non_target_features = []

        if eeg_data.size == 0:
            return False

        for _stim_i, sample_idx, is_target in triggers:
            start = sample_idx - self._pre
            end = sample_idx + self._post
            if start < 0 or end > len(eeg_data):
                continue

            features = self._extract_features(eeg_data[start:end, :])
            if features is None:
                continue

            if is_target:
                target_features.append(features)
            else:
                non_target_features.append(features)

        if not target_features or not non_target_features:
            self.calibrated = False
            self.calibration_summary = {
                "target_epochs": len(target_features),
                "non_target_epochs": len(non_target_features),
                "status": "insufficient_epochs",
            }
            return False

        target_mean = np.mean(np.vstack(target_features), axis=0)
        non_target_mean = np.mean(np.vstack(non_target_features), axis=0)
        weights = target_mean - non_target_mean

        if not np.any(weights):
            self.calibrated = False
            self.calibration_summary = {
                "target_epochs": len(target_features),
                "non_target_epochs": len(non_target_features),
                "status": "flat_weights",
            }
            return False

        self._calibration_weights = weights
        self.calibrated = True
        self.calibration_summary = {
            "target_epochs": len(target_features),
            "non_target_epochs": len(non_target_features),
            "status": "ok",
            "weights": weights.tolist(),
        }
        return True

    # ------------------------------------------------------------------
    def _ms(self, ms: float) -> int:
        return int(ms * self._sr / 1000)

    def _smooth(self, signal: np.ndarray) -> np.ndarray:
        window = max(1, self._ms(self._smooth_ms))
        if window <= 1:
            return signal
        kernel = np.ones(window, dtype=np.float64) / window
        return np.convolve(signal, kernel, mode="same")

    def _extract_features(self, epoch: np.ndarray):
        epoch = epoch.astype(np.float64)
        channel_scores = []

        for channel in self._channels:
            if channel < 0 or channel >= epoch.shape[1]:
                continue
            signal = epoch[:, channel]
            baseline = signal[self._bl_start : self._bl_end].mean()
            signal = signal - baseline
            signal = self._smooth(signal)
            channel_scores.append(signal[self._p3_start : self._p3_end].mean())

        if not channel_scores:
            return None
        return np.asarray(channel_scores, dtype=np.float64)

    def _score_features(self, features: np.ndarray) -> float:
        if self.calibrated and self._calibration_weights is not None:
            return float(np.dot(features, self._calibration_weights))
        return float(np.mean(features))

    def _store_result(self, scores: np.ndarray, counts: np.ndarray) -> None:
        self.last_scores = scores.copy()
        self.last_counts = counts.copy()
        if len(scores) < 2:
            self.last_confidence = 0.0
            return
        ordered = np.sort(scores)
        spread = float(np.std(scores))
        if spread == 0.0:
            self.last_confidence = 0.0
            return
        self.last_confidence = float((ordered[-1] - ordered[-2]) / spread)
