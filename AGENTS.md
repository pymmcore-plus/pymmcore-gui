# pymmcore-gui

This project is a high level Qt-based application for microscope control.

It wraps many lower-level libraries in the pymmcore-plus ecosystm:

- `pymmcore-plus`: The core programmatic library (which in turn wraps
  `pymmcore`: python bindings for the C++ Micro-Manager core library).
- `pymmcore-widgets`: An unarranged collection of Qt widgets for controlling and
   monitoring the `pymmcore_plus.CMMCorePlus` object.
- `ndv`: The primary image/stack viewing library.
- `useq-schema`: The data model for defining microscopy acquisition sequences.

This repo occasionally needs to subclass/modify/extend objects from these lower
level libraries.  But, if a change/feature does *not* need application-wide
awareness, consider making a PR to the lower level library.

## Commands

- Install: `uv sync`
- Test: `uv run pytest`
- Lint & Type check: `uv run prek -a`
- Install pre-commit hooks: `uv run prek install -f`

## Conventions & Project Principles

- Use `uv` for everything.
- PRs require passing CI before merge (`uv run prek -a` && `uv run pytest`).
- Resist using `setStyleSheet`.  Theming will be done application-wide.
- All qt library objects should be imported from `pymmcore_gui._qt` (our custom
  wrapper around PyQt/PySide).

## Git Workflow

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
