@tool
extends EditorPlugin

const StudioPanel = preload("res://addons/gdscript_studio/studio_panel.gd")
const PLUGIN_ICON = preload("res://addons/gdscript_studio/icon.svg")

var studio_panel: Control
var separate_window: Window


func _enter_tree() -> void:
	studio_panel = StudioPanel.new()
	studio_panel.separate_window_requested.connect(_open_separate_window)
	EditorInterface.get_editor_main_screen().add_child(studio_panel)
	_make_visible(false)
	add_tool_menu_item("Open GDScript Studio in Separate Window", _open_separate_window)


func _exit_tree() -> void:
	remove_tool_menu_item("Open GDScript Studio in Separate Window")
	if is_instance_valid(separate_window):
		separate_window.queue_free()
	if is_instance_valid(studio_panel):
		studio_panel.queue_free()


func _has_main_screen() -> bool:
	return true


func _make_visible(visible: bool) -> void:
	if is_instance_valid(studio_panel):
		studio_panel.visible = visible


func _get_plugin_name() -> String:
	return "GDScript Studio"


func _get_plugin_icon() -> Texture2D:
	return PLUGIN_ICON


func _open_separate_window() -> void:
	if is_instance_valid(separate_window):
		separate_window.show()
		separate_window.grab_focus()
		return

	separate_window = Window.new()
	# Window defaults to visible. Configure native-window behavior before it is
	# allowed to enter the editor's window tree.
	separate_window.hide()
	separate_window.title = "GDScript Studio"
	separate_window.force_native = true
	separate_window.size = Vector2i(1200, 800)
	separate_window.min_size = Vector2i(700, 450)
	separate_window.close_requested.connect(separate_window.hide)
	EditorInterface.get_base_control().add_child(separate_window)

	var window_panel := StudioPanel.new()
	window_panel.allow_separate_window = false
	separate_window.add_child(window_panel)
	separate_window.show()
	separate_window.grab_focus()
