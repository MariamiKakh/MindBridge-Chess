# MindBridge-Chess

A Brain-Computer Interface chess game that uses the Unicorn Hybrid Black EEG headset to control chess moves via P300 responses.

## Overview

The system guides the player through three brain-driven steps:
1. Piece selection
2. Direction selection
3. Square selection

## Project structure

- `src/` — main application and package code
- `configs/` — experiment and stimulus configuration
- `docs/` — architecture, experiment plan, and user flow documentation
- `tests/` — lightweight unit tests for key components
- `notebooks/` — analysis and validation notebooks
- `scripts/` — launch and visualization helpers

## Setup

Use `pyproject.toml` or `requirements.txt` to install dependencies.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
```

## Unicorn Hybrid Black

The Unicorn headset SDK is provided by the vendor and is imported as
`UnicornPy`. It is not installed from normal PyPI, so install the g.tec/Unicorn
SDK separately before hardware testing.

Before running with the headset connected:

```bash
python scripts/check_unicorn.py
```

If the SDK or headset is unavailable, the app runs in simulation mode so the
frontend and P300 flow can still be tested.

## Run

```bash
python scripts/run_experiment.py
```

Controls:

- `Space` manually selects the currently highlighted stimulus for testing.
- `Esc` or `q` closes the experiment window.
