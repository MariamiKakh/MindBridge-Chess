"""Translate decoded BCI selections into chess moves."""


class BCIInterface:
    """Maps piece, direction, and square selections to board commands."""

    def __init__(self, board):
        self.board = board

    def select_piece(self, piece_id):
        pass

    def select_direction(self, direction_id):
        pass

    def select_square(self, square_id):
        pass
