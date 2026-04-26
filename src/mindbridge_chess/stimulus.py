"""Stimulus presentation logic using PsychoPy."""

from pathlib import Path
import random
import time

import chess
from psychopy import core, event, visual

from .lsl_markers import LSLMarkerOutlet

# Board geometry (pixels, PsychoPy units='pix', origin at screen centre)
_SQ = 78
_LEFT = -_SQ * 4
_BOT = -_SQ * 4

# Colours ported from the VisualAdditions CSS palette into PsychoPy rgb space.
_BG = (-0.82, -0.82, -0.82)          # #171717
_PANEL = (-0.72, -0.72, -0.72)       # #242424
_PANEL_SOFT = (-0.65, -0.65, -0.65)  # #2d2d2d
_TEXT = (0.94, 0.91, 0.84)           # #f7f3ea
_MUTED = (0.45, 0.36, 0.25)          # #b9ad9f
_ACCENT = (1.00, 0.75, -0.52)        # #ffdf3d
_LIGHT = (0.75, 0.06, -0.59)         # #df8734
_DARK = (-0.29, -0.63, -0.80)        # #5a2f19
_FLASH = _ACCENT
_WIN_BG = _BG
_LEVEL_BOXES = [
    (-435, -95),
    (-145, -95),
    ( 145, -95),
    ( 435, -95),
]
_LEVEL_CARD_W = 270
_LEVEL_CARD_H = 390
_LEVEL_PREVIEW_SQ = 25
_BOARD_FRAME_PAD = 10
_FILES = "abcdefgh"
_KING_BLACK_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "KingBlack.png"
_KING_WHITE_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "KingWhite.png"
_ROOK_WHITE_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "RookWhite.png"
_ROOK_BLACK_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "RookBlack.png"
_KNIGHT_WHITE_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "KnightWhite.png"
_KNIGHT_BLACK_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "KnightBlack.png"
_BISHOP_WHITE_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "BishopWhite.png"
_BISHOP_BLACK_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "BishopBlack.png"
_PAWN_WHITE_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "Figures" / "PawnWhite.png"


class ExperimentStopped(Exception):
    """Raised when the user asks to stop the experiment window."""


