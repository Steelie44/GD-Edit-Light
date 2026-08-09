# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportConstantRedefinition=false, reportGeneralTypeIssues=false, reportIncompatibleMethodOverride=false, reportMissingParameterType=false, reportOptionalMemberAccess=false, reportPossiblyUnboundVariable=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUntypedBaseClass=false
"""GDScript Studio: a small, desktop-first editor for Godot projects.

QScintilla exposes limited static type information, so this file suppresses only
the Pylance diagnostics that stem from that third-party binding's dynamic API.
Runtime validation remains covered by the application's smoke tests.
"""

from __future__ import annotations

import json
import re
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QFileSystemWatcher, QModelIndex, QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFileSystemModel, QFont, QFontDatabase, QKeySequence, QPalette
from PyQt6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFontComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QStatusBar, QTabWidget, QLineEdit,
    QToolBar, QToolButton, QTreeView, QVBoxLayout, QWidget, QSpinBox, QDockWidget, QListWidget,
)

try:
    from PyQt6.Qsci import QsciAPIs, QsciLexerCustom, QsciScintilla
    QSCINTILLA_AVAILABLE = True
except ImportError:
    QSCINTILLA_AVAILABLE = False


MAX_FILE_SIZE = 2 * 1024 * 1024
DEFAULT_FONT_FAMILY = "Cascadia Code"
DEFAULT_FONT_SIZE = 12

THEMES: dict[str, dict[str, str]] = {
    "Dark": {
        "window": "#1e1e1e", "panel": "#252526", "editor": "#1e1e1e",
        "text": "#d4d4d4", "gutter": "#252526", "accent": "#569cd6",
        "keyword": "#c586c0", "string": "#ce9178", "comment": "#6a9955",
        "number": "#b5cea8", "builtin": "#4ec9b0", "annotation": "#dcdcaa",
        "constant": "#569cd6", "type": "#4ec9b0", "function": "#dcdcaa",
        "member": "#9cdcfe", "class": "#4ec9b0",
    },
    "Light": {
        "window": "#f7f7f7", "panel": "#efefef", "editor": "#ffffff",
        "text": "#000000", "gutter": "#f0f0f0", "accent": "#0067c0",
        "keyword": "#a31515", "string": "#a31515", "comment": "#008000",
        "number": "#098658", "builtin": "#267f99", "annotation": "#795e26",
        "constant": "#0000ff", "type": "#267f99", "function": "#795e26",
        "member": "#001080", "class": "#267f99",
    },
}


