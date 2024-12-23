bundle:
    uv run pyinstaller app/mmgui.spec  --log-level INFO

lint:
    uv run pre-commit run --all-files

test:
    uv run pytest