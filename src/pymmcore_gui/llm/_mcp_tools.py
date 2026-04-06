"""MCP tool definitions for microscope control."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from typing import TYPE_CHECKING, Any

import useq
from claude_code_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.metadata import summary_metadata

from pymmcore_gui._qt.QtCore import QObject, Signal

if TYPE_CHECKING:
    from claude_code_sdk.types import McpSdkServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Main-thread bridge: CMMCorePlus must be called from the Qt main thread.
# Tool handlers run in the SDK's async context (background thread).
#
# QTimer.singleShot(0, cb) does NOT work from a non-Qt thread because the
# timer is created in the calling thread's event loop.  Instead we use a
# signal with AutoConnection: emitting from the bg thread delivers the slot
# via QueuedConnection to the main thread.
# ---------------------------------------------------------------------------


class _MainThreadInvoker(QObject):
    """Invoke callables on the Qt main thread via a signal."""

    _call = Signal(object)  # carries a zero-arg callable

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(self._execute)

    @staticmethod
    def _execute(func: object) -> None:
        if callable(func):
            func()


# Singleton - created at import time (main thread).
_invoker = _MainThreadInvoker()


async def run_on_main_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run *func* on the Qt main thread and return the result."""
    future: concurrent.futures.Future[Any] = concurrent.futures.Future()

    def _run() -> None:
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    _invoker._call.emit(_run)
    return await asyncio.wrap_future(future)


def _text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": text}],
    }
    if is_error:
        result["is_error"] = True
    return result


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------


@tool("get_microscope_status", "Get a full summary of the microscope state.", {})
async def get_microscope_status(args: dict[str, Any]) -> dict[str, Any]:
    """Return summary_metadata as JSON."""

    def _get() -> str:
        core = CMMCorePlus.instance()
        meta = summary_metadata(core, include_property_details=False)
        return json.dumps(meta, default=str, indent=2)

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool(
    "get_current_position",
    "Get the current XY and Z stage positions in microns.",
    {},
)
async def get_current_position(args: dict[str, Any]) -> dict[str, Any]:
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

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool(
    "get_available_channels",
    "List the available channel configuration names.",
    {},
)
async def get_available_channels(args: dict[str, Any]) -> dict[str, Any]:
    def _get() -> str:
        core = CMMCorePlus.instance()
        channels = list(core.getAvailableConfigs("Channel"))
        return json.dumps(channels)

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool(
    "get_loaded_devices",
    "List all loaded devices with their types.",
    {},
)
async def get_loaded_devices(args: dict[str, Any]) -> dict[str, Any]:
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

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool(
    "get_device_properties",
    "Get all properties and current values for a specific device.",
    {"device_label": str},
)
async def get_device_properties(args: dict[str, Any]) -> dict[str, Any]:
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

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool("get_current_exposure", "Get the current camera exposure time in ms.", {})
async def get_current_exposure(args: dict[str, Any]) -> dict[str, Any]:
    def _get() -> str:
        core = CMMCorePlus.instance()
        return json.dumps({"exposure_ms": core.getExposure()})

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool("get_pixel_size", "Get the current pixel size in microns.", {})
async def get_pixel_size(args: dict[str, Any]) -> dict[str, Any]:
    def _get() -> str:
        core = CMMCorePlus.instance()
        return json.dumps({"pixel_size_um": core.getPixelSizeUm()})

    text = await run_on_main_thread(_get)
    return _text_result(text)


@tool(
    "get_mda_status",
    "Check whether an MDA acquisition is currently running or paused.",
    {},
)
async def get_mda_status(args: dict[str, Any]) -> dict[str, Any]:
    def _get() -> str:
        core = CMMCorePlus.instance()
        runner = core.mda
        return json.dumps(
            {"is_running": runner.is_running(), "is_paused": runner.is_paused()}
        )

    text = await run_on_main_thread(_get)
    return _text_result(text)


# ---------------------------------------------------------------------------
# Write tools (require hardware control ON)
# ---------------------------------------------------------------------------

