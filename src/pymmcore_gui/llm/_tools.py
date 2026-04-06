"""Shared tool definitions for microscope control.

Each tool is a ToolDef with a name, description, JSON schema, a sync handler
that runs on the Qt main thread, and a readonly flag. Both the Claude and
Ollama backends adapt these into their own formats.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import useq
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.metadata import summary_metadata

from pymmcore_gui._qt.QtCore import QObject, Signal

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Main-thread bridge (shared by all backends)
# ---------------------------------------------------------------------------


class _MainThreadInvoker(QObject):
    """Invoke callables on the Qt main thread via a signal."""

    _call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(self._execute)

    @staticmethod
    def _execute(func: object) -> None:
        if callable(func):
            func()


_invoker = _MainThreadInvoker()


def call_in_main_thread(func: Callable[..., Any], *args: Any) -> Any:
    """Run *func* on the Qt main thread (blocking the caller)."""
    future: concurrent.futures.Future[Any] = concurrent.futures.Future()

    def _run() -> None:
        try:
            future.set_result(func(*args))
        except Exception as exc:
            future.set_exception(exc)

    _invoker._call.emit(_run)
    return future.result(timeout=30)


# ---------------------------------------------------------------------------
# ToolDef
# ---------------------------------------------------------------------------


@dataclass
class ToolDef:
    """A tool that can be used by any LLM backend."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    handler: Callable[[dict[str, Any]], str]  # sync, returns text result
    readonly: bool = True


# ---------------------------------------------------------------------------
# Tool handlers (sync, called from background threads)
# ---------------------------------------------------------------------------


def _get_microscope_status(_args: dict[str, Any]) -> str:
    def _get() -> str:
        core = CMMCorePlus.instance()
        meta = summary_metadata(core, include_property_details=False)
        return json.dumps(meta, default=str, indent=2)

    return call_in_main_thread(_get)


def _get_current_position(_args: dict[str, Any]) -> str:
    def _get() -> str:
        core = CMMCorePlus.instance()
        try:
            x, y = core.getXPosition(), core.getYPosition()
        except Exception:
            x, y = float("nan"), float("nan")
        try:
            z = core.getPosition()
        except Exception:
            z = float("nan")
        return json.dumps({"x_um": x, "y_um": y, "z_um": z})

    return call_in_main_thread(_get)


def _get_available_channels(_args: dict[str, Any]) -> str:
    def _get() -> str:
        core = CMMCorePlus.instance()
        return json.dumps(list(core.getAvailableConfigs("Channel")))

    return call_in_main_thread(_get)


def _get_loaded_devices(_args: dict[str, Any]) -> str:
    def _get() -> str:
        core = CMMCorePlus.instance()
        devices = []
        for label in core.getLoadedDevices():
            try:
                dev_type = core.getDeviceType(label).name
            except Exception:
                dev_type = "Unknown"
            devices.append({"label": label, "type": dev_type})
        return json.dumps(devices, indent=2)

    return call_in_main_thread(_get)


def _get_device_properties(args: dict[str, Any]) -> str:
    label = args["device_label"]

    def _get() -> str:
        core = CMMCorePlus.instance()
        props = {}
        for name in core.getDevicePropertyNames(label):
            try:
                props[name] = core.getProperty(label, name)
            except Exception:
                props[name] = "(error reading)"
        return json.dumps(props, indent=2)

    return call_in_main_thread(_get)


def _get_current_exposure(_args: dict[str, Any]) -> str:
    def _get() -> str:
        return json.dumps({"exposure_ms": CMMCorePlus.instance().getExposure()})

    return call_in_main_thread(_get)


def _get_pixel_size(_args: dict[str, Any]) -> str:
    def _get() -> str:
        return json.dumps({"pixel_size_um": CMMCorePlus.instance().getPixelSizeUm()})

    return call_in_main_thread(_get)


def _get_mda_status(_args: dict[str, Any]) -> str:
    def _get() -> str:
        runner = CMMCorePlus.instance().mda
        return json.dumps(
            {"is_running": runner.is_running(), "is_paused": runner.is_paused()}
        )

    return call_in_main_thread(_get)


