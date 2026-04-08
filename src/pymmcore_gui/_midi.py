from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, ClassVar

import mido  # type: ignore[import-untyped]
from pymmcore_midi._device import Buttons, Knobs, MidiDevice
from pymmcore_midi._xtouch import XTouchMini

if TYPE_CHECKING:
    from collections.abc import Callable

    from pymmcore_plus import CMMCorePlus


class _XTouchMiniWindows(MidiDevice):
    """XTouchMini subclass that handles Windows port naming and broken callbacks.

    On Windows:
    1. mido appends port indices, and input/output may differ
       (e.g. 'X-TOUCH MINI 0' for input, 'X-TOUCH MINI 1' for output).
    2. rtmidi callbacks don't fire, so we poll in a background thread.
    """

    DEVICE_NAME: ClassVar[str] = ""  # set dynamically below

    def __init__(self) -> None:
        input_names: list[str] = mido.get_input_names()  # pyright: ignore[reportAttributeAccessIssue]
        output_names: list[str] = mido.get_output_names()  # pyright: ignore[reportAttributeAccessIssue]

        base = "X-TOUCH MINI"
        in_name = _find_port(input_names, base)
        out_name = _find_port(output_names, base)

        if in_name is None or out_name is None:
            raise OSError(
                f"Could not find X-TOUCH MINI ports. "
                f"Inputs: {input_names}, Outputs: {output_names}"
            )

        self._input: Any = mido.open_input(in_name)  # pyright: ignore[reportAttributeAccessIssue]
        self._output: Any = mido.open_output(out_name)  # pyright: ignore[reportAttributeAccessIssue]
        self._input.callback = None  # broken on Windows rtmidi

        self.device_name = in_name
        self._buttons = Buttons(range(48), self._output)
        self._knobs = Knobs(range(1, 19), self._output)
        self._debug = False

        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="midi-poll"
        )
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        for msg in self._input:
            self._on_msg(msg)


def _find_port(names: list[str], base: str) -> str | None:
    if base in names:
        return base
    for name in names:
        if name.startswith(base):
            return name
    return None


def _get_device() -> MidiDevice:
    """Create an X-TOUCH MINI device, using Windows workaround if needed."""
    available_inputs: set[str] = set(mido.get_input_names())  # pyright: ignore[reportAttributeAccessIssue]
    base_name: str = XTouchMini.DEVICE_NAME  # "X-TOUCH MINI"

    if base_name in available_inputs:
        return XTouchMini()

    in_name = _find_port(list(available_inputs), base_name)
    if not in_name:
        raise OSError(f"No X-TOUCH MINI found. Available inputs: {available_inputs}")
    _XTouchMiniWindows.DEVICE_NAME = in_name
    return _XTouchMiniWindows()


def connect_midi(core: CMMCorePlus) -> Callable[[], None]:
    """Connect an X-TOUCH MINI to core. Returns a disconnect function."""
    device = _get_device()
    disconnects: list[Callable[[], None]] = []

    # --- Buttons 8-11: Channel config group (BF, DAPI, FITC, TRITC) ---
    channel_group = core.getChannelGroup()
    config_buttons = {8: "BF", 9: "DAPI", 10: "FITC", 11: "TRITC"}

    def _update_channel_leds(current: str) -> None:
        for btn_id, cfg_name in config_buttons.items():
            if cfg_name == current:
                device.button[btn_id].press()
            else:
                device.button[btn_id].release()

    if channel_group:
        for btn_id, cfg_name in config_buttons.items():
            _connect_config_button(
                device, core, channel_group, btn_id, cfg_name, disconnects
            )

        # Set initial LED state
        try:
            _update_channel_leds(core.getCurrentConfig(channel_group))
        except Exception:
            pass

        def _on_config_set(group: str, config: str) -> None:
            if group == channel_group:
                _update_channel_leds(config)

        core.events.configSet.connect(_on_config_set)
        disconnects.append(lambda: core.events.configSet.disconnect(_on_config_set))

    # --- Knobs 1-4: LED intensity controls (throttled) ---
    led_knobs = {
        1: ("LED:L:37:1", "LED Intensity(%)"),  # LED BF
        2: ("LED:L:37:2", "LED Intensity(%)"),  # LED 405
        3: ("LED:L:37:3", "LED Intensity(%)"),  # LED 491
        4: ("LED:L:37:4", "LED Intensity(%)"),  # LED 561
    }
    for knob_id, (dev_label, prop_name) in led_knobs.items():
        try:
            dc = _connect_knob_throttled(
                device.knob[knob_id], core, dev_label, prop_name
            )
            disconnects.append(dc)
        except Exception:
            pass

    # --- Knob 8: Exposure on camera device (1ms - 1500ms) ---
    cam = core.getCameraDevice()
    if cam:
        dc = _connect_knob_throttled(
            device.knob[8],
            core,
            cam,
            "Exposure",
            prop_min=1.0,
            prop_max=500.0,
        )
        disconnects.append(dc)

    # --- Button 23 (record): Snap ---
    def safe_snap() -> None:
        if not core.isSequenceRunning():
            core.snap()

    device.button[23].pressed.connect(safe_snap)
    disconnects.append(lambda: device.button[23].pressed.disconnect(safe_snap))

    # --- Button 22 (play): Toggle live ---
    def toggle_live() -> None:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()
        else:
            core.startContinuousSequenceAcquisition()

    device.button[22].pressed.connect(toggle_live)
    disconnects.append(lambda: device.button[22].pressed.disconnect(toggle_live))

    # --- Button 21 (stop): Stop live ---
    def stop_live() -> None:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()

    device.button[21].pressed.connect(stop_live)
    disconnects.append(lambda: device.button[21].pressed.disconnect(stop_live))

    # --- LED feedback: light play button while live is running ---
    play_btn = device.button[22]

    def _live_started() -> None:
        play_btn.press()

    def _live_stopped() -> None:
        play_btn.release()

    core.events.continuousSequenceAcquisitionStarted.connect(_live_started)
    core.events.sequenceAcquisitionStopped.connect(_live_stopped)
    disconnects.append(
        lambda: core.events.continuousSequenceAcquisitionStarted.disconnect(
            _live_started
        )
    )
    disconnects.append(
        lambda: core.events.sequenceAcquisitionStopped.disconnect(_live_stopped)
    )

    def disconnect() -> None:
        for d in disconnects:
            d()

    return disconnect