if QSCINTILLA_AVAILABLE:
    class GDScriptLexer(QsciLexerCustom):
        """A deliberately small lexer for the GDScript language."""

        DEFAULT, KEYWORD, STRING, COMMENT, NUMBER, BUILTIN, ANNOTATION, CONSTANT, TYPE, FUNCTION, MEMBER, CLASS = range(12)
        keyword_set = {
            "as", "assert", "await", "break", "breakpoint", "class", "class_name",
            "const", "continue", "elif", "else", "enum", "extends", "for", "func",
            "if", "in", "is", "match", "pass", "preload", "return", "self", "signal",
            "static", "super", "var", "void", "when", "while", "yield",
        }
        operator_set = {"and", "not", "or"}
        constant_set = {"false", "true", "null", "PI", "TAU", "INF", "NAN"}
        type_set = {
            "Variant", "bool", "int", "float", "String", "StringName", "NodePath", "RID",
            "Callable", "Signal", "Dictionary", "Array", "PackedByteArray", "PackedInt32Array",
            "PackedInt64Array", "PackedFloat32Array", "PackedFloat64Array", "PackedStringArray",
            "PackedVector2Array", "PackedVector3Array", "PackedVector4Array", "PackedColorArray",
            "Vector2", "Vector2i", "Rect2", "Rect2i", "Vector3", "Vector3i", "Transform2D",
            "Vector4", "Vector4i", "Plane", "Quaternion", "AABB", "Basis", "Transform3D",
            "Projection", "Color", "Object",
        }
        builtin_set = {
            "abs", "assert", "ceil", "clamp", "deg_to_rad", "floor", "is_instance_valid",
            "lerp", "load", "max", "min", "move_toward", "print", "prints", "printt",
            "push_error", "push_warning", "rad_to_deg", "range", "round", "snapped", "str",
            "typeof", "weakref",
        }
        annotation_set = {
            "@abstract", "@export", "@export_category", "@export_color_no_alpha", "@export_custom",
            "@export_dir", "@export_enum", "@export_exp_easing", "@export_file", "@export_flags",
            "@export_flags_2d_navigation", "@export_flags_2d_physics", "@export_flags_2d_render",
            "@export_flags_3d_navigation", "@export_flags_3d_physics", "@export_flags_3d_render",
            "@export_global_dir", "@export_global_file", "@export_group", "@export_multiline",
            "@export_node_path", "@export_placeholder", "@export_range", "@export_storage",
            "@export_subgroup", "@export_tool_button", "@icon", "@onready", "@rpc",
            "@static_unload", "@tool", "@warning_ignore", "@warning_ignore_restore", "@warning_ignore_start",
        }
        token_pattern = re.compile(
            r"(?P<comment>\#.*$)|(?P<annotation>@[A-Za-z_]\w*)|"
            r"(?P<string>(?:[rR])?(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"))|"
            r"(?P<number>\b(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|\d[\d_]*(?:\.\d[\d_]*|(?:[eE][+-]?\d[\d_]*)?)?)\b)|"
            r"(?P<word>\b[A-Za-z_]\w*\b)", re.MULTILINE
        )

        def language(self) -> str:
            return "GDScript"

        def description(self, style: int) -> str:
            return {
                self.DEFAULT: "Default", self.KEYWORD: "Keyword", self.STRING: "String",
                self.COMMENT: "Comment", self.NUMBER: "Number", self.BUILTIN: "Built-in",
                self.ANNOTATION: "Annotation", self.CONSTANT: "Constant", self.TYPE: "Built-in type",
                self.FUNCTION: "Function", self.MEMBER: "Member", self.CLASS: "Class name",
            }.get(style, "Default")

        def styleText(self, start: int, end: int) -> None:
            editor = self.parent()
            if editor is None or not hasattr(editor, "text"):
                return
            source = editor.text().encode("utf-8")
            chunk = source[start:end].decode("utf-8", errors="ignore")
            self.startStyling(start)
            cursor = 0

            def paint(value: str, style: int) -> None:
                self.setStyling(len(value.encode("utf-8")), style)

            for match in self.token_pattern.finditer(chunk):
                paint(chunk[cursor:match.start()], self.DEFAULT)
                value = match.group(0)
                if match.lastgroup == "comment":
                    style = self.COMMENT
                elif match.lastgroup == "annotation":
                    style = self.ANNOTATION if value in self.annotation_set else self.DEFAULT
                elif match.lastgroup == "string":
                    style = self.STRING
                elif match.lastgroup == "number":
                    style = self.NUMBER
                elif value in self.keyword_set or value in self.operator_set:
                    style = self.KEYWORD
                elif value in self.constant_set:
                    style = self.CONSTANT
                elif value in self.type_set:
                    style = self.TYPE
                elif value in self.builtin_set:
                    style = self.BUILTIN
                elif chunk[:match.start()].rstrip().endswith("."):
                    style = self.MEMBER
                elif chunk[match.end():].lstrip().startswith("("):
                    style = self.FUNCTION
                elif value[:1].isupper():
                    style = self.CLASS
                else:
                    style = self.DEFAULT
                paint(value, style)
                cursor = match.end()
            paint(chunk[cursor:], self.DEFAULT)


