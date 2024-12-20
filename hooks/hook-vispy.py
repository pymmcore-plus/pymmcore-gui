from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("vispy")

hiddenimports = [
    "vispy.glsl",
    "vispy.app.backends._pyqt6",
    "vispy.app.backends._test",
]
