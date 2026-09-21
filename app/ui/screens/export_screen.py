from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import ObjectProperty, StringProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.app import App

try:
    from app.services.export_service import ExportService
    from app.database.models import ExportConfig
except ImportError:
    ExportService = None
    ExportConfig = None

class ExportScreen(Screen):
    """
    ExportScreen provides options to export current project data.
    """
    selected_format = StringProperty("CSV")
    selected_scope = StringProperty("all")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'export'
        self.processing_service = None
        self.formats = ["DOCX", "XLSX", "CSV", "JSON", "HTML", "TXT", "MD"]
        self.scopes = [
            ("all", "Entire document"),
            ("category", "Category"),
            ("selected", "Selected records"),
            ("search", "Search results")
        ]
        
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        main_layout = BoxLayout(orientation='vertical', padding=dp(30), spacing=dp(20))
        
        # Header
        header_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        back_btn = Button(text="← Back", size_hint_x=None, width=dp(100))
        back_btn.bind(on_release=self._go_back)
        title = Label(text="Export / Convert", font_size=sp(24), bold=True, color=(0.1, 0.1, 0.1, 1))
        header_box.add_widget(back_btn)
        header_box.add_widget(title)
        
        main_layout.add_widget(header_box)
        
        # Formats
        format_box = BoxLayout(orientation='vertical', size_hint_y=0.3, spacing=dp(10))
        format_label = Label(text="Format:", font_size=sp(16), bold=True, color=(0.2, 0.2, 0.2, 1), size_hint_y=None, height=dp(30), halign='left')
        format_label.bind(size=format_label.setter('text_size'))
        format_box.add_widget(format_label)
        
        grid = GridLayout(cols=4, spacing=dp(10), size_hint_y=None, height=dp(100))
        self.format_buttons = []
        for fmt in self.formats:
            btn = ToggleButton(text=fmt, group='formats', state='down' if fmt == self.selected_format else 'normal')
            btn.bind(on_press=lambda x, f=fmt: self._select_format(f))
            self.format_buttons.append(btn)
            grid.add_widget(btn)
            
        format_box.add_widget(grid)
        main_layout.add_widget(format_box)
        
        # Scope
        scope_box = BoxLayout(orientation='vertical', size_hint_y=0.4, spacing=dp(10))
        scope_label = Label(text="Scope:", font_size=sp(16), bold=True, color=(0.2, 0.2, 0.2, 1), size_hint_y=None, height=dp(30), halign='left')
        scope_label.bind(size=scope_label.setter('text_size'))
        scope_box.add_widget(scope_label)
        
        self.scope_buttons = []
        for sid, text in self.scopes:
            btn = ToggleButton(
                text=text, 
                group='scopes', 
                state='down' if sid == self.selected_scope else 'normal',
                size_hint_y=None, height=dp(40),
                halign='left',
                padding=(dp(10), 0)
            )
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=lambda x, s=sid: self._select_scope(s))
            self.scope_buttons.append(btn)
            scope_box.add_widget(btn)
            
        main_layout.add_widget(scope_box)
        
        # Preview
        preview_box = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=dp(5))
        with preview_box.canvas.before:
            Color(0.9, 0.9, 0.9, 1)
            self.preview_rect = RoundedRectangle(pos=preview_box.pos, size=preview_box.size, radius=[dp(5)])
        preview_box.bind(pos=self._update_preview_rect, size=self._update_preview_rect)
        
        prev_label = Label(text="Preview:", bold=True, color=(0.3, 0.3, 0.3, 1), size_hint_y=None, height=dp(25), halign='left')
        prev_label.bind(size=prev_label.setter('text_size'))
        
        self.preview_text = Label(
            text="Will export 0 records.\nFields: None", 
            color=(0.4, 0.4, 0.4, 1),
            halign='left', valign='top'
        )
        self.preview_text.bind(size=self.preview_text.setter('text_size'))
        
        preview_box.add_widget(prev_label)
        preview_box.add_widget(self.preview_text)
        
        main_layout.add_widget(preview_box)
        
        # Export Button
        export_btn_box = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(50), dp(10)])
        self.export_action_btn = Button(
            text="Export", 
            background_color=(0.2, 0.6, 0.2, 1),
            bold=True
        )
        self.export_action_btn.bind(on_release=self._do_export)
        export_btn_box.add_widget(self.export_action_btn)
        
        main_layout.add_widget(export_btn_box)
        self.add_widget(main_layout)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        
    def _update_preview_rect(self, instance, value):
        self.preview_rect.pos = instance.pos
        self.preview_rect.size = instance.size

    def load_export_options(self, processing_service):
        """Prepares export screen based on current loaded service."""
        self.processing_service = processing_service
        self._update_preview()

    def _select_format(self, format_name):
        self.selected_format = format_name
        self._update_preview()

    def _select_scope(self, scope):
        self.selected_scope = scope
        self._update_preview()

    def _update_preview(self):
        record_count = 0
        if self.selected_scope == "all":
            record_count = 345 # Mock for now
        elif self.selected_scope == "category":
            record_count = 124
        elif self.selected_scope == "selected":
            record_count = 18
        elif self.selected_scope == "search":
            record_count = 7
            
        self.preview_text.text = f"Will export {record_count} records in {self.selected_format} format.\nFields: Name, Roll No, Class..."

    def _do_export(self, instance):
        if not ExportService or not ExportConfig:
            self._show_popup("Export Failed", "Export modules not available.")
            return
            
        config = ExportConfig(
            format=self.selected_format,
            scope=self.selected_scope
        )
        
        try:
            service = ExportService()
            result_path = service.export(config, self.processing_service)
            self._show_popup("Export Success", f"Successfully exported to:\n{result_path}")
        except Exception as e:
            self._show_popup("Export Error", str(e))

    def _show_popup(self, title, message):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        lbl = Label(text=message, halign='center', color=(1,1,1,1))
        lbl.bind(size=lbl.setter('text_size'))
        btn = Button(text="OK", size_hint_y=None, height=dp(40))
        
        content.add_widget(lbl)
        content.add_widget(btn)
        
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def _go_back(self, instance):
        app = App.get_running_app()
        app.screen_manager.current = 'workspace'
