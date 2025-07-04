set windows-powershell

# run the main application
run:
    uv run python -m pymmcore_gui

# create application bundle using pyinstaller
bundle:
    uv run pyinstaller app/mmgui.spec --clean --noconfirm --log-level INFO

# lint all files with pre-commit
lint:
    uv run pre-commit run --all-files

# run tests
test:
    uv run pytest

# switch to pyside6 backend
use-pyside:
    uv sync --group PySide6 --no-install-package PyQt6 --no-install-package PyQt6Ads
