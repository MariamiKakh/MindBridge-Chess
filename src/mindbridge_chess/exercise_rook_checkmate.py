"""2 Rooks vs Lone King checkmate exercise — single end-to-end BCI pipeline test."""

import chess
import numpy as np

from .board import ChessBoard
from .eeg_acquisition import EEGAcquisition
from .p300_detector import P300Detector
from .stimulus import ExperimentStopped, StimulusPresenter

# Fixed starting position: rooks separated, Ke4 (white) vs Ke8 (black)
_EXERCISE_FEN = "4k3/8/8/8/4K3/R7/8/1R6 w - - 0 1"

# Timing parameters (per spec)
_FLASH_MS = 100
_IFI_MS   = 1000
_CYCLES   = 8
_START_DELAY_SECONDS = 5.0
_POST_PIECE_SELECTION_DELAY_SECONDS = 3.0
_POST_MOVE_DELAY_SECONDS = 3.0
_CALIBRATION_CYCLES = 10
_CALIBRATION_TARGET_BOX = "top_right"
_CALIBRATION_INSTRUCTION_SECONDS = 4.0
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
            'p300_window_ms': [250, 400],
        }
        self.board     = ChessBoard()
        self.eeg       = EEGAcquisition({"allow_simulation": False})
        self.detector  = P300Detector(det_cfg)
        self.presenter = StimulusPresenter(stim_cfg)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.board.load_fen(_EXERCISE_FEN)
        try:
            self.eeg.start()
            status = self.eeg.status
            device = status.device_name or "none"
            self.presenter.send_marker(f"experiment_start;eeg_mode={status.mode};device={device}")
            self._run_calibration()
            self.presenter.send_marker("game_start")
            self.presenter.draw_board(self.board.board)
            self.presenter.wait(_START_DELAY_SECONDS)
            while not self.board.is_game_over():
                if self.board.turn == chess.WHITE:
                    self._white_turn()
                else:
                    self._skip_black_turn()
            if self.board.is_checkmate():
                self.presenter.show_message("CHECKMATE", board=self.board.board)
        except ExperimentStopped:
            self.presenter.send_marker("experiment_stopped")
            pass
        finally:
            self.eeg.stop()
            self.presenter.close()

    # ------------------------------------------------------------------
    def _run_calibration(self) -> None:
        """Run an empty-board P300 marker check before the chess exercise."""
        empty_board = chess.Board(None)
        groups = self._calibration_square_groups()

        self.presenter.send_marker(
            f"calibration_start;cycles={_CALIBRATION_CYCLES};target={_CALIBRATION_TARGET_BOX}"
        )
        self.presenter.draw_board(empty_board)
        self.presenter.show_message(
            "Calibration:\nwatch TOP RIGHT",
            board=empty_board,
            duration=_CALIBRATION_INSTRUCTION_SECONDS,
        )
        self.eeg.clear()
        self.presenter.wait(0.2)
        flash_log = self.presenter.flash_labeled_square_groups(
            empty_board,
            groups,
            cycles=_CALIBRATION_CYCLES,
            target_label=_CALIBRATION_TARGET_BOX,
            marker_prefix="calibration",
        )
        self._fit_calibration(flash_log)
        self.presenter.send_marker(f"calibration_end;target={_CALIBRATION_TARGET_BOX}")

    def _calibration_square_groups(self) -> list:
        """Return four individual board squares for calibration flashing."""
        return [
            ("top_left", [chess.B7]),
            ("top_right", [chess.G7]),
            ("bottom_left", [chess.B2]),
            ("bottom_right", [chess.G2]),
        ]

    def _fit_calibration(self, flash_log: list) -> None:
        """Train the detector from the labeled calibration flashes."""
        self.presenter.wait(0.6)
        eeg_data = self.eeg.read_buffer()
        triggers = [
            (stim_i, int((ts - self.eeg.t_start) * self.eeg.sample_rate), bool(target))
            for stim_i, ts, _label, _cycle, target in flash_log
        ]
        trained = self.detector.fit_calibration(eeg_data, triggers)
        summary = self.detector.calibration_summary
        self.presenter.send_marker(
            "calibration_fit;"
            f"trained={int(trained)};"
            f"target_epochs={summary.get('target_epochs', 0)};"
            f"non_target_epochs={summary.get('non_target_epochs', 0)};"
            f"status={summary.get('status', 'unknown')}"
        )

    # ------------------------------------------------------------------
    def _white_turn(self) -> None:
        # Step 1 — player selects which white piece to move.
        piece_squares = self.board.get_movable_white_piece_squares()
        if not piece_squares:
            return
        selected_sq = self._flash_and_detect(piece_squares)
        self.presenter.send_marker(f"piece_selected;square={chess.square_name(selected_sq)}")
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
        self.presenter.send_marker(f"move_applied;uci={move.uci()}")
        self.board.board.turn = chess.WHITE
        self.presenter.draw_board(self.board.board)
        self.presenter.wait(_POST_MOVE_DELAY_SECONDS)

    def _skip_black_turn(self) -> None:
        """Keep the exercise controlled only by the user's P300 selections."""
        self.presenter.send_marker("black_turn_skipped")
        self.board.board.turn = chess.WHITE
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
        flash_log = self.presenter.flash_square_groups(self.board.board, square_groups)
        return self._detect_index(flash_log, n_stimuli=len(square_groups))

    def _flash_and_detect(self, squares: list):
        """
        Flash *squares* with the P300 protocol, collect EEG, detect the
        selected square via P300, and return it.
        """
        self.eeg.clear()
        self.presenter.wait(0.2)   # pre-roll: ensures >=50 samples of baseline before first flash

        flash_log = self.presenter.flash_squares(self.board.board, squares)
        winner_idx = self._detect_index(flash_log, n_stimuli=len(squares))
        self.presenter.send_marker(f"p300_selection;index={winner_idx}")
        return squares[winner_idx]

    def _detect_index(self, flash_log: list, n_stimuli: int) -> int:
        """Choose the stimulus that wins the most per-cycle P300 predictions."""
        self.presenter.wait(0.6)   # post-stimulus collection window for the last epoch
        eeg_data = self.eeg.read_buffer()

        cycle_triggers: dict = {}
        for entry in flash_log:
            stim_i, ts = entry[0], entry[1]
            cycle = entry[2] if len(entry) > 2 else 1
            sample_idx = int((ts - self.eeg.t_start) * self.eeg.sample_rate)
            cycle_triggers.setdefault(cycle, []).append((stim_i, sample_idx))

        votes = np.zeros(n_stimuli, dtype=np.int32)
        score_sums = np.zeros(n_stimuli, dtype=np.float64)
        for cycle in sorted(cycle_triggers):
            prediction = self.detector.detect(eeg_data, cycle_triggers[cycle], n_stimuli=n_stimuli)
            votes[prediction] += 1
            if len(self.detector.last_scores) == n_stimuli:
                score_sums += self.detector.last_scores
            self.presenter.send_marker(
                f"decision_cycle_prediction;cycle={cycle};index={prediction}"
            )

        best_vote_count = votes.max()
        tied = np.flatnonzero(votes == best_vote_count)
        if len(tied) == 1:
            winner = int(tied[0])
        else:
            winner = int(tied[np.argmax(score_sums[tied])])

        self.detector.last_scores = score_sums
        self.detector.last_counts = votes
        self.presenter.send_marker(
            f"decision_vote_result;index={winner};votes={','.join(str(v) for v in votes)}"
        )
        return winner


def run_exercise() -> None:
    RookCheckmateExercise().run()
