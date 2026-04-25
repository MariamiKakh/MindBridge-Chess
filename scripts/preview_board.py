"""Preview the board rendering without running the full EEG experiment."""

import chess

from mindbridge_chess.stimulus import StimulusPresenter


def main() -> None:
    """Open a short board preview with image-based pieces visible."""
    board = chess.Board("5k2/8/2N5/8/4K3/8/R7/1R6 w - - 0 1")
    presenter = StimulusPresenter()
    try:
        presenter.draw_board(board)
        presenter.show_message("Piece preview", board=board, duration=6.0)
    finally:
        presenter.close()


if __name__ == "__main__":
    main()