class StimulusPresenter:
    """Renders the chess board and drives the P300 flashing protocol."""

    def __init__(self, config=None):
        cfg = config or {}
        self._flash_dur = cfg.get('flash_duration_ms', 100) / 1000.0
        self._ifi       = cfg.get('inter_flash_ms',    75)  / 1000.0
        self._cycles    = cfg.get('cycles_per_decision', 3)
        self._markers = LSLMarkerOutlet(
            name=cfg.get("lsl_marker_stream_name", "MindBridgeEvents"),
            stream_type=cfg.get("lsl_marker_stream_type", "Markers"),
            source_id=cfg.get("lsl_marker_source_id", "mindbridge_chess_events"),
        )

        self.win = visual.Window(
            size=(1280, 720),
            fullscr=False,
            color=_WIN_BG,
            colorSpace='rgb',
            units='pix',
            allowGUI=True,
        )
        self._current_level = None
        self._status_text = "Focus on the flashing option."
        self._manual_selection_index = None
        self._rects: dict = {}   # chess.Square -> (Rect, base_color_tuple)
        self._black_king = self._init_image(_KING_BLACK_IMAGE, (_SQ * 0.72, _SQ * 0.72))
        self._white_king = self._init_image(_KING_WHITE_IMAGE, (_SQ * 0.72, _SQ * 0.72))
        self._white_rook = self._init_white_rook_image()
        self._black_rook = self._init_black_rook_image()
        self._white_knight = self._init_white_knight_image()
        self._black_knight = self._init_black_knight_image()
        self._white_bishop = self._init_white_bishop_image()
        self._black_bishop = self._init_black_bishop_image()
        self._white_pawn = self._init_white_pawn_image()
        self._init_rects()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw_board(self, board: chess.Board, highlight_squares: list = None) -> None:
        """Render the current board position and flip."""
        self._check_for_exit()
        self._draw_base(board, highlight_squares=highlight_squares)
        self.win.flip()
        self._push_marker("board_draw")

    def draw_calibration_board(self, board: chess.Board) -> None:
        """Render only the board for calibration, without game UI panels."""
        self._check_for_exit()
        self._draw_calibration_base(board)
        self.win.flip()
        self._push_marker("calibration_board_draw")

    def set_current_level(self, level: dict) -> None:
        """Store level metadata for the board-side information panel."""
        self._current_level = level

    def set_status(self, text: str) -> None:
        """Update the visible board status without changing experiment timing."""
        self._status_text = text

    def consume_manual_selection(self):
        """Return and clear the latest spacebar selection, if one was made."""
        index = self._manual_selection_index
        self._manual_selection_index = None
        return index

    def wait(self, duration: float) -> None:
        """Wait while still responding to exit keys."""
        end_time = time.time() + duration
        while time.time() < end_time:
            self._check_for_keys()
            core.wait(min(0.02, end_time - time.time()))

    def flash_squares(self, board: chess.Board, squares: list) -> list:
        """
        Flash each square in *squares* one at a time for *_cycles* full passes.

        Returns a list of (stim_index, wall_timestamp_at_onset) — one entry per
        flash, ordered by (cycle, square).  stim_index is the 0-based position of
        the flashed square within *squares*.
        """
        log: list = []
        for cycle in range(self._cycles):
            for i, sq in enumerate(squares):
                self._check_for_exit()

                # --- flash ON ---
                self._draw_base(board, highlight_sq=sq)
                self.win.callOnFlip(
                    self._push_marker,
                    f"flash_on;square={chess.square_name(sq)};index={i};cycle={cycle + 1}",
                )
                ts = time.time()
                self.win.flip()
                log.append((i, ts, cycle + 1))
                if self._wait_for_manual_selection(self._flash_dur, i, "square"):
                    self._draw_base(board)
                    self.win.callOnFlip(
                        self._push_marker,
                        f"flash_off;square={chess.square_name(sq)};index={i};cycle={cycle + 1}",
                    )
                    self.win.flip()
                    return log

                # --- flash OFF ---
                self._draw_base(board)
                self.win.callOnFlip(
                    self._push_marker,
                    f"flash_off;square={chess.square_name(sq)};index={i};cycle={cycle + 1}",
                )
                self.win.flip()
                self.wait(self._ifi)
        return log

    def flash_square_groups(self, board: chess.Board, square_groups: list) -> list:
        """
        Flash groups of squares one at a time.

        Used for rook direction selection, where each stimulus is a whole row or
        column path instead of a single destination square.
        """
        log: list = []
        for cycle in range(self._cycles):
            for i, squares in enumerate(square_groups):
                self._check_for_exit()

                self._draw_base(board, highlight_squares=squares)
                square_names = ",".join(chess.square_name(sq) for sq in squares)
                self.win.callOnFlip(
                    self._push_marker,
                    f"group_flash_on;squares={square_names};index={i};cycle={cycle + 1}",
                )
                ts = time.time()
                self.win.flip()
                log.append((i, ts, cycle + 1))
                if self._wait_for_manual_selection(self._flash_dur, i, "group"):
                    self._draw_base(board)
                    self.win.callOnFlip(
                        self._push_marker,
                        f"group_flash_off;squares={square_names};index={i};cycle={cycle + 1}",
                    )
                    self.win.flip()
                    return log

                self._draw_base(board)
                self.win.callOnFlip(
                    self._push_marker,
                    f"group_flash_off;squares={square_names};index={i};cycle={cycle + 1}",
                )
                self.win.flip()
                self.wait(self._ifi)
        return log

    def flash_labeled_square_groups(
        self,
        board: chess.Board,
        labeled_square_groups: list,
        cycles: int,
        target_label: str,
        marker_prefix: str,
        start_cycle: int = 0,
    ) -> list:
        """Flash labeled square groups and mark target/non-target events for calibration."""
        log: list = []
        for cycle in range(cycles):
            display_cycle = start_cycle + cycle + 1
            self._push_marker(f"{marker_prefix}_cycle_start;cycle={display_cycle};target={target_label}")
            cycle_groups = list(labeled_square_groups)
            random.shuffle(cycle_groups)
            for i, (label, squares) in enumerate(cycle_groups):
                self._check_for_exit()
                square_names = ",".join(chess.square_name(sq) for sq in squares)
                target = int(label == target_label)

                self._draw_calibration_base(board, highlight_squares=squares)
                self.win.callOnFlip(
                    self._push_marker,
                    f"{marker_prefix}_flash_on;box={label};index={i};cycle={display_cycle};"
                    f"target={target};squares={square_names}",
                )
                ts = time.time()
                self.win.flip()
                log.append((i, ts, label, display_cycle, target))
                self.wait(self._flash_dur)

                self._draw_calibration_base(board)
                self.win.callOnFlip(
                    self._push_marker,
                    f"{marker_prefix}_flash_off;box={label};index={i};cycle={display_cycle};"
                    f"target={target};squares={square_names}",
                )
                self.win.flip()
                self.wait(self._ifi)
        return log

    def show_calibration_message(self, text: str, board: chess.Board, duration: float = 4.0) -> None:
        """Show a calibration instruction over the clean board only."""
        self._check_for_exit()
        self._draw_calibration_base(board)
        visual.Rect(
            self.win,
            width=560,
            height=160,
            pos=(0, 0),
            fillColor=_PANEL,
            lineColor=_ACCENT,
            lineWidth=2,
            opacity=0.94,
            colorSpace='rgb',
        ).draw()
        visual.TextStim(
            self.win,
            text=text,
            pos=(0, 0),
            color=_ACCENT,
            colorSpace='rgb',
            height=52,
            bold=True,
            wrapWidth=500,
        ).draw()
        self.win.callOnFlip(self._push_marker, f"message;value={text}")
        self.win.flip()
        self.wait(duration)

    def draw_level_selector(self, levels: list) -> None:
        """Show available levels before P300 level selection starts."""
        self._check_for_exit()
        self._draw_level_options(levels)
        self.win.flip()
        self._push_marker("level_selector_draw")

    def flash_level_options(self, levels: list, cycles: int) -> list:
        """Flash level cards and return logs for P300-based level selection."""
        log: list = []
        for cycle in range(cycles):
            self._push_marker(f"level_cycle_start;cycle={cycle + 1}")
            for i, level in enumerate(levels):
                self._check_for_exit()
                level_id = level["id"]

                self._draw_level_options(levels, highlight_index=i)
                self.win.callOnFlip(
                    self._push_marker,
                    f"level_flash_on;id={level_id};index={i};cycle={cycle + 1}",
                )
                ts = time.time()
                self.win.flip()
                log.append((i, ts, cycle + 1))
                if self._wait_for_manual_selection(self._flash_dur, i, "level"):
                    self._draw_level_options(levels)
                    self.win.callOnFlip(
                        self._push_marker,
                        f"level_flash_off;id={level_id};index={i};cycle={cycle + 1}",
                    )
                    self.win.flip()
                    return log

                self._draw_level_options(levels)
                self.win.callOnFlip(
                    self._push_marker,
                    f"level_flash_off;id={level_id};index={i};cycle={cycle + 1}",
                )
                self.win.flip()
                self.wait(self._ifi)
        return log

    def show_message(
        self,
        text:     str,
        board:    chess.Board = None,
        duration: float = 4.0,
    ) -> None:
        """Display a text overlay (optionally on top of a board position)."""
        self._check_for_exit()
        if board is not None:
            self._draw_base(board)
        else:
            self._draw_background()
        visual.Rect(
            self.win,
            width=620,
            height=230,
            pos=(0, 0),
            fillColor=_PANEL,
            lineColor=_ACCENT,
            lineWidth=2,
            opacity=0.94,
            colorSpace='rgb',
        ).draw()
        visual.TextStim(
            self.win,
            text=text,
            pos=(0, 0),
            color=_ACCENT,
            colorSpace='rgb',
            height=56,
            bold=True,
            wrapWidth=540,
        ).draw()
        self.win.callOnFlip(self._push_marker, f"message;value={text}")
        self.win.flip()
        self.wait(duration)

    def close(self) -> None:
        self._push_marker("experiment_closed")
        self.win.close()

    def send_marker(self, marker: str) -> None:
        """Publish a non-visual experiment marker."""
        self._push_marker(marker)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_for_exit(self) -> None:
        self._check_for_keys()

    def _push_marker(self, marker: str) -> None:
        self._markers.push(marker)

    def _check_for_keys(self) -> None:
        keys = event.getKeys(keyList=['escape', 'q'])
        if 'escape' in keys or 'q' in keys:
            raise ExperimentStopped()

    def _wait_for_manual_selection(self, duration: float, index: int, kind: str) -> bool:
        """Return True when space is pressed during the active flash window."""
        event.clearEvents(eventType='keyboard')
        end_time = time.time() + duration
        while time.time() < end_time:
            keys = event.getKeys(keyList=['escape', 'q', 'space'])
            if 'escape' in keys or 'q' in keys:
                raise ExperimentStopped()
            if 'space' in keys:
                self._manual_selection_index = index
                self._push_marker(f"manual_selection;kind={kind};index={index}")
                return True
            core.wait(min(0.02, end_time - time.time()))
        return False

    def _sq_to_xy(self, sq: int) -> tuple:
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        x = _LEFT + file * _SQ + _SQ // 2
        y = _BOT  + rank * _SQ + _SQ // 2
        return x, y

    def _draw_background(self) -> None:
        visual.Rect(
            self.win,
            width=1280,
            height=720,
            pos=(0, 0),
            fillColor=_BG,
            lineColor=None,
            colorSpace='rgb',
        ).draw()
        visual.Circle(
            self.win,
            radius=360,
            pos=(-520, 290),
            fillColor=_ACCENT,
            lineColor=None,
            opacity=0.18,
            colorSpace='rgb',
        ).draw()
        visual.Circle(
            self.win,
            radius=320,
            pos=(530, -285),
            fillColor=_ACCENT,
            lineColor=None,
            opacity=0.12,
            colorSpace='rgb',
        ).draw()

    def _draw_text(
        self,
        text: str,
        pos: tuple,
        height: int,
        color: tuple = _TEXT,
        bold: bool = False,
        wrap_width: int = None,
        align_horiz: str = "center",
        font: str = "Arial",
    ) -> None:
        visual.TextStim(
            self.win,
            text=text,
            pos=pos,
            color=color,
            colorSpace='rgb',
            height=height,
            bold=bold,
            wrapWidth=wrap_width,
            alignText=align_horiz,
            anchorHoriz=align_horiz,
            font=font,
        ).draw()

    def _draw_panel(self, center: tuple, size: tuple, highlighted: bool = False) -> None:
        width, height = size
        if highlighted:
            visual.Rect(
                self.win,
                width=width + 22,
                height=height + 22,
                pos=center,
                fillColor=_ACCENT,
                lineColor=None,
                opacity=0.24,
                colorSpace='rgb',
            ).draw()
        visual.Rect(
            self.win,
            width=width,
            height=height,
            pos=center,
            fillColor=_PANEL_SOFT if highlighted else _PANEL,
            lineColor=_ACCENT if highlighted else (-0.55, -0.55, -0.55),
            lineWidth=4 if highlighted else 1,
            colorSpace='rgb',
        ).draw()

    def _init_rects(self) -> None:
        for sq in chess.SQUARES:
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            base = _LIGHT if (file + rank) % 2 == 1 else _DARK
            rect = visual.Rect(
                self.win,
                width=_SQ, height=_SQ,
                pos=self._sq_to_xy(sq),
                fillColor=base,
                lineColor=None,
                colorSpace='rgb',
            )
            self._rects[sq] = (rect, base)

    def _init_image(self, path: Path, size: tuple):
        if not path.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(path),
            size=size,
            units='pix',
        )

    def _init_white_rook_image(self):
        if not _ROOK_WHITE_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_ROOK_WHITE_IMAGE),
            size=(_SQ * 0.62, _SQ * 0.68),
            units='pix',
        )

    def _init_black_rook_image(self):
        if not _ROOK_BLACK_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_ROOK_BLACK_IMAGE),
            size=(_SQ * 0.62, _SQ * 0.68),
            units='pix',
        )

    def _init_white_knight_image(self):
        if not _KNIGHT_WHITE_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_KNIGHT_WHITE_IMAGE),
            size=(_SQ * 0.62, _SQ * 0.78),
            units='pix',
        )

    def _init_black_knight_image(self):
        if not _KNIGHT_BLACK_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_KNIGHT_BLACK_IMAGE),
            size=(_SQ * 0.62, _SQ * 0.78),
            units='pix',
        )

    def _init_white_bishop_image(self):
        if not _BISHOP_WHITE_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_BISHOP_WHITE_IMAGE),
            size=(_SQ * 0.68, _SQ * 0.72),
            units='pix',
        )

    def _init_black_bishop_image(self):
        if not _BISHOP_BLACK_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_BISHOP_BLACK_IMAGE),
            size=(_SQ * 0.68, _SQ * 0.72),
            units='pix',
        )

    def _init_white_pawn_image(self):
        if not _PAWN_WHITE_IMAGE.exists():
            return None
        return visual.ImageStim(
            self.win,
            image=str(_PAWN_WHITE_IMAGE),
            size=(_SQ * 0.56, _SQ * 0.72),
            units='pix',
        )

    def _piece_image_path(self, piece: chess.Piece):
        if piece.piece_type == chess.KING:
            return _KING_WHITE_IMAGE if piece.color == chess.WHITE else _KING_BLACK_IMAGE
        if piece.piece_type == chess.ROOK:
            return _ROOK_WHITE_IMAGE if piece.color == chess.WHITE else _ROOK_BLACK_IMAGE
        if piece.piece_type == chess.KNIGHT:
            return _KNIGHT_WHITE_IMAGE if piece.color == chess.WHITE else _KNIGHT_BLACK_IMAGE
        if piece.piece_type == chess.BISHOP:
            return _BISHOP_WHITE_IMAGE if piece.color == chess.WHITE else _BISHOP_BLACK_IMAGE
        if piece.piece_type == chess.PAWN and piece.color == chess.WHITE:
            return _PAWN_WHITE_IMAGE
        return None

    def _draw_level_options(self, levels: list, highlight_index: int = None) -> None:
        self._draw_background()
        self._draw_text("MindGambit", (-475, 300), 46, _ACCENT, font="Palatino Linotype")
        self._draw_text("Choose an Endgame Level", (-475, 245), 42, _ACCENT, wrap_width=620)
        self._draw_text(
            "Choose your battlefield. Focus on a level, or press Space when it flashes.",
            (-405, 195),
            22,
            _MUTED,
            wrap_width=700,
        )

        for i, level in enumerate(levels):
            x, y = _LEVEL_BOXES[i]
            highlighted = i == highlight_index
            y_pos = y + (10 if highlighted else 0)
            self._draw_panel((x, y_pos), (_LEVEL_CARD_W, _LEVEL_CARD_H), highlighted=highlighted)
            if highlighted:
                visual.Rect(
                    self.win,
                    width=_LEVEL_CARD_W - 16,
                    height=42,
                    pos=(x, y_pos + 140),
                    fillColor=_ACCENT,
                    lineColor=None,
                    opacity=0.22,
                    colorSpace='rgb',
                ).draw()
            self._draw_level_preview(level["fen"], center=(x, y_pos + 86))
            self._draw_text(level["tag"].upper(), (x - 108, y_pos - 58), 13, _ACCENT, True, 220, "left")
            self._draw_text(level["title"], (x - 108, y_pos - 86), 21, _TEXT, True, 220, "left")
            self._draw_text(level["description"], (x - 108, y_pos - 132), 15, _MUTED, False, 220, "left")

    def _draw_level_preview(self, fen: str, center: tuple) -> None:
        board = chess.Board(fen)
        board_size = _LEVEL_PREVIEW_SQ * 8
        left = center[0] - board_size / 2
        top = center[1] + board_size / 2
        visual.Rect(
            self.win,
            width=board_size + 12,
            height=board_size + 12,
            pos=center,
            fillColor=_PANEL,
            lineColor=_PANEL,
            lineWidth=6,
            colorSpace='rgb',
        ).draw()
        for rank_from_top in range(8):
            for file in range(8):
                x = left + file * _LEVEL_PREVIEW_SQ + _LEVEL_PREVIEW_SQ / 2
                y = top - rank_from_top * _LEVEL_PREVIEW_SQ - _LEVEL_PREVIEW_SQ / 2
                color = _LIGHT if (file + rank_from_top) % 2 == 0 else _DARK
                visual.Rect(
                    self.win,
                    width=_LEVEL_PREVIEW_SQ,
                    height=_LEVEL_PREVIEW_SQ,
                    pos=(x, y),
                    fillColor=color,
                    lineColor=None,
                    colorSpace='rgb',
                ).draw()
                square = chess.square(file, 7 - rank_from_top)
                piece = board.piece_at(square)
                if piece is None:
                    continue
                image_path = self._piece_image_path(piece)
                if image_path is not None and image_path.exists():
                    visual.ImageStim(
                        self.win,
                        image=str(image_path),
                        pos=(x, y),
                        size=(_LEVEL_PREVIEW_SQ * 0.72, _LEVEL_PREVIEW_SQ * 0.72),
                        units='pix',
                    ).draw()
                else:
                    visual.TextStim(
                        self.win,
                        text=piece.symbol().upper(),
                        pos=(x, y),
                        color=(1.0, 1.0, 1.0) if piece.color == chess.WHITE else (-1.0, -1.0, -1.0),
                        colorSpace='rgb',
                        height=14,
                        bold=True,
                    ).draw()

    def _draw_board_header(self) -> None:
        level = self._current_level or {}
        self._draw_text("SELECTED LEVEL", (-580, 305), 14, _ACCENT, True, 260, "left")
        self._draw_text(level.get("title", "MindGambit Chess"), (-580, 272), 28, _TEXT, True, 300, "left")
        self._draw_text(
            level.get("description", "Focus on the flashing chess option."),
            (-580, 220),
            17,
            _MUTED,
            False,
            300,
            "left",
        )

    def _draw_board_shell(self) -> None:
        board_size = _SQ * 8
        visual.Rect(
            self.win,
            width=board_size + _BOARD_FRAME_PAD * 2,
            height=board_size + _BOARD_FRAME_PAD * 2,
            pos=(0, 0),
            fillColor=_PANEL,
            lineColor=_PANEL,
            lineWidth=10,
            colorSpace='rgb',
        ).draw()

    def _draw_board_labels(self) -> None:
        for file, label in enumerate(_FILES):
            x = _LEFT + file * _SQ + _SQ // 2
            self._draw_text(label, (x, _BOT - 22), 14, _ACCENT, True)
        for rank_from_top in range(8):
            rank = 8 - rank_from_top
            y = _BOT + (7 - rank_from_top) * _SQ + _SQ // 2
            self._draw_text(str(rank), (_LEFT - 22, y), 14, _ACCENT, True)

    def _draw_level_panel(self, board: chess.Board, highlights: set) -> None:
        x, y = 505, 70
        self._draw_panel((x, y), (300, 455))
        level = self._current_level or {}
        highlighted_text = self._format_highlights(highlights) if highlights else "Waiting..."
        goal = level.get("goal", "Watch the target square during calibration.")
        fen = board.fen()
        self._draw_text("Status", (x - 125, y + 180), 17, _TEXT, True, 250, "left")
        self._draw_text(self._status_text, (x - 125, y + 145), 15, _MUTED, False, 250, "left")
        self._draw_text("Endgame Goal", (x - 125, y + 70), 17, _TEXT, True, 250, "left")
        self._draw_text(goal, (x - 125, y + 25), 15, _MUTED, False, 250, "left")
        self._draw_text("Chosen Position", (x - 125, y - 80), 17, _TEXT, True, 250, "left")
        self._draw_text(highlighted_text, (x - 125, y - 112), 15, _ACCENT, False, 250, "left")
        self._draw_text(fen, (x - 125, y - 165), 12, _ACCENT, False, 250, "left")

    def _format_highlights(self, highlights: set) -> str:
        names = [chess.square_name(square) for square in sorted(highlights)]
        return ", ".join(names)

    def _draw_calibration_base(self, board: chess.Board, highlight_squares=None) -> None:
        """Draw a clean board only for calibration flashes."""
        self._draw_background()
        self._draw_board_shell()
        highlights = set(highlight_squares or [])
        for sq, (rect, base) in self._rects.items():
            rect.fillColor = _FLASH if sq in highlights else base
            rect.draw()

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None:
                continue
            x, y = self._sq_to_xy(sq)
            color = (1.0, 1.0, 1.0) if piece.color == chess.WHITE else (-0.84, -0.84, -0.84)
            visual.TextStim(
                self.win,
                text=piece.symbol().upper(),
                pos=(x, y),
                color=color,
                colorSpace='rgb',
                height=int(_SQ * 0.65),
                bold=True,
            ).draw()

    def _draw_base(self, board: chess.Board, highlight_sq=None, highlight_squares=None) -> None:
        """Draw all squares + pieces without flipping."""
        self._draw_background()
        self._draw_board_header()
        self._draw_board_shell()
        highlights = set(highlight_squares or [])
        if highlight_sq is not None:
            highlights.add(highlight_sq)

        for sq, (rect, base) in self._rects.items():
            rect.fillColor = _FLASH if sq in highlights else base
            rect.draw()

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None:
                continue
            x, y = self._sq_to_xy(sq)
            if (
                piece.piece_type == chess.KING
                and (
                    (piece.color == chess.WHITE and self._white_king is not None)
                    or (piece.color == chess.BLACK and self._black_king is not None)
                )
            ):
                king = self._white_king if piece.color == chess.WHITE else self._black_king
                king.pos = (x, y)
                king.draw()
                continue
            if (
                piece.piece_type == chess.ROOK
                and piece.color == chess.WHITE
                and self._white_rook is not None
            ):
                self._white_rook.pos = (x, y)
                self._white_rook.draw()
                continue
            if (
                piece.piece_type == chess.ROOK
                and piece.color == chess.BLACK
                and self._black_rook is not None
            ):
                self._black_rook.pos = (x, y)
                self._black_rook.draw()
                continue
            if (
                piece.piece_type == chess.KNIGHT
                and piece.color == chess.WHITE
                and self._white_knight is not None
            ):
                self._white_knight.pos = (x, y)
                self._white_knight.draw()
                continue
            if (
                piece.piece_type == chess.KNIGHT
                and piece.color == chess.BLACK
                and self._black_knight is not None
            ):
                self._black_knight.pos = (x, y)
                self._black_knight.draw()
                continue
            if (
                piece.piece_type == chess.BISHOP
                and piece.color == chess.WHITE
                and self._white_bishop is not None
            ):
                self._white_bishop.pos = (x, y)
                self._white_bishop.draw()
                continue
            if (
                piece.piece_type == chess.BISHOP
                and piece.color == chess.BLACK
                and self._black_bishop is not None
            ):
                self._black_bishop.pos = (x, y)
                self._black_bishop.draw()
                continue
            if (
                piece.piece_type == chess.PAWN
                and piece.color == chess.WHITE
                and self._white_pawn is not None
            ):
                self._white_pawn.pos = (x, y)
                self._white_pawn.draw()
                continue

            color = (1.0, 1.0, 1.0) if piece.color == chess.WHITE else (-0.84, -0.84, -0.84)
            visual.TextStim(
                self.win,
                text=piece.symbol().upper(),
                pos=(x, y),
                color=color,
                colorSpace='rgb',
                height=int(_SQ * 0.65),
                bold=True,
            ).draw()

        self._draw_board_labels()
        self._draw_level_panel(board, highlights)