def _create_mda_sequence(args: dict[str, Any]) -> str:
    try:
        seq = useq.MDASequence.model_validate(args)
    except Exception as e:
        return f"Validation error: {e}"

    n_events = sum(1 for _ in seq)
    est = seq.estimate_duration()
    summary = {
        "uid": str(seq.uid),
        "num_events": n_events,
        "axes_used": seq.used_axes,
        "sizes": dict(seq.sizes),
        "estimated_duration_s": est.total_duration,
        "sequence_json": seq.model_dump(mode="json", exclude_defaults=True),
    }
    return json.dumps(summary, indent=2)


def _run_mda_sequence(args: dict[str, Any]) -> str:
    try:
        seq = useq.MDASequence.model_validate(args)
    except Exception as e:
        return f"Validation error: {e}"

    def _run() -> str:
        CMMCorePlus.instance().run_mda(seq, output="memory")
        return json.dumps(
            {
                "status": "started",
                "uid": str(seq.uid),
                "num_events": sum(1 for _ in seq),
            }
        )

    return call_in_main_thread(_run)


def _move_stage(args: dict[str, Any]) -> str:
    def _move() -> str:
        core = CMMCorePlus.instance()
        moved = []
        if "x_um" in args and "y_um" in args:
            core.setXYPosition(args["x_um"], args["y_um"])
            moved.append(f"XY to ({args['x_um']}, {args['y_um']})")
        if "z_um" in args:
            core.setPosition(args["z_um"])
            moved.append(f"Z to {args['z_um']}")
        return f"Moved: {', '.join(moved)}" if moved else "No position specified."

    return call_in_main_thread(_move)


def _set_exposure(args: dict[str, Any]) -> str:
    ms = args["exposure_ms"]

    def _set() -> str:
        CMMCorePlus.instance().setExposure(ms)
        return f"Exposure set to {ms} ms."

    return call_in_main_thread(_set)


def _set_channel(args: dict[str, Any]) -> str:
    name = args["channel_name"]

    def _set() -> str:
        CMMCorePlus.instance().setConfig("Channel", name)
        return f"Channel set to '{name}'."

    return call_in_main_thread(_set)


def _snap_image(_args: dict[str, Any]) -> str:
    def _snap() -> str:
        CMMCorePlus.instance().snap()
        return "Image snapped."

    return call_in_main_thread(_snap)


def _start_live(_args: dict[str, Any]) -> str:
    def _start() -> str:
        CMMCorePlus.instance().startContinuousSequenceAcquisition(0)
        return "Live mode started."

    return call_in_main_thread(_start)


def _stop_live(_args: dict[str, Any]) -> str:
    def _stop() -> str:
        CMMCorePlus.instance().stopSequenceAcquisition()
        return "Live mode stopped."

    return call_in_main_thread(_stop)


def _set_property(args: dict[str, Any]) -> str:
    dev, prop, val = args["device"], args["property_name"], args["value"]

    def _set() -> str:
        CMMCorePlus.instance().setProperty(dev, prop, val)
        return f"Set {dev}.{prop} = {val}"

    return call_in_main_thread(_set)


def _pause_mda(_args: dict[str, Any]) -> str:
    def _pause() -> str:
        runner = CMMCorePlus.instance().mda
        runner.set_paused(not runner.is_paused())
        state = "paused" if runner.is_paused() else "resumed"
        return f"MDA {state}."

    return call_in_main_thread(_pause)


def _cancel_mda(_args: dict[str, Any]) -> str:
    def _cancel() -> str:
        CMMCorePlus.instance().mda.cancel()
        return "MDA cancelled."

    return call_in_main_thread(_cancel)


# ---------------------------------------------------------------------------
# MDA schema (shared between backends)
# ---------------------------------------------------------------------------

