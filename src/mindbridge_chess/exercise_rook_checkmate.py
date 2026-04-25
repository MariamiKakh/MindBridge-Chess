"""2 Rooks vs Lone King checkmate exercise — single end-to-end BCI pipeline test."""

import chess

from .board import ChessBoard
from .eeg_acquisition import EEGAcquisition
from .p300_detector import P300Detector
from .stimulus import ExperimentStopped, ManualSelection, StimulusPresenter

# Fixed starting position: rooks separated, Ke4 (white) vs Ke8 (black)
_EXERCISE_FEN = "4k3/8/8/8/4K3/R7/8/1R6 w - - 0 1"

# Timing parameters (per spec)
_FLASH_MS = 600
_IFI_MS   = 500
_CYCLES   = 5
_START_DELAY_SECONDS = 5.0
_POST_PIECE_SELECTION_DELAY_SECONDS = 3.0
_PZ_CH    = 4   # Pz channel index: Fz=0 C3=1 Cz=2 C4=3 Pz=4 PO7=5 Oz=6 PO8=7
_P300_CHANNELS = [4, 6, 2]  # Pz primary, with Oz/Cz as supporting channels


class RookCheckmateExercise:
    def __init__(self):
        stim_cfg = {
            'flash_duration_ms':  _FLASH_MS,
            'inter_flash_ms':     _IFI_MS,
            'cycles_per_decision': _CYCLES,
        }
        det_cfg = {
            'pz_channel_index': _PZ_CH,
            'channels': _P300_CHANNELS,
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
            self.presenter.wait(_START_DELAY_SECONDS)
            while not self.board.is_game_over():
                if self.board.turn == chess.WHITE:
                    self._white_turn()
                else:
                    self._black_auto_turn()
            if self.board.is_checkmate():
                self.presenter.show_message("CHECKMATE", board=self.board.board)
        except ExperimentStopped:
            pass
        finally:
            self.eeg.stop()
            self.presenter.close()

    # ------------------------------------------------------------------
    def _white_turn(self) -> None:
        # Step 1 — player selects which white piece to move.
        piece_squares = self.board.get_movable_white_piece_squares()
        if not piece_squares:
            return
        selected_sq = self._flash_and_detect(piece_squares)
        self.presenter.wait(_POST_PIECE_SELECTION_DELAY_SECONDS)

        # Step 2 — player selects destination square
        legal_moves    = self.board.get_legal_moves_for_square(selected_sq)
        if not legal_moves:
            return
        selected_piece = self.board.board.piece_at(selected_sq)
        if selected_piece and selected_piece.piece_type == chess.ROOK:
            chosen_target = self._select_rook_target(selected_sq, legal_moves)
        else:
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
    def _select_rook_target(self, selected_sq: int, legal_moves: list) -> int:
        """Choose a rook direction first, then a target square in that direction."""
        direction_groups = self._rook_direction_groups(selected_sq, legal_moves)
        if not direction_groups:
            return legal_moves[0].to_square

        group_index = self._flash_groups_and_detect(direction_groups)
        direction_squares = direction_groups[group_index]
        if len(direction_squares) == 1:
            return direction_squares[0]

        return self._flash_and_detect(direction_squares)

    def _rook_direction_groups(self, selected_sq: int, legal_moves: list) -> list:
        """Group rook legal destinations into up/down/left/right paths."""
        from_file = chess.square_file(selected_sq)
        from_rank = chess.square_rank(selected_sq)
        groups = {
            "up": [],
            "right": [],
            "down": [],
            "left": [],
        }

        for move in legal_moves:
            to_file = chess.square_file(move.to_square)
            to_rank = chess.square_rank(move.to_square)
            if to_file == from_file and to_rank > from_rank:
                groups["up"].append(move.to_square)
            elif to_file > from_file and to_rank == from_rank:
                groups["right"].append(move.to_square)
            elif to_file == from_file and to_rank < from_rank:
                groups["down"].append(move.to_square)
            elif to_file < from_file and to_rank == from_rank:
                groups["left"].append(move.to_square)

        ordered_groups = []
        for direction in ("up", "right", "down", "left"):
            squares = groups[direction]
            squares.sort(key=lambda sq: abs(chess.square_file(sq) - from_file) + abs(chess.square_rank(sq) - from_rank))
            if squares:
                ordered_groups.append(squares)
        return ordered_groups

    def _flash_groups_and_detect(self, square_groups: list) -> int:
        """Flash square groups and return the selected group index."""
        self.eeg.clear()
        self.presenter.wait(0.2)
        try:
            flash_log = self.presenter.flash_square_groups(self.board.board, square_groups)
        except ManualSelection as selection:
            return selection.stimulus_index
        return self._detect_index(flash_log, n_stimuli=len(square_groups))

    def _flash_and_detect(self, squares: list):
        """
        Flash *squares* with the P300 protocol, collect EEG, detect the
        selected square via P300, and return it.
        """
        self.eeg.clear()
        self.presenter.wait(0.2)   # pre-roll: ensures >=50 samples of baseline before first flash

        try:
            flash_log = self.presenter.flash_squares(self.board.board, squares)
        except ManualSelection as selection:
            return squares[selection.stimulus_index]

        winner_idx = self._detect_index(flash_log, n_stimuli=len(squares))
        return squares[winner_idx]

    def _detect_index(self, flash_log: list, n_stimuli: int) -> int:
        """Use EEG data collected during flashing to choose a stimulus index."""
        self.presenter.wait(0.6)   # post-stimulus collection window for the last epoch
        eeg_data = self.eeg.read_buffer()

        # Convert wall-clock flash timestamps to sample indices within this trial
        triggers = [
            (stim_i, int((ts - self.eeg.t_start) * self.eeg.sample_rate))
            for stim_i, ts in flash_log
        ]

        return self.detector.detect(eeg_data, triggers, n_stimuli=n_stimuli)


def run_exercise() -> None:
    RookCheckmateExercise().run()
