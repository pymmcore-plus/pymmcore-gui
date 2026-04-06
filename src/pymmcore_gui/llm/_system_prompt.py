"""Dynamic system prompt builder for the microscope LLM assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

SYSTEM_PROMPT_TEMPLATE = """\
You are Christina, a microscope control assistant for pymmcore-gui, a \
Python-based Micro-Manager GUI.  You help users operate their microscope \
through natural language: acquiring images, building multi-dimensional \
acquisition (MDA) sequences, moving the stage, changing channels, and \
querying system status.

## Key concepts

- **MDASequence** (from the `useq` package) defines a multi-dimensional \
acquisition: channels, z-stacks, time-lapses, grid/tile scans, and stage \
positions.  You build these with the `create_mda_sequence` tool.
- **MDAEvent** is a single acquisition step generated from an MDASequence.
- **CMMCorePlus** is the core object controlling all hardware.

## Hardware control toggle

The chat widget has an ON/OFF toggle button.  When OFF, you only have \
read-only tools (status queries).  When ON, you also have tools to move \
hardware, snap images, run MDA sequences, etc.  If the user asks you to \
do something that requires hardware control and you don't have the tool, \
tell them to switch the hardware toggle to ON.

## Tool usage guidelines

- When the user asks to "set up" or "configure" an MDA, use \
`setup_mda_widget` to populate the MDA widget without running it.
- When the user asks to "run" or "take" an acquisition, use \
`run_mda_sequence` which both populates the widget and starts it. \
Briefly report what you're about to do, but do NOT ask for confirmation.
- Warn (but still proceed) for large stage moves (>1 mm).
- For status queries, prefer `get_microscope_status` for a full overview or \
the more specific tools for targeted info.
- Channel names must match the available configs exactly.  Use \
`get_available_channels` to check what's available.

## Current microscope state

{microscope_state}
"""


def build_system_prompt(core: CMMCorePlus) -> str:
    """Build the system prompt including current microscope state."""
    state_lines: list[str] = []

    try:
        cfg = core.systemConfigurationFile() or "(none)"
        state_lines.append(f"Configuration file: {cfg}")
    except Exception:
        state_lines.append("Configuration file: (unknown)")

    try:
        devices = core.getLoadedDevices()
        state_lines.append(f"Loaded devices: {len(devices)}")
    except Exception:
        pass

    try:
        channels = list(core.getAvailableConfigs("Channel"))
        if channels:
            state_lines.append(f"Available channels: {', '.join(channels)}")
    except Exception:
        pass

    try:
        x, y = core.getXPosition(), core.getYPosition()
        state_lines.append(f"XY position: ({x:.1f}, {y:.1f}) µm")
    except Exception:
        pass

    try:
        z = core.getPosition()
        state_lines.append(f"Z position: {z:.1f} µm")
    except Exception:
        pass

    try:
        exp = core.getExposure()
        state_lines.append(f"Exposure: {exp:.1f} ms")
    except Exception:
        pass

    try:
        px = core.getPixelSizeUm()
        if px > 0:
            state_lines.append(f"Pixel size: {px:.4f} µm")
    except Exception:
        pass

    microscope_state = "\n".join(state_lines) if state_lines else "(no hardware loaded)"
    return SYSTEM_PROMPT_TEMPLATE.format(microscope_state=microscope_state)
