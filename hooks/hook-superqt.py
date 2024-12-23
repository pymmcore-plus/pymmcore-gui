from PyInstaller.utils.hooks import collect_data_files, collect_entry_point

datas, hiddenimports = collect_entry_point("superqt.fonticon")
for hiddenimport in hiddenimports:
    datas += collect_data_files(hiddenimport)
