from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import mido
from pymmcore_midi._core_connect import connect_knob_to_property
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

    DEVICE_NAME: str = ""  # set dynamically below

    def __init__(self) -> None:
        input_names = mido.get_input_names()
        output_names = mido.get_output_names()

        base = "X-TOUCH MINI"
        in_name = _find_port(input_names, base)
        out_name = _find_port(output_names, base)

        if in_name is None or out_name is None:
            raise OSError(
                f"Could not find X-TOUCH MINI ports. "
                f"Inputs: {input_names}, Outputs: {output_names}"
            )

        self._input: mido.ports.BaseInput = mido.open_input(in_name)
        self._output: mido.ports.BaseOutput = mido.open_output(out_name)
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
    available_inputs = set(mido.get_input_names())
    base_name = XTouchMini.DEVICE_NAME  # "X-TOUCH MINI"

    if base_name in available_inputs:
        return XTouchMini()

    in_name = _find_port(list(available_inputs), base_name)
    if not in_name:
        raise OSError(
            f"No X-TOUCH MINI found. Available inputs: {available_inputs}"
        )
    _XTouchMiniWindows.DEVICE_NAME = in_name
    return _XTouchMiniWindows()


def connect_midi(core: CMMCorePlus) -> Callable[[], None]:
    """Connect an X-TOUCH MINI to core. Returns a disconnect function."""
    device = _get_device()
    disconnecters: list[Callable] = []

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

            def _select(name: str = cfg_name) -> None:
                core.setConfig(channel_group, name)

            device.button[btn_id].pressed.connect(_select)
            disconnecters.append(
                lambda b=btn_id, s=_select: device.button[b].pressed.disconnect(s)
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
        disconnecters.append(
            lambda: core.events.configSet.disconnect(_on_config_set)
        )

    # --- Knob 8: Exposure on camera device ---
    cam = core.getCameraDevice()
    if cam:
        dc = connect_knob_to_property(device.knob[8], core, cam, "Exposure")
        disconnecters.append(dc)

    # --- Button 23 (record): Snap ---
    def safe_snap() -> None:
        if not core.isSequenceRunning():
            core.snap()

    device.button[23].pressed.connect(safe_snap)
    disconnecters.append(lambda: device.button[23].pressed.disconnect(safe_snap))

    # --- Button 22 (play): Toggle live ---
    def toggle_live() -> None:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()
        else:
            core.startContinuousSequenceAcquisition()

    device.button[22].pressed.connect(toggle_live)
    disconnecters.append(lambda: device.button[22].pressed.disconnect(toggle_live))

    # --- Button 21 (stop): Stop live ---
    def stop_live() -> None:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()

    device.button[21].pressed.connect(stop_live)
    disconnecters.append(lambda: device.button[21].pressed.disconnect(stop_live))

    # --- LED feedback: light play button while live is running ---
    play_btn = device.button[22]

    def _live_started() -> None:
        play_btn.press()

    def _live_stopped() -> None:
        play_btn.release()

    core.events.continuousSequenceAcquisitionStarted.connect(_live_started)
    core.events.sequenceAcquisitionStopped.connect(_live_stopped)
    disconnecters.append(
        lambda: core.events.continuousSequenceAcquisitionStarted.disconnect(
            _live_started
        )
    )
    disconnecters.append(
        lambda: core.events.sequenceAcquisitionStopped.disconnect(_live_stopped)
    )

    def disconnect() -> None:
        for d in disconnecters:
            d()

    return disconnect
