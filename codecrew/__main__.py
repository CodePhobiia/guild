"""Entry point for running CodeCrew as a module."""

from codecrew.cli import app


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
