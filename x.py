from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QWidget
from useq import MDASequence

from pymmcore_gui._ndv_viewers import NDVViewersManager

app = QApplication([])
wdg = QWidget()
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration("/Users/fdrgsp/Desktop/test_config.cfg")
mng = NDVViewersManager(wdg, mmc)


def _show(ndv_viewer, sequence):
    print("Showing viewer for sequence:", sequence)
    ndv_viewer.show()


mng.mdaViewerCreated.connect(_show)


sequence = MDASequence(
    axis_order="tpcz",
    channels=["DAPI", {"config": "FITC", "exposure": 1}],
    stage_positions=[(0, 0), (1, 1)],
    time_plan={"interval": 1, "loops": 2},
    z_plan={"range": 4, "step": 0.5},
)
mmc.run_mda(sequence, output="example_from_gui.ome.zarr")

app.exec()
