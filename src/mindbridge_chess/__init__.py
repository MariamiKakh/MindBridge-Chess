"""MindBridge Chess BCI package."""

def main() -> None:
    """Run the application entry point."""
    from .app import main as app_main

    app_main()

__all__ = ["main"]
