"""2 Rooks vs Lone King checkmate exercise — single end-to-end BCI pipeline test."""

import time

import chess

from .board import ChessBoard
from .eeg_acquisition import EEGAcquisition
from .p300_detector import P300Detector
from .stimulus import StimulusPresenter

# Fixed starting position: Ra1, Rb1, Ke4 (white) vs Ke8 (black)
_EXERCISE_FEN = "4k3/8/8/8/4K3/8/8/RR6 w - - 0 1"

# Timing parameters (per spec)
_FLASH_MS = 100
_IFI_MS   = 75
_CYCLES   = 3
_PZ_CH    = 4   # Pz channel index: Fz=0 C3=1 Cz=2 C4=3 Pz=4 PO7=5 Oz=6 PO8=7


class RookCheckmateExercise:
    def __init__(self):
        stim_cfg = {
            'flash_duration_ms':  _FLASH_MS,
            'inter_flash_ms':     _IFI_MS,
            'cycles_per_decision': _CYCLES,
        }
        det_cfg = {
            'pz_channel_index': _PZ_CH,
        }
        self.board     = ChessBoard()
        self.eeg       = EEGAcquisition()
        self.detector  = P300Detector(det_cfg)
        self.presenter = StimulusPresenter(stim_cfg)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.board.load_fen(_EXERCISE_FEN)
        self.eeg.start()
        try:
            self.presenter.draw_board(self.board.board)
            while not self.board.is_game_over():
                if self.board.turn == chess.WHITE:
                    self._white_turn()
                else:
                    self._black_auto_turn()
            if self.board.is_checkmate():
                self.presenter.show_message("CHECKMATE", board=self.board.board)
        finally:
            self.eeg.stop()
            self.presenter.close()

    # ------------------------------------------------------------------
    def _white_turn(self) -> None:
        # Step 1 — player selects which rook to move
        rook_squares = self.board.get_white_rook_squares()
        if not rook_squares:
            return
        selected_sq = self._flash_and_detect(rook_squares)

        # Step 2 — player selects destination square
        legal_moves    = self.board.get_legal_moves_for_square(selected_sq)
        if not legal_moves:
            return
        target_squares = [m.to_square for m in legal_moves]
        chosen_target  = self._flash_and_detect(target_squares)

        move = next(m for m in legal_moves if m.to_square == chosen_target)
        self.board.apply_move(move)
        self.presenter.draw_board(self.board.board)

    def _black_auto_turn(self) -> None:
        move = self.board.get_black_auto_move()
        if move:
            self.board.apply_move(move)
            self.presenter.draw_board(self.board.board)

    # ------------------------------------------------------------------
    def _flash_and_detect(self, squares: list):
        """
        Flash *squares* with the P300 protocol, collect EEG, detect the
        selected square via P300, and return it.
        """
        self.eeg.clear()
        time.sleep(0.2)   # pre-roll: ensures ≥50 samples of baseline before first flash

        flash_log = self.presenter.flash_squares(self.board.board, squares)

        time.sleep(0.6)   # post-stimulus collection window for the last epoch
        eeg_data = self.eeg.read_buffer()

        # Convert wall-clock flash timestamps to sample indices within this trial
        triggers = [
            (stim_i, int((ts - self.eeg.t_start) * self.eeg.sample_rate))
            for stim_i, ts in flash_log
        ]

        winner_idx = self.detector.detect(eeg_data, triggers, n_stimuli=len(squares))
        return squares[winner_idx]


def run_exercise() -> None:
    RookCheckmateExercise().run()
