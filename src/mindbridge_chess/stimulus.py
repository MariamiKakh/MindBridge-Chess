"""Stimulus presentation logic using PsychoPy."""

from pathlib import Path
import time

import chess
from psychopy import core, event, visual

# Board geometry (pixels, PsychoPy units='pix', origin at screen centre)
_SQ   = 80          # square side length
_LEFT = -320        # x of the board's left edge
_BOT  = -320        # y of the board's bottom edge

# Colours in PsychoPy rgb space (-1 to 1)
_LIGHT  = ( 0.64,  0.09, -0.44)   # warm beige
_DARK   = (-0.40, -0.63, -0.78)   # dark brown
_FLASH  = ( 1.00,  1.00, -1.00)   # bright yellow
_WIN_BG = (-0.69, -0.69, -0.69)   # dark grey
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


class ManualSelection(Exception):
    """Raised when the user manually selects the highlighted stimulus."""

    def __init__(self, stimulus_index: int):
        self.stimulus_index = stimulus_index


class StimulusPresenter:
    """Renders the chess board and drives the P300 flashing protocol."""

    def __init__(self, config=None):
        cfg = config or {}
        self._flash_dur = cfg.get('flash_duration_ms', 100) / 1000.0
        self._ifi       = cfg.get('inter_flash_ms',    75)  / 1000.0
        self._cycles    = cfg.get('cycles_per_decision', 3)

        self.win = visual.Window(
            size=(720, 720),
            fullscr=False,
            color=_WIN_BG,
            colorSpace='rgb',
            units='pix',
            allowGUI=True,
        )
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

    def draw_board(self, board: chess.Board) -> None:
        """Render the current board position and flip."""
        self._check_for_exit()
        self._draw_base(board)
        self.win.flip()

    def wait(self, duration: float, selection_index: int = None) -> None:
        """Wait while still responding to exit keys."""
        end_time = time.time() + duration
        while time.time() < end_time:
            self._check_for_keys(selection_index)
            core.wait(min(0.02, end_time - time.time()))

    def flash_squares(self, board: chess.Board, squares: list) -> list:
        """
        Flash each square in *squares* one at a time for *_cycles* full passes.

        Returns a list of (stim_index, wall_timestamp_at_onset) — one entry per
        flash, ordered by (cycle, square).  stim_index is the 0-based position of
        the flashed square within *squares*.
        """
        log: list = []
        for _cycle in range(self._cycles):
            for i, sq in enumerate(squares):
                self._check_for_exit()

                # --- flash ON ---
                self._draw_base(board, highlight_sq=sq)
                ts = time.time()
                self.win.flip()
                log.append((i, ts))
                self.wait(self._flash_dur, selection_index=i)

                # --- flash OFF ---
                self._draw_base(board)
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
        for _cycle in range(self._cycles):
            for i, squares in enumerate(square_groups):
                self._check_for_exit()

                self._draw_base(board, highlight_squares=squares)
                ts = time.time()
                self.win.flip()
                log.append((i, ts))
                self.wait(self._flash_dur, selection_index=i)

                self._draw_base(board)
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
        visual.TextStim(
            self.win,
            text=text,
            pos=(0, 0),
            color=(1.0, 1.0, -1.0),
            colorSpace='rgb',
            height=80,
            bold=True,
        ).draw()
        self.win.flip()
        self.wait(duration)

    def close(self) -> None:
        self.win.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_for_exit(self) -> None:
        self._check_for_keys()

    def _check_for_keys(self, selection_index: int = None) -> None:
        keys = event.getKeys(keyList=['escape', 'q', 'space'])
        if 'escape' in keys or 'q' in keys:
            raise ExperimentStopped()
        if selection_index is not None and 'space' in keys:
            raise ManualSelection(selection_index)

    def _sq_to_xy(self, sq: int) -> tuple:
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        x = _LEFT + file * _SQ + _SQ // 2
        y = _BOT  + rank * _SQ + _SQ // 2
        return x, y

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

    def _draw_base(self, board: chess.Board, highlight_sq=None, highlight_squares=None) -> None:
        """Draw all squares + pieces without flipping."""
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
