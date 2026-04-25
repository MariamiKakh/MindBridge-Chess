"""P300 classification logic for universal detection."""


class P300Classifier:
    """Scores epochs and decides whether a P300 response is present."""

    def __init__(self, config=None):
        self.config = config

    def predict(self, features):
        return 0.0
