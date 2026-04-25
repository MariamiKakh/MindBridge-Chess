# Architecture

This project separates EEG acquisition, stimulus presentation, P300 detection, and chess logic into distinct modules.

- `eeg_acquisition.py` captures signals from the Unicorn Hybrid Black headset.
- `stimulus.py` presents timed flashes and sends event markers.
- `p300_detector.py` epochs EEG data and decodes the P300 response.
- `board.py` manages the chess state and legal move execution.
- `app.py` orchestrates the end-to-end BCI chess experience.