# Simplified MDA schema — the full MDASequence.model_json_schema() uses $ref/$defs
# which the Claude API rejects.  This flat schema covers the common parameters and
# the handler uses MDASequence.model_validate() for full validation.
_MDA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "channels": {
            "type": "array",
            "description": (
                "Channels to acquire. Each channel needs a 'config' name "
                "matching an available channel preset (use get_available_channels). "
                "Optional: 'exposure' (ms), 'do_stack' (bool), 'z_offset' (um)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "config": {"type": "string"},
                    "group": {
                        "type": "string",
                        "default": "Channel",
                    },
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
                "Time-lapse settings. Common: {'interval': seconds, 'loops': N}. "
                "Or use {'duration': seconds, 'loops': N}."
            ),
            "properties": {
                "interval": {"type": "number", "description": "Seconds between frames"},
                "loops": {"type": "integer", "description": "Number of timepoints"},
                "duration": {
                    "type": "number",
                    "description": "Total duration in seconds",
                },
            },
        },
        "z_plan": {
            "type": "object",
            "description": (
                "Z-stack settings. Use {'range': um, 'step': um} for symmetric "
                "range around current Z. Or {'above': um, 'below': um, 'step': um}. "
                "Or {'top': um, 'bottom': um, 'step': um} for absolute positions."
            ),
            "properties": {
                "range": {"type": "number", "description": "Symmetric range (um)"},
                "above": {"type": "number", "description": "Range above Z (um)"},
                "below": {"type": "number", "description": "Range below Z (um)"},
                "top": {"type": "number", "description": "Absolute top Z (um)"},
                "bottom": {"type": "number", "description": "Absolute bottom Z (um)"},
                "step": {"type": "number", "description": "Step size in um"},
                "go_up": {"type": "boolean", "default": True},
            },
        },
        "stage_positions": {
            "type": "array",
            "description": "Stage positions to visit: x, y, z (um), name.",
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
                "Grid/tile scan. Use {'rows': N, 'columns': N} for a grid, "
                "or {'width': um, 'height': um} for area-based. "
                "'overlap' is a [x_pct, y_pct] array (0-100)."
            ),
            "properties": {
                "rows": {"type": "integer"},
                "columns": {"type": "integer"},
                "width": {"type": "number"},
                "height": {"type": "number"},
                "overlap": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Overlap percentages [x, y]",
                },
            },
        },
        "axis_order": {
            "type": "string",
            "description": (
                "Iteration order as a string of axis chars: t=time, p=position, "
                "g=grid, c=channel, z=z-stack.  Default: 'tpgcz'."
            ),
            "default": "tpgcz",
        },
    },
}


@tool(
    "create_mda_sequence",
    "Create and validate an MDA (multi-dimensional acquisition) sequence. "
    "Returns a preview with event count and estimated duration. "
    "Does NOT start the acquisition - use run_mda_sequence for that.",
    _MDA_SCHEMA,
)
async def create_mda_sequence(args: dict[str, Any]) -> dict[str, Any]:
    try:
        seq = useq.MDASequence.model_validate(args)
    except Exception as e:
        return _text_result(f"Validation error: {e}", is_error=True)

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
    return _text_result(json.dumps(summary, indent=2))


@tool(
    "run_mda_sequence",
    "Run an MDA sequence on the microscope. "
    "Pass the same parameters as create_mda_sequence.",
    _MDA_SCHEMA,
)
async def run_mda_sequence(args: dict[str, Any]) -> dict[str, Any]:
    try:
        seq = useq.MDASequence.model_validate(args)
    except Exception as e:
        return _text_result(f"Validation error: {e}", is_error=True)

    def _run() -> str:
        core = CMMCorePlus.instance()
        core.run_mda(seq, output="memory")
        return json.dumps(
            {
                "status": "started",
                "uid": str(seq.uid),
                "num_events": sum(1 for _ in seq),
            }
        )

    text = await run_on_main_thread(_run)
    return _text_result(text)


@tool(
    "move_stage",
    "Move the XY stage and/or Z focus. "
    "Provide x_um/y_um for XY, z_um for Z. All in microns.",
    {"x_um": float, "y_um": float, "z_um": float},
)
async def move_stage(args: dict[str, Any]) -> dict[str, Any]:
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

    text = await run_on_main_thread(_move)
    return _text_result(text)


@tool(
    "set_exposure",
    "Set the camera exposure time.",
    {"exposure_ms": float},
)
async def set_exposure(args: dict[str, Any]) -> dict[str, Any]:
    ms = args["exposure_ms"]

    def _set() -> str:
        CMMCorePlus.instance().setExposure(ms)
        return f"Exposure set to {ms} ms."

    text = await run_on_main_thread(_set)
    return _text_result(text)


