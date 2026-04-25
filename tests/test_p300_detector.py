import numpy as np

from mindbridge_chess.p300_detector import P300Detector


def test_p300_detector_selects_strongest_synthetic_response():
    detector = P300Detector({"channels": [4], "smooth_ms": 1})
    sample_rate = 250
    eeg = np.zeros((500, 8), dtype=np.float32)

    triggers = [
        (0, 100),
        (1, 200),
        (2, 300),
    ]
    p300_start = 100 + int((100 + 250) * sample_rate / 1000)
    p300_end = 100 + int((100 + 500) * sample_rate / 1000)
    eeg[p300_start:p300_end, 4] = 8.0

    assert detector.detect(eeg, triggers, n_stimuli=3) == 0
    assert detector.last_scores[0] > detector.last_scores[1]
    assert detector.last_confidence > 0


def test_p300_detector_handles_empty_data():
    detector = P300Detector()

    assert detector.detect(np.zeros((0, 8), dtype=np.float32), [], n_stimuli=3) == 0
    assert detector.last_confidence == 0.0
