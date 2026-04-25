import time

import numpy as np

from mindbridge_chess.eeg_acquisition import EEGAcquisition


def test_eeg_acquisition_simulation_mode_buffers_samples():
    eeg = EEGAcquisition({"allow_simulation": True, "force_simulation": True})
    eeg.start()
    try:
        eeg.clear()
        time.sleep(0.03)
        data = eeg.read_buffer()
    finally:
        eeg.stop()

    assert eeg.status.mode == "stopped"
    assert eeg.status.simulated is True
    assert isinstance(data, np.ndarray)
    assert data.shape[1] == 8
