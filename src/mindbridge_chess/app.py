"""Main application entry point for the BCI chess system."""

from .exercise_rook_checkmate import RookCheckmateExercise


def main() -> None:
    """Run the 2 Rooks vs Lone King checkmate exercise."""
    RookCheckmateExercise().run()


if __name__ == "__main__":
    main()
