@tool
extends Control

## A self-contained editor screen for Godot projects.  It intentionally uses
## Godot's native CodeEdit and GDScriptSyntaxHighlighter, so no external app,
## executable, or syntax-definition download is needed.

signal separate_window_requested

var allow_separate_window := true
var file_tree: Tree
var code_editor: CodeEdit
var document_label: Label
var status_label: Label
var current_path := ""
var is_dirty := false
var is_loading := false


func _ready() -> void:
	name = "GDScriptStudio"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	_build_interface()
	_refresh_file_tree()


func _build_interface() -> void:
	var layout := VBoxContainer.new()
	layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layout.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(layout)

	var toolbar := HBoxContainer.new()
	layout.add_child(toolbar)

	var refresh_button := Button.new()
	refresh_button.text = "Refresh Files"
	refresh_button.tooltip_text = "Refresh the project script list"
	refresh_button.pressed.connect(_refresh_file_tree)
	toolbar.add_child(refresh_button)

	var save_button := Button.new()
	save_button.text = "Save"
	save_button.tooltip_text = "Save the current script (Ctrl+S)"
	save_button.pressed.connect(_save_current_script)
	toolbar.add_child(save_button)

	if allow_separate_window:
		var window_button := Button.new()
		window_button.text = "Open Separate Window"
		window_button.tooltip_text = "Open GDScript Studio in a native window for another monitor"
		window_button.pressed.connect(separate_window_requested.emit)
		toolbar.add_child(window_button)

	document_label = Label.new()
	document_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	document_label.text = "Select a GDScript file from the project"
	toolbar.add_child(document_label)

	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(split)

	file_tree = Tree.new()
	file_tree.custom_minimum_size.x = 230.0
	file_tree.hide_root = true
	file_tree.item_activated.connect(_open_selected_script)
	split.add_child(file_tree)

	code_editor = CodeEdit.new()
	code_editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	code_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	code_editor.syntax_highlighter = GDScriptSyntaxHighlighter.new()
	code_editor.gutters_draw_line_numbers = true
	code_editor.gutters_draw_fold_gutter = true
	code_editor.line_folding = true
	code_editor.indent_use_spaces = false
	code_editor.indent_size = 4
	code_editor.indent_automatic = true
	code_editor.auto_brace_completion_enabled = true
	code_editor.auto_brace_completion_highlight_matching = true
	code_editor.text_changed.connect(_mark_dirty)
	split.add_child(code_editor)

	status_label = Label.new()
	status_label.text = "Ready"
	layout.add_child(status_label)


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.ctrl_pressed and event.keycode == KEY_S:
			_save_current_script()
			get_viewport().set_input_as_handled()


func _refresh_file_tree() -> void:
	file_tree.clear()
	var root := file_tree.create_item()
	root.set_text(0, "res://")
	root.set_metadata(0, "res://")
	_add_directory(root, "res://")
	root.collapsed = false
	status_label.text = "Project files refreshed"


func _add_directory(parent: TreeItem, path: String) -> void:
	var directory := DirAccess.open(path)
	if directory == null:
		return

	var folders: Array[String] = []
	var scripts: Array[String] = []
	directory.list_dir_begin()
	var entry := directory.get_next()
	while not entry.is_empty():
		if not entry.begins_with("."):
			if directory.current_is_dir():
				folders.append(entry)
			elif entry.get_extension().to_lower() == "gd":
				scripts.append(entry)
		entry = directory.get_next()
	directory.list_dir_end()

	folders.sort()
	scripts.sort()
	for folder in folders:
		var folder_path := path.path_join(folder)
		var folder_item := file_tree.create_item(parent)
		folder_item.set_text(0, folder)
		folder_item.set_metadata(0, folder_path)
		_add_directory(folder_item, folder_path)
	for script in scripts:
		var script_item := file_tree.create_item(parent)
		script_item.set_text(0, script)
		script_item.set_metadata(0, path.path_join(script))


func _open_selected_script() -> void:
	var selected := file_tree.get_selected()
	if selected == null:
		return
	var path := str(selected.get_metadata(0))
	if path.ends_with(".gd"):
		_open_script(path)


func _open_script(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		status_label.text = "Could not open %s" % path
		return
	is_loading = true
	code_editor.text = file.get_as_text()
	file.close()
	is_loading = false
	current_path = path
	is_dirty = false
	document_label.text = path
	status_label.text = "Opened %s" % path


func _mark_dirty() -> void:
	if is_loading or current_path.is_empty():
		return
	is_dirty = true
	document_label.text = "%s *" % current_path


func _save_current_script() -> void:
	if current_path.is_empty():
		status_label.text = "Choose a script from the project files first"
		return
	var file := FileAccess.open(current_path, FileAccess.WRITE)
	if file == null:
		status_label.text = "Could not save %s" % current_path
		return
	file.store_string(code_editor.text)
	file.close()
	is_dirty = false
	document_label.text = current_path
	status_label.text = "Synced with Godot: %s" % current_path
	EditorInterface.get_resource_filesystem().scan()
	EditorInterface.get_script_editor().reload_open_files()
