import pytest

from mindbridge_chess.board import ChessBoard


def test_board_initializes():
    board = ChessBoard()
    assert board.get_legal_moves()
