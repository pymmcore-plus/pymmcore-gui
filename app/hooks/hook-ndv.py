from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("ndv")

hiddenimports = [
    "ndv.views._qt",
    "ndv.views._qt._app",
    "ndv.views._qt._array_view",
    "ndv.views._qt._main_thread",
    "ndv.views._vispy",
    "ndv.views._vispy._array_canvas",
    "ndv.views._vispy._histogram",
    "ndv.views._vispy._plot_widget",
]