def _connect_knob_throttled(
    knob: Any,
    core: CMMCorePlus,
    device_label: str,
    property_name: str,
    interval_ms: int = 50,
    prop_min: float | None = None,
    prop_max: float | None = None,
) -> Callable[[], None]:
    """Like connect_knob_to_property, but throttles setProperty calls.

    Only the most recent knob value is sent to hardware, at most once per
    `interval_ms`. Intermediate values are dropped so the knob stays responsive.
    A trailing timer ensures the final value is always applied.

    If prop_min/prop_max are provided, they override the device property limits.
    """
    import time
    import warnings

    if prop_min is not None and prop_max is not None:
        prop_lower = prop_min
        prop_range = prop_max - prop_min
    elif core.hasPropertyLimits(device_label, property_name):
        prop_lower = core.getPropertyLowerLimit(device_label, property_name)
        prop_range = (
            core.getPropertyUpperLimit(device_label, property_name) - prop_lower
        )
    else:
        warnings.warn(
            f"Property {device_label}.{property_name} has no limits and "
            "cannot be connected to a MIDI knob",
            stacklevel=2,
        )
        return lambda: None
    min_interval = interval_ms / 1000.0

    def knob2value(value: float) -> float:
        v = value / 127.0 * prop_range + prop_lower
        return float(round(v))

    def value2knob(value: float | str) -> int:
        out = (float(value) - prop_lower) / prop_range * 127.0
        return min(max(int(out), 0), 127)

    # Set knob to current property value
    knob.set_value(value2knob(float(core.getProperty(device_label, property_name))))

    _last_set: list[float] = [0.0]
    _trailing: list[threading.Timer | None] = [None]

    def _set_property(value: float) -> None:
        _last_set[0] = time.monotonic()
        core.setProperty(device_label, property_name, knob2value(value))

    def _on_knob_changed(value: float) -> None:
        # Cancel any pending trailing call
        if _trailing[0] is not None:
            _trailing[0].cancel()
            _trailing[0] = None

        now = time.monotonic()
        elapsed = now - _last_set[0]

        if elapsed >= min_interval:
            _set_property(value)
        else:
            # Schedule a trailing call so the final value is always applied
            delay = min_interval - elapsed
            t = threading.Timer(delay, _set_property, args=(value,))
            t.daemon = True
            t.start()
            _trailing[0] = t

    knob.changed.connect(_on_knob_changed)

    # Bidirectional: update knob when property changes externally
    def _update_knob_value(dev: str, prop: str, value: str) -> None:
        if dev == device_label and prop == property_name:
            knob.set_value(value2knob(value))

    core.events.propertyChanged.connect(_update_knob_value)

    def disconnect() -> None:
        if _trailing[0] is not None:
            _trailing[0].cancel()
        knob.changed.disconnect(_on_knob_changed)
        core.events.propertyChanged.disconnect(_update_knob_value)

    return disconnect


def _connect_config_button(
    device: MidiDevice,
    core: CMMCorePlus,
    channel_group: str,
    btn_id: int,
    cfg_name: str,
    disconnects: list[Callable[[], None]],
) -> None:
    def _select() -> None:
        core.setConfig(channel_group, cfg_name)

    device.button[btn_id].pressed.connect(_select)
    disconnects.append(lambda: device.button[btn_id].pressed.disconnect(_select))
