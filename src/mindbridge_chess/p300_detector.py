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
        self._pz_ch    = cfg.get('pz_channel_index', 4)
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

        for stim_i, sample_idx in triggers:
            start = sample_idx - self._pre
            end   = sample_idx + self._post
            if start < 0 or end > len(eeg_data):
                continue

            pz = eeg_data[start:end, self._pz_ch].astype(np.float64)

            baseline = pz[self._bl_start : self._bl_end].mean()
            pz -= baseline

            scores[stim_i] += pz[self._p3_start : self._p3_end].mean()
            counts[stim_i] += 1

        valid = counts > 0
        if valid.any():
            scores[valid] /= counts[valid]

        return int(np.argmax(scores))

    # ------------------------------------------------------------------
    def _ms(self, ms: float) -> int:
        return int(ms * self._sr / 1000)
