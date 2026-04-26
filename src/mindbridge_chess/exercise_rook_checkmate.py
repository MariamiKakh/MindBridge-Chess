"""2 Rooks vs Lone King checkmate exercise — single end-to-end BCI pipeline test."""

import chess
import numpy as np

from .board import ChessBoard
from .eeg_acquisition import EEGAcquisition
from .p300_detector import P300Detector
from .stimulus import ExperimentStopped, StimulusPresenter

_LEVELS = [
    {
        "id": "two-rooks-mate",
        "title": "Level 1: Two Rooks Mate",
        "tag": "Beginner endgame",
        "description": "Use two separated rooks to restrict the lone black king.",
        "goal": "Practice selecting a rook, choosing a row or column direction, then choosing the final square.",
        "fen": "4k3/8/8/8/4K3/R7/8/1R6 w - - 0 1",
    },
    {
        "id": "rook-box",
        "title": "Level 2: Rook Box",
        "tag": "Rook control",
        "description": "One rook and king coordinate to reduce the black king's space.",
        "goal": "Focus on rook movement and direction selection before exact-square selection.",
        "fen": "6k1/8/8/8/4K3/8/8/5R2 w - - 0 1",
    },
    {
        "id": "minor-piece-net",
        "title": "Level 3: Minor Piece Net",
        "tag": "Piece coordination",
        "description": "White king, bishop, and knight coordinate against a lone king.",
        "goal": "Preview future levels where bishops and knights are also selectable pieces.",
        "fen": "7k/8/8/8/4K3/8/3B4/6N1 w - - 0 1",
    },
    {
        "id": "mixed-endgame",
        "title": "Level 4: Mixed Endgame",
        "tag": "Full visual test",
        "description": "A richer board case for checking piece images and layout.",
        "goal": "Use this level to visually verify kings, rooks, bishops, knights, and pawns.",
        "fen": "4k3/2n5/8/8/4K3/2B5/R6P/1R6 w - - 0 1",
    },
]

# Timing parameters (per spec)
_FLASH_MS = 100
_IFI_MS   = 1000
_CYCLES   = 8
_START_DELAY_SECONDS = 5.0
_POST_PIECE_SELECTION_DELAY_SECONDS = 3.0
_POST_MOVE_DELAY_SECONDS = 3.0
_OPPONENT_MOVE_DELAY_SECONDS = 1.2
_OPPONENT_HIGHLIGHT_SECONDS = 0.9
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
        try:
            self.eeg.start()
            status = self.eeg.status
            device = status.device_name or "none"
            self.presenter.send_marker(f"experiment_start;eeg_mode={status.mode};device={device}")
            self._run_calibration()
            selected_level = self._select_level()
            self.board.load_fen(selected_level["fen"])
            self.presenter.set_current_level(selected_level)
            self.presenter.send_marker(f"level_selected;id={selected_level['id']};fen={selected_level['fen']}")
            self.presenter.show_message(
                f"{selected_level['title']}\n{selected_level['tag']}",
                board=self.board.board,
                duration=3.0,
            )
            self.presenter.send_marker("game_start")
            self.presenter.set_status("Board opened. Flashing starts in 5 seconds.")
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
    def _select_level(self) -> dict:
        """Select one level using the calibrated P300 detector."""
        self.presenter.send_marker(f"level_selection_start;count={len(_LEVELS)}")
        self.presenter.draw_level_selector(_LEVELS)
        self.presenter.wait(2.0)
        self.eeg.clear()
        self.presenter.wait(0.2)
        flash_log = self.presenter.flash_level_options(_LEVELS, cycles=_CYCLES)
        winner_idx = self._detect_index(flash_log, n_stimuli=len(_LEVELS))
        level = _LEVELS[winner_idx]
        self.presenter.send_marker(f"level_selection_end;index={winner_idx};id={level['id']}")
        return level

    # ------------------------------------------------------------------
    def _white_turn(self) -> None:
        # Step 1 — player selects which white piece to move.
        self.presenter.set_status("Focus on a white piece. Press Space when it flashes.")
        piece_squares = self.board.get_movable_white_piece_squares()
        if not piece_squares:
            return
        selected_sq = self._flash_and_detect(piece_squares)
        self.presenter.send_marker(f"piece_selected;square={chess.square_name(selected_sq)}")
        self.presenter.set_status("Piece selected. Direction or square choices start in 3 seconds.")
        self.presenter.wait(_POST_PIECE_SELECTION_DELAY_SECONDS)

        # Step 2 — player selects destination square
        legal_moves    = self.board.get_legal_moves_for_square(selected_sq)
        if not legal_moves:
            return
        selected_piece = self.board.board.piece_at(selected_sq)
        if selected_piece and selected_piece.piece_type == chess.ROOK:
            chosen_target = self._select_rook_target(selected_sq, legal_moves)
        else:
            self.presenter.set_status("Focus on a destination box. Press Space when it flashes.")
            target_squares = [m.to_square for m in legal_moves]
            chosen_target  = self._flash_and_detect(target_squares)

        move = next(m for m in legal_moves if m.to_square == chosen_target)
        self.board.apply_move(move)
        self.presenter.send_marker(f"move_applied;uci={move.uci()}")
        self.presenter.set_status("White move applied. Opponent is thinking...")
        self.presenter.draw_board(self.board.board)
        self.presenter.wait(_POST_MOVE_DELAY_SECONDS)

    def _black_auto_turn(self) -> None:
        """Let the opponent make one automatic black move."""
        self.presenter.set_status("Opponent is thinking...")
        self.presenter.wait(_OPPONENT_MOVE_DELAY_SECONDS)
        move = self.board.get_black_auto_move()
        if move is None:
            self.presenter.send_marker("black_auto_no_move")
            return
        self.board.apply_move(move)
        self.presenter.send_marker(f"black_auto_move;uci={move.uci()}")
        self.presenter.set_status("Opponent moved. Focus on a white piece.")
        self.presenter.draw_board(self.board.board, highlight_squares=[move.from_square, move.to_square])
        self.presenter.wait(_OPPONENT_HIGHLIGHT_SECONDS)
        self.presenter.draw_board(self.board.board)
        self.presenter.wait(_POST_MOVE_DELAY_SECONDS)

    # ------------------------------------------------------------------
    def _select_rook_target(self, selected_sq: int, legal_moves: list) -> int:
        """Choose a rook direction first, then a target square in that direction."""
        direction_groups = self._rook_direction_groups(selected_sq, legal_moves)
        if not direction_groups:
            return legal_moves[0].to_square

        self.presenter.set_status("Focus on a rook direction. Press Space when that path flashes.")
        group_index = self._flash_groups_and_detect(direction_groups)
        direction_squares = direction_groups[group_index]
        if len(direction_squares) == 1:
            return direction_squares[0]

        self.presenter.set_status("Focus on the exact box inside that direction. Press Space when it flashes.")
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
        manual_index = self.presenter.consume_manual_selection()
        if manual_index is not None:
            winner = max(0, min(int(manual_index), n_stimuli - 1))
            self.presenter.send_marker(f"decision_manual_result;index={winner}")
            return winner

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
