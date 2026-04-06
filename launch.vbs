Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\QI\Documents\pymmcore-gui"
WshShell.Run "uv run mmgui", 0, False