MDA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "channels": {
            "type": "array",
            "description": (
                "Channels to acquire. Each needs 'config' matching an "
                "available preset. Optional: 'exposure' (ms), 'do_stack', "
                "'z_offset' (um)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "config": {"type": "string"},
                    "group": {"type": "string", "default": "Channel"},
                    "exposure": {"type": "number"},
                    "do_stack": {"type": "boolean", "default": True},
                    "z_offset": {"type": "number", "default": 0},
                },
                "required": ["config"],
            },
        },
        "time_plan": {
            "type": "object",
            "description": (
                "Time-lapse: {'interval': seconds, 'loops': N} "
                "or {'duration': seconds, 'loops': N}."
            ),
            "properties": {
                "interval": {"type": "number"},
                "loops": {"type": "integer"},
                "duration": {"type": "number"},
            },
        },
        "z_plan": {
            "type": "object",
            "description": (
                "Z-stack: {'range': um, 'step': um} for symmetric, "
                "or {'above': um, 'below': um, 'step': um}, "
                "or {'top': um, 'bottom': um, 'step': um}."
            ),
            "properties": {
                "range": {"type": "number"},
                "above": {"type": "number"},
                "below": {"type": "number"},
                "top": {"type": "number"},
                "bottom": {"type": "number"},
                "step": {"type": "number"},
                "go_up": {"type": "boolean", "default": True},
            },
        },
        "stage_positions": {
            "type": "array",
            "description": "Stage positions: x, y, z (um), name.",
            "items": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                    "name": {"type": "string"},
                },
            },
        },
        "grid_plan": {
            "type": "object",
            "description": (
                "Grid/tile: {'rows': N, 'columns': N} or {'width': um, 'height': um}."
            ),
            "properties": {
                "rows": {"type": "integer"},
                "columns": {"type": "integer"},
                "width": {"type": "number"},
                "height": {"type": "number"},
                "overlap": {
                    "type": "array",
                    "items": {"type": "number"},
                },
            },
        },
        "axis_order": {
            "type": "string",
            "description": "Axis order string, e.g. 'tpgcz'.",
            "default": "tpgcz",
        },
    },
}

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


def _td(
    name: str,
    desc: str,
    handler: Callable[[dict[str, Any]], str],
    params: dict[str, Any] | None = None,
    *,
    readonly: bool = True,
) -> ToolDef:
    return ToolDef(name, desc, params or {}, handler, readonly=readonly)


_r, _w = True, False  # readonly flags

READONLY_TOOLS: list[ToolDef] = [
    _td("get_microscope_status", "Get microscope state.", _get_microscope_status),
    _td("get_current_position", "Get XY/Z position.", _get_current_position),
    _td("get_available_channels", "List channels.", _get_available_channels),
    _td("get_loaded_devices", "List devices.", _get_loaded_devices),
    _td(
        "get_device_properties",
        "Get device properties.",
        _get_device_properties,
        {"device_label": str},
    ),
    _td("get_current_exposure", "Get exposure (ms).", _get_current_exposure),
    _td("get_pixel_size", "Get pixel size (um).", _get_pixel_size),
    _td("get_mda_status", "Check MDA status.", _get_mda_status),
]

WRITE_TOOLS: list[ToolDef] = [
    _td(
        "create_mda_sequence",
        "Preview an MDA sequence.",
        _create_mda_sequence,
        MDA_SCHEMA,
        readonly=_w,
    ),
    _td(
        "run_mda_sequence",
        "Run an MDA sequence.",
        _run_mda_sequence,
        MDA_SCHEMA,
        readonly=_w,
    ),
    _td(
        "move_stage",
        "Move stage (um).",
        _move_stage,
        {"x_um": float, "y_um": float, "z_um": float},
        readonly=_w,
    ),
    _td(
        "set_exposure",
        "Set exposure (ms).",
        _set_exposure,
        {"exposure_ms": float},
        readonly=_w,
    ),
    _td(
        "set_channel",
        "Set channel preset.",
        _set_channel,
        {"channel_name": str},
        readonly=_w,
    ),
    _td("snap_image", "Snap an image.", _snap_image, readonly=_w),
    _td("start_live", "Start live mode.", _start_live, readonly=_w),
    _td("stop_live", "Stop live mode.", _stop_live, readonly=_w),
    _td(
        "set_property",
        "Set device property.",
        _set_property,
        {"device": str, "property_name": str, "value": str},
        readonly=_w,
    ),
    _td("pause_mda", "Pause/resume MDA.", _pause_mda, readonly=_w),
    _td("cancel_mda", "Cancel MDA.", _cancel_mda, readonly=_w),
]

ALL_TOOLS: list[ToolDef] = READONLY_TOOLS + WRITE_TOOLS


def get_tools(*, hardware_enabled: bool = True) -> list[ToolDef]:
    """Return the appropriate tool set based on hardware toggle."""
    return ALL_TOOLS if hardware_enabled else READONLY_TOOLS
