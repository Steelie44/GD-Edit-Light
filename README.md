# GDScript Studio

A compact desktop editor for Godot GDScript projects. It includes a project file tree, tabbed files, GDScript syntax highlighting, saved light/dark themes, a theme editor, and standard new/open/save workflows.

## Run

From PowerShell in this directory:

```powershell
.\venv\Scripts\python.exe .\gdscript_editor.py
```

The editor starts with this folder as the project root. Double-click a file in the left panel to open it. `Ctrl+S` saves and `Ctrl+Shift+S` saves under a new name. Use **File → Open Project Folder** to switch projects. Theme, font, and indentation controls sit on the menu bar; use **Import** to add a local font file for the editor. Choose tabs or 2/4/8 spaces as the editor indentation style.

## Requirements

The provided virtual environment already contains PyQt6 and QScintilla. If QScintilla is unavailable, the editor remains usable with the built-in plain-text widget.

## Godot plugin

Copy the `godot_addon/gdscript_studio` folder into your Godot project's `addons/gdscript_studio` folder. Enable **GDScript Studio** from **Project → Project Settings → Plugins**. In **Editor → Editor Settings**, set `gdscript_studio/executable` to `GDScriptStudio.exe`. To run the Python source instead, set it to this project's `venv/Scripts/python.exe` and set `gdscript_studio/editor_script` to this project's `gdscript_editor.py`.

Use **Tools → Open Current Script in GDScript Studio** in Godot to open the selected script. Both programs edit the same file. Enable **Text Editor → Behavior → Auto Reload Scripts on External Change** in Godot to reload saves made from GDScript Studio; GDScript Studio itself now watches opened files and reloads non-modified documents after saves made in Godot.

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** license.

- **You are free to:** Share, copy, redistribute, adapt, and build upon this material.
- **Under the following terms:**
  - **Attribution:** You must give appropriate credit, provide a link to the license, and indicate if changes were made.
  - **NonCommercial:** You may not use the material for commercial purposes or financial gain.

For the full legal code, visit the [Creative Commons CC BY-NC 4.0 License Page](https://creativecommons.org/licenses/by-nc/4.0/legalcode).