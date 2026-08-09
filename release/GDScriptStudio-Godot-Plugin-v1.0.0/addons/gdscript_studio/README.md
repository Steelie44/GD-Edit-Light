# GDScript Studio

GDScript Studio is a self-contained Godot 4 editor plugin. It adds a **GDScript
Studio** main-screen tab with a project script tree, GDScript syntax highlighting,
and save support. It uses Godot's built-in editor controls, so it does not launch
or require a separate executable, Python installation, or downloaded resources.

## Install

1. Extract this archive into the root of a Godot project. It will create
   `res://addons/gdscript_studio/`.
2. Open the project, then enable **GDScript Studio** in
   **Project > Project Settings > Plugins**.
3. Select the new **GDScript Studio** tab beside Godot's other main editor tabs.
4. Double-click a `.gd` file in the left project tree, edit it, and press
   **Ctrl+S** or **Save**.

Use **Open Separate Window** (or **Tools > Open GDScript Studio in Separate
Window**) to put the editor in a movable native OS window, such as on a second
monitor. It remains part of the Godot editor session, but writes to the exact
same project files and refreshes Godot when you save.

Edits stay inside GDScript Studio until you explicitly press **Ctrl+S** or
**Save**. Saving writes the selected project script, rescans project resources,
and reloads Godot's open scripts. This avoids parser errors while you are in the
middle of an edit. This plugin is intended for Godot 4.x.