@tool(
    "set_channel",
    "Set the active channel/config preset.",
    {"channel_name": str},
)
async def set_channel(args: dict[str, Any]) -> dict[str, Any]:
    name = args["channel_name"]

    def _set() -> str:
        CMMCorePlus.instance().setConfig("Channel", name)
        return f"Channel set to '{name}'."

    text = await run_on_main_thread(_set)
    return _text_result(text)


@tool("snap_image", "Snap a single image with the current settings.", {})
async def snap_image(args: dict[str, Any]) -> dict[str, Any]:
    def _snap() -> str:
        CMMCorePlus.instance().snap()
        return "Image snapped."

    text = await run_on_main_thread(_snap)
    return _text_result(text)


@tool("start_live", "Start continuous (live) image acquisition.", {})
async def start_live(args: dict[str, Any]) -> dict[str, Any]:
    def _start() -> str:
        core = CMMCorePlus.instance()
        core.startContinuousSequenceAcquisition(0)
        return "Live mode started."

    text = await run_on_main_thread(_start)
    return _text_result(text)


@tool("stop_live", "Stop continuous (live) image acquisition.", {})
async def stop_live(args: dict[str, Any]) -> dict[str, Any]:
    def _stop() -> str:
        CMMCorePlus.instance().stopSequenceAcquisition()
        return "Live mode stopped."

    text = await run_on_main_thread(_stop)
    return _text_result(text)


@tool(
    "set_property",
    "Set a device property value.",
    {"device": str, "property_name": str, "value": str},
)
async def set_property(args: dict[str, Any]) -> dict[str, Any]:
    dev, prop, val = args["device"], args["property_name"], args["value"]

    def _set() -> str:
        CMMCorePlus.instance().setProperty(dev, prop, val)
        return f"Set {dev}.{prop} = {val}"

    text = await run_on_main_thread(_set)
    return _text_result(text)


@tool("pause_mda", "Pause or resume a running MDA acquisition.", {})
async def pause_mda(args: dict[str, Any]) -> dict[str, Any]:
    def _pause() -> str:
        runner = CMMCorePlus.instance().mda
        runner.set_paused(not runner.is_paused())
        state = "paused" if runner.is_paused() else "resumed"
        return f"MDA {state}."

    text = await run_on_main_thread(_pause)
    return _text_result(text)


@tool("cancel_mda", "Cancel a running MDA acquisition.", {})
async def cancel_mda(args: dict[str, Any]) -> dict[str, Any]:
    def _cancel() -> str:
        CMMCorePlus.instance().mda.cancel()
        return "MDA cancelled."

    text = await run_on_main_thread(_cancel)
    return _text_result(text)


# ---------------------------------------------------------------------------
# Tool collections
# ---------------------------------------------------------------------------

READONLY_TOOLS: list[SdkMcpTool[Any]] = [
    get_microscope_status,
    get_current_position,
    get_available_channels,
    get_loaded_devices,
    get_device_properties,
    get_current_exposure,
    get_pixel_size,
    get_mda_status,
]

WRITE_TOOLS: list[SdkMcpTool[Any]] = [
    create_mda_sequence,
    run_mda_sequence,
    move_stage,
    set_exposure,
    set_channel,
    snap_image,
    start_live,
    stop_live,
    set_property,
    pause_mda,
    cancel_mda,
]

ALL_TOOLS: list[SdkMcpTool[Any]] = READONLY_TOOLS + WRITE_TOOLS


def _wrap_with_logging(t: SdkMcpTool[Any]) -> SdkMcpTool[Any]:
    """Wrap a tool handler with debug logging."""
    original = t.handler

    async def _logged(args: Any) -> dict[str, Any]:
        logger.debug("Tool CALL: %s  args=%s", t.name, args)
        try:
            result = await original(args)
            logger.debug(
                "Tool OK: %s  result_size=%d",
                t.name,
                len(str(result)),
            )
            return result
        except Exception:
            logger.exception("Tool ERROR: %s", t.name)
            raise

    return SdkMcpTool(
        name=t.name,
        description=t.description,
        input_schema=t.input_schema,
        handler=_logged,
    )


def create_microscope_server(*, hardware_enabled: bool = False) -> McpSdkServerConfig:
    """Create an in-process MCP server with the appropriate tool set."""
    tools = ALL_TOOLS if hardware_enabled else READONLY_TOOLS
    wrapped = [_wrap_with_logging(t) for t in tools]
    logger.info(
        "Creating MCP server (hardware=%s) with %d tools: %s",
        hardware_enabled,
        len(wrapped),
        [t.name for t in wrapped],
    )
    return create_sdk_mcp_server("microscope", tools=wrapped)
