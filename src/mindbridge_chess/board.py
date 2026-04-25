"""Chess board and move management using python-chess."""

import random

import chess


class ChessBoard:
    """Wraps python-chess board state and legal move handling."""

    def __init__(self) -> None:
        self.board = chess.Board()

    def load_fen(self, fen: str) -> None:
        self.board = chess.Board(fen)

    def get_legal_moves(self) -> list:
        return list(self.board.legal_moves)

    def apply_move(self, move: chess.Move) -> None:
        self.board.push(move)

    def get_white_rook_squares(self) -> list:
        """Return list of chess.Square for every white rook still on the board."""
        return list(self.board.pieces(chess.ROOK, chess.WHITE))

    def get_legal_moves_for_square(self, square: chess.Square) -> list:
        """Return all legal moves whose origin is *square*."""
        return [m for m in self.board.legal_moves if m.from_square == square]

    def get_black_auto_move(self):
        """Pick a random legal move for black (used for auto-play)."""
        moves = list(self.board.legal_moves)
        return random.choice(moves) if moves else None

    def is_checkmate(self) -> bool:
        return self.board.is_checkmate()

    def is_game_over(self) -> bool:
        return self.board.is_game_over()

    @property
    def turn(self) -> chess.Color:
        return self.board.turn