class ThemeEditor(QDialog):
    """Edits the active palette without introducing a heavyweight preferences UI."""

    labels = {
        "window": "Application background", "panel": "Panels", "editor": "Editor background",
        "text": "Editor text", "gutter": "Line-number gutter", "accent": "Accent",
        "keyword": "Keywords", "string": "Strings", "comment": "Comments",
        "number": "Numbers", "builtin": "Built-ins", "annotation": "Annotations",
        "constant": "Constants", "type": "Built-in types", "function": "Functions",
        "member": "Members", "class": "Class names",
    }

    def __init__(self, colors: dict[str, str], parent: QWidget, dialog_style: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Theme editor")
        self.setStyleSheet(dialog_style)
        self.colors = colors.copy()
        self.buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for key, label in self.labels.items():
            button = QPushButton(self.colors[key])
            button.clicked.connect(lambda _, color_key=key: self.pick_color(color_key))
            self.buttons[key] = button
            self._refresh_button(key)
            form.addRow(label, button)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def pick_color(self, key: str) -> None:
        dialog = QColorDialog(QColor(self.colors[key]), self)
        dialog.setWindowTitle(f"Choose {self.labels[key].lower()}")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec():
            color = dialog.currentColor()
            self.colors[key] = color.name()
            self._refresh_button(key)

    def _refresh_button(self, key: str) -> None:
        color = QColor(self.colors[key])
        text_color = "#000000" if color.lightness() > 140 else "#ffffff"
        self.buttons[key].setText(self.colors[key])
        self.buttons[key].setStyleSheet(f"background: {self.colors[key]}; color: {text_color}; padding: 4px;")


class CodeEditor(QsciScintilla if QSCINTILLA_AVAILABLE else QPlainTextEdit):
    def __init__(self, colors: dict[str, str], font_family: str, font_size: int, indent_mode: str, indent_width: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lexer: Optional[object] = None
        if QSCINTILLA_AVAILABLE:
            self.setUtf8(True)
            self.setMarginLineNumbers(0, True)
            self.setMarginWidth(0, "00000")
            self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
            self.setMarginWidth(1, 14)
            self.setMarginSensitivity(1, True)
            self.markerDefine(QsciScintilla.MarkerSymbol.Circle, 1)
            self.marginClicked.connect(self.toggle_breakpoint)
            self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
            self.setAutoIndent(True)
            self.setIndentationsUseTabs(False)
            self.setTabWidth(4)
            self.lexer = GDScriptLexer(self)
            self.setLexer(self.lexer)
            self.api = QsciAPIs(self.lexer)
            for word in sorted(GDScriptLexer.keyword_set | GDScriptLexer.type_set | GDScriptLexer.builtin_set):
                self.api.add(word)
            self.api.prepare()
            self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
            self.setAutoCompletionThreshold(2)
        else:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.apply_font(font_family, font_size)
        self.apply_indentation(indent_mode, indent_width)
        self.apply_theme(colors)

    def text_value(self) -> str:
        return self.text() if QSCINTILLA_AVAILABLE else self.toPlainText()

    def set_text_value(self, text: str) -> None:
        if QSCINTILLA_AVAILABLE:
            self.setText(text)
        else:
            self.setPlainText(text)
        self.setModified(False)

    def apply_theme(self, colors: dict[str, str]) -> None:
        if QSCINTILLA_AVAILABLE:
            self.setPaper(QColor(colors["editor"]))
            self.setColor(QColor(colors["text"]))
            self.setCaretLineVisible(True)
            self.setCaretLineBackgroundColor(QColor(colors["panel"]))
            self.setMarginsBackgroundColor(QColor(colors["gutter"]))
            self.setMarginsForegroundColor(QColor(colors["text"]))
            assert isinstance(self.lexer, GDScriptLexer)
            for style, key in ((GDScriptLexer.DEFAULT, "text"), (GDScriptLexer.KEYWORD, "keyword"),
                               (GDScriptLexer.STRING, "string"), (GDScriptLexer.COMMENT, "comment"),
                               (GDScriptLexer.NUMBER, "number"), (GDScriptLexer.BUILTIN, "builtin"),
                               (GDScriptLexer.ANNOTATION, "annotation"), (GDScriptLexer.CONSTANT, "constant"),
                               (GDScriptLexer.TYPE, "type"), (GDScriptLexer.FUNCTION, "function"),
                               (GDScriptLexer.MEMBER, "member"), (GDScriptLexer.CLASS, "class")):
                self.lexer.setColor(QColor(colors[key]), style)
            self.lexer.setPaper(QColor(colors["editor"]))
            self.recolor()
        else:
            self.setStyleSheet(f"background: {colors['editor']}; color: {colors['text']}; border: 0;")

    def apply_font(self, family: str, size: int) -> None:
        font = QFont(family, size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        if QSCINTILLA_AVAILABLE:
            self.setMarginsFont(font)
            assert isinstance(self.lexer, GDScriptLexer)
            self.lexer.setDefaultFont(font)
            for style in range(12):
                self.lexer.setFont(font, style)
            self.recolor()

    def apply_indentation(self, mode: str, width: int) -> None:
        use_tabs = mode == "Tabs"
        if QSCINTILLA_AVAILABLE:
            self.setIndentationsUseTabs(use_tabs)
            self.setIndentationWidth(width)
            self.setTabWidth(width)
        else:
            self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * width)

    def toggle_breakpoint(self, margin: int, line: int, _: int) -> None:
        if margin != 1:
            return
        if self.markersAtLine(line) & (1 << 1):
            self.markerDelete(line, 1)
        else:
            self.markerAdd(line, 1)


class Document(QWidget):
    def __init__(self, colors: dict[str, str], font_family: str, font_size: int, indent_mode: str, indent_width: int, path: Optional[Path] = None) -> None:
        super().__init__()
        self.path = path
        self.editor = CodeEditor(colors, font_family, font_size, indent_mode, indent_width, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

    @property
    def name(self) -> str:
        return self.path.name if self.path else "Untitled"


class EditorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GD Edit Light")
        self.settings = QSettings("GDScriptStudio", "GDScriptStudio")
        self.imported_font_paths = self._restore_imported_fonts()
        self.font_family = str(self.settings.value("font/family", DEFAULT_FONT_FAMILY))
        self.font_size = max(6, min(72, int(self.settings.value("font/size", DEFAULT_FONT_SIZE))))
        self.indent_mode = str(self.settings.value("indent/mode", "Spaces"))
        self.indent_width = int(self.settings.value("indent/width", 4))
        if self.indent_mode not in {"Tabs", "Spaces"} or self.indent_width not in {2, 4, 8}:
            self.indent_mode, self.indent_width = "Spaces", 4
        # A distributable editor must never expose its own installation or source folder
        # as the user's project. Start each launch with a clean, disposable workspace.
        self._empty_workspace = TemporaryDirectory(prefix="GDScriptStudio-")
        self.project_dir = Path(self._empty_workspace.name)
        self.theme_name = str(self.settings.value("theme", "Dark"))
        self.palettes = self._load_palettes()
        self.setMinimumSize(1180, 500)
        self.resize(1280, 820)
        self._create_actions()
        self._create_layout()
        self._create_menu_and_toolbar()
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self.reload_external_file)
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.apply_theme()
        self.new_file()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30_000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()

    def _load_palettes(self) -> dict[str, dict[str, str]]:
        palettes = {name: colors.copy() for name, colors in THEMES.items()}
        for name in THEMES:
            saved = self.settings.value(f"palette/{name}", "")
            if saved:
                try:
                    palettes[name].update(json.loads(str(saved)))
                except (TypeError, json.JSONDecodeError):
                    pass
        return palettes

    def _restore_imported_fonts(self) -> list[str]:
        saved = self.settings.value("font/imported_paths", [])
        paths = [str(path) for path in (saved if isinstance(saved, list) else [saved]) if str(path)]
        restored: list[str] = []
        for path in paths:
            if Path(path).is_file() and QFontDatabase.addApplicationFont(path) != -1:
                restored.append(path)
        return restored

    @property
    def colors(self) -> dict[str, str]:
        return self.palettes[self.theme_name]

    def _create_actions(self) -> None:
        self.new_action = QAction("New", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_file)
        self.open_action = QAction("Open…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_dialog)
        self.open_project_action = QAction("Open Project Folder…", self, triggered=self.choose_project_folder)
        self.save_action = QAction("Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_current)
        self.save_as_action = QAction("Save As…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=self.save_current_as)
        self.find_action = QAction("Find…", self, shortcut=QKeySequence.StandardKey.Find, triggered=self.find_in_document)
        self.replace_action = QAction("Find and Replace", self, shortcut=QKeySequence("Ctrl+H"), triggered=self.find_in_document)
        self.goto_action = QAction("Go to Line…", self, shortcut=QKeySequence("Ctrl+G"), triggered=self.go_to_line)
        self.shortcuts_action = QAction("Keyboard Shortcuts", self, triggered=self.show_shortcuts)
        self.theme_editor_action = QAction("Edit Current Theme…", self, triggered=self.edit_theme)
        self.import_font_action = QAction("Import Font…", self, triggered=self.import_font)
        self.split_action = QAction("Split Tab", self, triggered=self.split_current_tab)
        self.close_split_action = QAction("Close Split", self, triggered=self.close_split)
        self.zoom_in_action = QAction("Zoom In", self, shortcut=QKeySequence.StandardKey.ZoomIn, triggered=lambda: self.zoom(1))
        self.zoom_out_action = QAction("Zoom Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, triggered=lambda: self.zoom(-1))
        self.snippet_actions = [QAction(label, self, triggered=lambda _, text=snippet: self.insert_snippet(text)) for label, snippet in (
            ("Ready function", "func _ready() -> void:\n\t"), ("Process function", "func _process(delta: float) -> void:\n\t"),
            ("Export variable", "@export var value: float = 0.0"), ("Signal", "signal value_changed(value: float)"),
        )]

    def _create_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.model = QFileSystemModel(self)
        self.model.setRootPath(str(self.project_dir))
        self.tree = QTreeView(splitter)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(self.project_dir)))
        self.tree.setHeaderHidden(True)
        self.tree.setExpandsOnDoubleClick(True)
        for column in range(1, 4):
            self.tree.setColumnHidden(column, True)
        self.tree.doubleClicked.connect(self.open_tree_item)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal, splitter)
        self.tabs = QTabWidget(self.editor_splitter)
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_status)
        self.tabs.currentChanged.connect(lambda _: self.refresh_outline())
        self.outline = QListWidget(self)
        self.outline.itemActivated.connect(self.go_to_outline_item)
        self.outline_dock = QDockWidget("Outline", self)
        self.outline_dock.setWidget(self.outline)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.outline_dock)
        self.split_document: Optional[Document] = None
        self.split_source: Optional[Document] = None
        self._syncing_split = False
        splitter.setSizes((270, 1010))
        self.setCentralWidget(splitter)

    def _create_menu_and_toolbar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addActions((self.new_action, self.open_action, self.open_project_action))
        file_menu.addSeparator()
        file_menu.addActions((self.save_action, self.save_as_action))
        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addActions((self.find_action, self.replace_action, self.goto_action, self.zoom_in_action, self.zoom_out_action))
        edit_menu.addSeparator()
        edit_menu.addActions((self.split_action, self.close_split_action))
        appearance_menu = self.menuBar().addMenu("Appearance")
        appearance_menu.addActions((self.theme_editor_action, self.import_font_action))
        snippets_menu = self.menuBar().addMenu("Snippets")
        snippets_menu.addActions(self.snippet_actions)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.outline_dock.toggleViewAction())
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.shortcuts_action)
        self.recent_files_menu = self.menuBar().addMenu("Recent")
        self.refresh_recent_menu()
        toolbar = QToolBar("Main toolbar", self)
        toolbar.setMovable(False)
        toolbar.addActions((self.new_action, self.open_action, self.save_action, self.split_action))
        self.find_input = QLineEdit(toolbar)
        self.find_input.setPlaceholderText("Find")
        self.find_input.setFixedWidth(170)
        self.find_input.setVisible(False)
        self.find_input.returnPressed.connect(self.find_next)
        toolbar.addWidget(self.find_input)
        self.replace_input = QLineEdit(toolbar)
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.setFixedWidth(150)
        self.replace_input.setVisible(False)
        toolbar.addWidget(self.replace_input)
        self.replace_button = QToolButton(toolbar)
        self.replace_button.setText("Replace")
        self.replace_button.setVisible(False)
        self.replace_button.clicked.connect(self.replace_next)
        toolbar.addWidget(self.replace_button)
        menu_bar = self.menuBar()
        controls = QWidget(menu_bar)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(6, 0, 4, 0)
        controls_layout.setSpacing(4)
        controls_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox(controls)
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.theme_name)
        self.theme_combo.setFixedWidth(82)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        controls_layout.addWidget(self.theme_combo)
        theme_editor_button = QToolButton(controls)
        theme_editor_button.setDefaultAction(self.theme_editor_action)
        theme_editor_button.setText("Edit theme")
        theme_editor_button.setToolTip("Edit current theme")
        theme_editor_button.setFixedWidth(82)
        controls_layout.addWidget(theme_editor_button)
        controls_layout.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox(controls)
        self.font_combo.setCurrentFont(QFont(self.font_family))
        self.font_combo.setFixedWidth(155)
        self.font_combo.currentFontChanged.connect(self.change_font_family)
        controls_layout.addWidget(self.font_combo)
        self.font_size_spin = QSpinBox(controls)
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.font_size)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setFixedWidth(68)
        self.font_size_spin.valueChanged.connect(self.change_font_size)
        controls_layout.addWidget(self.font_size_spin)
        import_font_button = QToolButton(controls)
        import_font_button.setDefaultAction(self.import_font_action)
        import_font_button.setText("Import Font")
        import_font_button.setToolTip("Import a font file")
        import_font_button.setFixedWidth(95)
        controls_layout.addWidget(import_font_button)
        controls_layout.addWidget(QLabel("Indentation:"))
        self.indent_combo = QComboBox(controls)
        self.indent_combo.addItems(("Tabs", "2 spaces", "4 spaces", "8 spaces"))
        self.indent_combo.setCurrentText("Tabs" if self.indent_mode == "Tabs" else f"{self.indent_width} spaces")
        self.indent_combo.setFixedWidth(100)
        self.indent_combo.currentTextChanged.connect(self.change_indentation)
        controls_layout.addWidget(self.indent_combo)
        menu_bar.setCornerWidget(controls, Qt.Corner.TopRightCorner)
        self.addToolBar(toolbar)

    def current_document(self) -> Optional[Document]:
        focus = QApplication.focusWidget()
        if self.split_document is not None and focus is not None and self.split_document.isAncestorOf(focus):
            return self.split_document
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, Document) else None

    def documents(self) -> list[Document]:
        documents = [self.tabs.widget(index) for index in range(self.tabs.count())]
        result = [doc for doc in documents if isinstance(doc, Document)]
        if self.split_document is not None:
            result.append(self.split_document)
        return result

    def setting_paths(self, key: str) -> list[Path]:
        """Read a QSettings string list safely, including legacy scalar values."""
        value = self.settings.value(key, [])
        values = value if isinstance(value, list) else ([value] if value else [])
        return [Path(str(item)) for item in values]

    def new_file(self) -> None:
        doc = Document(self.colors, self.font_family, self.font_size, self.indent_mode, self.indent_width)
        self.add_document(doc)

    def add_document(self, document: Document) -> None:
        index = self.tabs.addTab(document, document.name)
        self.tabs.setCurrentIndex(index)
        document.editor.modificationChanged.connect(lambda dirty, doc=document: self.document_modified(doc, dirty))
        document.editor.textChanged.connect(self.refresh_outline)
        if QSCINTILLA_AVAILABLE:
            document.editor.cursorPositionChanged.connect(lambda *_: self.update_status())
        else:
            document.editor.cursorPositionChanged.connect(self.update_status)
        self.update_status()
        self.refresh_outline()

    def document_modified(self, document: Document, dirty: bool) -> None:
        index = self.tabs.indexOf(document)
        if index >= 0:
            self.tabs.setTabText(index, f"{'● ' if dirty else ''}{document.name}")

    def refresh_outline(self, *_: object) -> None:
        if not hasattr(self, "outline"):
            return
        self.outline.clear()
        doc = self.current_document()
        if doc is None:
            return
        for line, text in enumerate(doc.editor.text_value().splitlines()):
            match = re.match(r"\s*(?:func|signal|class)\s+([A-Za-z_]\w*)", text)
            if match:
                self.outline.addItem(f"{match.group(1)} — line {line + 1}")
                self.outline.item(self.outline.count() - 1).setData(Qt.ItemDataRole.UserRole, line)

    def go_to_outline_item(self, item) -> None:
        doc = self.current_document()
        if doc is None:
            return
        line = int(item.data(Qt.ItemDataRole.UserRole))
        if QSCINTILLA_AVAILABLE:
            doc.editor.setCursorPosition(line, 0)
            doc.editor.ensureLineVisible(line)

    def open_tree_item(self, index: QModelIndex) -> None:
        path = Path(self.model.filePath(index))
        if path.is_file():
            self.open_path(path)

    def open_dialog(self) -> None:
        dialog = self.themed_file_dialog(
            "Open script", "Godot scripts (*.gd);;Text files (*.txt *.py);;All files (*)"
        )
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if dialog.exec():
            self.open_path(Path(dialog.selectedFiles()[0]))

    def open_path(self, path: Path) -> None:
        path = path.resolve()
        for index in range(self.tabs.count()):
            doc = self.tabs.widget(index)
            if isinstance(doc, Document) and doc.path == path:
                self.tabs.setCurrentIndex(index)
                return
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                raise ValueError("Files larger than 2 MB are not opened by this lightweight editor.")
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as error:
            self.show_message(QMessageBox.Icon.Critical, "Unable to open file", f"{path.name}\n\n{error}")
            return
        doc = Document(self.colors, self.font_family, self.font_size, self.indent_mode, self.indent_width, path)
        doc.editor.set_text_value(text)
        self.add_document(doc)
        self.watch_file(path)
        self.add_recent_file(path)

    def choose_project_folder(self) -> None:
        dialog = self.themed_file_dialog("Open project folder")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dialog.exec():
            folder = dialog.selectedFiles()[0]
            self.project_dir = Path(folder)
            self.model.setRootPath(folder)
            self.tree.setRootIndex(self.model.index(folder))
            self.update_status()

    def save_current(self) -> bool:
        doc = self.current_document()
        if doc is None:
            return False
        if doc.path is None:
            return self.save_current_as()
        return self.save_document(doc)

    def save_document(self, doc: Document) -> bool:
        """Persist one document without depending on which editor pane has focus."""
        assert doc.path is not None
        try:
            doc.path.write_text(doc.editor.text_value(), encoding="utf-8", newline="\n")
        except OSError as error:
            self.show_message(QMessageBox.Icon.Critical, "Unable to save file", f"{doc.path.name}\n\n{error}")
            return False
        doc.editor.setModified(False)
        self.status.showMessage(f"Saved {doc.path.name}", 2500)
        self.add_recent_file(doc.path)
        return True

    def save_current_as(self) -> bool:
        doc = self.current_document()
        if doc is None:
            return False
        dialog = self.themed_file_dialog("Save script", "GDScript (*.gd);;All files (*)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.selectFile(str(doc.path or self.project_dir / "script.gd"))
        if not dialog.exec():
            return False
        doc.path = Path(dialog.selectedFiles()[0])
        self.watch_file(doc.path)
        self.document_modified(doc, doc.editor.isModified())
        return self.save_document(doc)

    def watch_file(self, path: Path) -> None:
        """Track external saves from Godot without polling the project directory."""
        resolved_path = str(path.resolve())
        if resolved_path not in self.file_watcher.files():
            self.file_watcher.addPath(resolved_path)

    def reload_external_file(self, changed_path: str) -> None:
        path = Path(changed_path)
        for doc in self.documents():
            if doc.path is None or doc.path.resolve() != path.resolve():
                continue
            if doc.editor.isModified():
                self.status.showMessage(f"External change detected for {doc.name}; local edits were preserved.", 5000)
                return
            try:
                doc.editor.set_text_value(path.read_text(encoding="utf-8"))
                self.status.showMessage(f"Reloaded {doc.name} after an external save.", 2500)
            except (OSError, UnicodeDecodeError) as error:
                self.status.showMessage(f"Could not reload {path.name}: {error}", 5000)
            finally:
                # Some platforms remove a watch after a file is atomically replaced.
                self.watch_file(path)

    def close_tab(self, index: int) -> None:
        doc = self.tabs.widget(index)
        if not isinstance(doc, Document):
            return
        if doc.editor.isModified() and not self.confirm_save(doc):
            return
        if doc is self.split_source_document():
            self.close_split()
        self.tabs.removeTab(index)
        doc.deleteLater()
        if self.tabs.count() == 0:
            self.new_file()

    def confirm_save(self, doc: Document) -> bool:
        result = self.ask_question(
            "Unsaved changes", f"Save changes to {doc.name}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Save:
            return self.save_document(doc) if doc.path is not None else self.save_current_as()
        return result == QMessageBox.StandardButton.Discard

    def find_in_document(self) -> None:
        self.find_input.setVisible(True)
        self.replace_input.setVisible(True)
        self.replace_button.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def replace_next(self) -> None:
        doc = self.current_document()
        if doc is None or not self.find_input.text():
            return
        if QSCINTILLA_AVAILABLE:
            doc.editor.replaceSelectedText(self.replace_input.text())
        else:
            cursor = doc.editor.textCursor()
            if cursor.hasSelection():
                cursor.insertText(self.replace_input.text())
        self.find_next()

    def go_to_line(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        line, accepted = QInputDialog.getInt(self, "Go to Line", "Line number:", 1, 1, max(1, doc.editor.lines() if QSCINTILLA_AVAILABLE else doc.editor.blockCount()))
        if not accepted:
            return
        if QSCINTILLA_AVAILABLE:
            doc.editor.setCursorPosition(line - 1, 0)
            doc.editor.ensureLineVisible(line - 1)
        else:
            cursor = doc.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.MoveAnchor, line - 1)
            doc.editor.setTextCursor(cursor)

    def show_shortcuts(self) -> None:
        self.show_message(
            QMessageBox.Icon.Information, "Keyboard shortcuts",
            "Ctrl+N  New\nCtrl+O  Open\nCtrl+S  Save\nCtrl+Shift+S  Save As\n"
            "Ctrl+F  Find / Replace\nCtrl+G  Go to line\nCtrl+H  Find and replace\n"
            "Ctrl++ / Ctrl+-  Zoom\nUse the marker gutter to toggle breakpoints.",
        )

    def insert_snippet(self, text: str) -> None:
        doc = self.current_document()
        if doc is None:
            return
        if QSCINTILLA_AVAILABLE:
            doc.editor.replaceSelectedText(text)
        else:
            doc.editor.textCursor().insertText(text)

    def add_recent_file(self, path: Path) -> None:
        current = [str(item) for item in self.setting_paths("recent/files")]
        updated = [str(path)] + [item for item in current if item != str(path)]
        self.settings.setValue("recent/files", updated[:10])
        self.refresh_recent_menu()

    def refresh_recent_menu(self) -> None:
        if not hasattr(self, "recent_files_menu"):
            return
        self.recent_files_menu.clear()
        paths = self.setting_paths("recent/files")
        existing = [path for path in paths if path.is_file()]
        if not existing:
            action = self.recent_files_menu.addAction("No recent files")
            action.setEnabled(False)
            return
        for path in existing:
            self.recent_files_menu.addAction(path.name, lambda _, file_path=path: self.open_path(file_path))

    def autosave(self) -> None:
        for doc in self.documents():
            if doc.path is not None and doc.editor.isModified():
                self.save_document(doc)

    def find_next(self) -> None:
        doc = self.current_document()
        query = self.find_input.text()
        if doc is None or not query:
            return
        if QSCINTILLA_AVAILABLE:
            found = doc.editor.findFirst(query, False, False, False, True, True)
        else:
            found = doc.editor.find(query)
        if not found:
            self.status.showMessage(f'No match for "{query}"', 2500)

    def split_source_document(self) -> Optional[Document]:
        return self.split_source

    def split_current_tab(self) -> None:
        if self.tabs.count() < 2:
            self.status.showMessage("Open at least two tabs before splitting the editor.", 3000)
            return
        source = self.current_document()
        if source is None:
            return
        self.close_split()
        duplicate = Document(self.colors, self.font_family, self.font_size, self.indent_mode, self.indent_width, source.path)
        duplicate.editor.set_text_value(source.editor.text_value())
        self.split_document = duplicate
        self.split_source = source
        self.editor_splitter.addWidget(duplicate)
        self.editor_splitter.setSizes((self.editor_splitter.width() // 2, self.editor_splitter.width() // 2))
        source.editor.textChanged.connect(lambda: self.sync_split(source, duplicate))
        duplicate.editor.textChanged.connect(lambda: self.sync_split(duplicate, source))
        self.status.showMessage(f"Split view: {source.name}", 2500)

    def sync_split(self, source: Document, target: Document) -> None:
        if self._syncing_split or source.editor.text_value() == target.editor.text_value():
            return
        self._syncing_split = True
        target.editor.set_text_value(source.editor.text_value())
        target.editor.setModified(source.editor.isModified())
        self._syncing_split = False

    def close_split(self) -> None:
        if self.split_document is None:
            return
        self.split_document.setParent(None)
        self.split_document.deleteLater()
        self.split_document = None
        self.split_source = None

    def change_theme(self, name: str) -> None:
        if name not in self.palettes:
            return
        self.theme_name = name
        self.settings.setValue("theme", name)
        self.apply_theme()

    def edit_theme(self) -> None:
        dialog = ThemeEditor(self.colors, self, self.dialog_style_sheet())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.palettes[self.theme_name] = dialog.colors
            self.settings.setValue(f"palette/{self.theme_name}", json.dumps(dialog.colors))
            self.apply_theme()

    def import_font(self) -> None:
        dialog = self.themed_file_dialog("Import editor font", "Font files (*.ttf *.otf *.ttc *.woff *.woff2)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if not dialog.exec():
            return
        filename = dialog.selectedFiles()[0]
        font_id = QFontDatabase.addApplicationFont(filename)
        if font_id == -1:
            self.show_message(QMessageBox.Icon.Critical, "Unable to import font", "Qt could not load this font file.")
            return
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            self.show_message(QMessageBox.Icon.Critical, "Unable to import font", "The imported file does not expose a usable font family.")
            return
        if filename not in self.imported_font_paths:
            self.imported_font_paths.append(filename)
            self.settings.setValue("font/imported_paths", self.imported_font_paths)
        self.font_combo.setCurrentFont(QFont(families[0]))
        self.status.showMessage(f"Imported font: {families[0]}", 3000)

    def change_font_family(self, font: QFont | str) -> None:
        self.font_family = font.family() if isinstance(font, QFont) else font
        self.settings.setValue("font/family", self.font_family)
        self.apply_editor_font()

    def change_font_size(self, size: int) -> None:
        self.font_size = size
        self.settings.setValue("font/size", size)
        self.apply_editor_font()

    def apply_editor_font(self) -> None:
        for doc in self.documents():
            doc.editor.apply_font(self.font_family, self.font_size)

    def change_indentation(self, selection: str) -> None:
        if selection == "Tabs":
            self.indent_mode, self.indent_width = "Tabs", 4
        else:
            self.indent_mode = "Spaces"
            self.indent_width = int(selection.split()[0])
        self.settings.setValue("indent/mode", self.indent_mode)
        self.settings.setValue("indent/width", self.indent_width)
        for doc in self.documents():
            doc.editor.apply_indentation(self.indent_mode, self.indent_width)

    def themed_file_dialog(self, title: str, name_filter: str = "All files (*)") -> QFileDialog:
        """Create a non-native file dialog so Qt can apply the active editor theme."""
        dialog = QFileDialog(self, title, str(self.project_dir), name_filter)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setViewMode(QFileDialog.ViewMode.Detail)
        dialog.setStyleSheet(self.dialog_style_sheet())
        return dialog

    def dialog_style_sheet(self) -> str:
        c = self.colors
        return (
            f"QDialog, QMessageBox, QInputDialog, QColorDialog {{ background: {c['window']}; color: {c['text']}; }}"
            f"QLabel, QCheckBox {{ color: {c['text']}; }}"
            f"QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QListView, QTreeView {{ background: {c['editor']}; color: {c['text']}; border: 1px solid {c['accent']}; padding: 4px; }}"
            f"QPushButton {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['accent']}; padding: 5px 12px; }}"
            f"QPushButton:hover {{ background: {c['accent']}; color: {c['window']}; }}"
            f"QHeaderView::section {{ background: {c['panel']}; color: {c['text']}; padding: 4px; }}"
        )

    def show_message(self, icon: QMessageBox.Icon, title: str, message: str) -> None:
        dialog = QMessageBox(icon, title, message, QMessageBox.StandardButton.Ok, self)
        dialog.setStyleSheet(self.dialog_style_sheet())
        dialog.exec()

    def ask_question(self, title: str, message: str, buttons: QMessageBox.StandardButton, default: QMessageBox.StandardButton) -> QMessageBox.StandardButton:
        dialog = QMessageBox(QMessageBox.Icon.Question, title, message, buttons, self)
        dialog.setDefaultButton(default)
        dialog.setStyleSheet(self.dialog_style_sheet())
        return QMessageBox.StandardButton(dialog.exec())

    def apply_theme(self) -> None:
        c = self.colors
        palette = QApplication.instance().palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
        QApplication.instance().setPalette(palette)
        self.setStyleSheet(
            f"QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar, QLabel, QToolButton {{ background: {c['window']}; color: {c['text']}; }}"
            f"QMenu {{ min-width: 230px; }}"
            f"QMenuBar::item, QMenu::item {{ color: {c['text']}; min-width: 190px; padding: 6px 22px; }}"
            f"QMenuBar::item:selected, QMenu::item:selected {{ background: {c['panel']}; color: {c['text']}; }}"
            f"QTreeView, QListView, QTabWidget::pane {{ background: {c['panel']}; color: {c['text']}; border: 0; }}"
            f"QHeaderView::section {{ background: {c['panel']}; color: {c['text']}; }}"
            f"QTabBar::tab {{ background: {c['panel']}; color: {c['text']}; padding: 7px 12px; }}"
            f"QTabBar::tab:selected {{ background: {c['editor']}; border-top: 2px solid {c['accent']}; }}"
            f"QComboBox, QPushButton, QLineEdit {{ background: {c['panel']}; color: {c['text']}; padding: 4px; }}"
        )
        for doc in self.documents():
            doc.editor.apply_theme(c)

    def zoom(self, amount: int) -> None:
        doc = self.current_document()
        if doc is not None and QSCINTILLA_AVAILABLE:
            doc.editor.zoomIn(amount) if amount > 0 else doc.editor.zoomOut(-amount)

    def update_status(self, *_: object) -> None:
        doc = self.current_document()
        if doc is None:
            self.status.showMessage(str(self.project_dir))
            return
        if QSCINTILLA_AVAILABLE:
            line, column = doc.editor.getCursorPosition()
            position = f"Ln {line + 1}, Col {column + 1}"
        else:
            cursor = doc.editor.textCursor()
            position = f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}"
        self.status.showMessage(f"{self.project_dir}    {position}")

    def closeEvent(self, event) -> None:
        for doc in self.documents():
            if doc.editor.isModified() and not self.confirm_save(doc):
                event.ignore()
                return
        self._empty_workspace.cleanup()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GDScript Studio")
    app.setOrganizationName("GDScriptStudio")
    window = EditorWindow()
    if len(sys.argv) > 1:
        requested_path = Path(sys.argv[1])
        if requested_path.is_file():
            window.open_path(requested_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
