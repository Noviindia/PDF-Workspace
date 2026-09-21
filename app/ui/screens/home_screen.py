import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.properties import ObjectProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.app import App

try:
    from plyer import filechooser
except ImportError:
    filechooser = None

class HomeScreen(Screen):
    """
    HomeScreen is the initial view showing recent projects and allowing PDF import.
    """
    recent_projects = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'home'
        # background
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        main_layout = BoxLayout(orientation='vertical', padding=dp(40), spacing=dp(30))
        
        # Title area
        title_box = BoxLayout(orientation='vertical', size_hint=(1, 0.2))
        title = Label(text="PDF Workspace", font_size=sp(36), bold=True, color=(0.1, 0.1, 0.1, 1))
        subtitle = Label(text="🔒 100% Local & Offline", font_size=sp(16), color=(0.4, 0.6, 0.4, 1))
        title_box.add_widget(title)
        title_box.add_widget(subtitle)
        main_layout.add_widget(title_box)

        # Drop area / Browse button
        drop_area = BoxLayout(orientation='vertical', size_hint=(1, 0.4), spacing=dp(10))
        with drop_area.canvas.before:
            Color(0.9, 0.9, 0.9, 1)
            self.drop_rect = RoundedRectangle(pos=drop_area.pos, size=drop_area.size, radius=[dp(10)])
            Color(0.7, 0.7, 0.7, 1)
            self.drop_line = Line(rounded_rectangle=[drop_area.x, drop_area.y, drop_area.width, drop_area.height, dp(10)], width=1, dash_offset=5, dash_length=5)
        drop_area.bind(pos=self._update_drop_rect, size=self._update_drop_rect)
        
        drop_label = Label(text="📄 Drop PDF Here\nor", font_size=sp(20), color=(0.3, 0.3, 0.3, 1), halign='center')
        browse_btn = Button(text="Browse Files", size_hint=(None, None), size=(dp(200), dp(50)), pos_hint={'center_x': 0.5})
        browse_btn.bind(on_release=self.open_file_chooser)
        drop_area.add_widget(drop_label)
        drop_area.add_widget(browse_btn)
        main_layout.add_widget(drop_area)

        # Recent Documents area
        recent_box = BoxLayout(orientation='vertical', size_hint=(1, 0.4), spacing=dp(10))
        recent_title = Label(text="Recent Documents", font_size=sp(18), bold=True, color=(0.2, 0.2, 0.2, 1), size_hint=(1, None), height=dp(30), halign='left', text_size=(None, None))
        recent_title.bind(size=recent_title.setter('text_size'))
        recent_box.add_widget(recent_title)

        self.recent_list_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        self.recent_list_layout.bind(minimum_height=self.recent_list_layout.setter('height'))
        
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.recent_list_layout)
        recent_box.add_widget(scroll)

        main_layout.add_widget(recent_box)
        self.add_widget(main_layout)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _update_drop_rect(self, instance, value):
        self.drop_rect.pos = instance.pos
        self.drop_rect.size = instance.size
        self.drop_line.rounded_rectangle = [instance.x, instance.y, instance.width, instance.height, dp(10)]

    def on_enter(self):
        """Called when the screen is entered."""
        self._load_recent_documents()

    def _load_recent_documents(self):
        self.recent_list_layout.clear_widgets()
        app = App.get_running_app()
        recent = []
        if hasattr(app, 'project_service') and app.project_service:
            try:
                recent = app.project_service.get_recent_projects()
            except Exception:
                pass
        
        if not recent:
            recent = [
                {'name': 'students.pdf', 'path': '/path/to/students.pdf', 'date': 'Sep 15, 2026'},
                {'name': 'report.pdf', 'path': '/path/to/report.pdf', 'date': 'Sep 14, 2026'}
            ]
        
        for doc in recent:
            btn = Button(
                text=f"📁 {doc.get('name', 'Unknown')}  - {doc.get('date', '')}",
                size_hint_y=None, height=dp(40),
                background_color=(0.9, 0.9, 0.9, 1),
                color=(0.1, 0.1, 0.1, 1),
                halign='left'
            )
            btn.bind(size=btn.setter('text_size'))
            btn.path = doc.get('path', '')
            btn.bind(on_release=lambda x: self._on_recent_clicked(x.path))
            self.recent_list_layout.add_widget(btn)

    def open_file_chooser(self, instance):
        """Opens native file chooser on Android or Kivy FileChooser on Desktop."""
        if platform == 'android' and filechooser:
            filechooser.open_file(on_selection=self._on_android_file_selected, filters=[("PDF Files", "*.pdf")])
        else:
            self._show_kivy_file_chooser()

    def _on_android_file_selected(self, selection):
        if selection:
            self._on_file_selected(selection[0])

    def _show_kivy_file_chooser(self):
        content = BoxLayout(orientation='vertical')
        fc = FileChooserListView(filters=['*.pdf'], path=os.path.expanduser('~'))
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50))
        cancel_btn = Button(text="Cancel")
        open_btn = Button(text="Open")
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(open_btn)
        
        content.add_widget(fc)
        content.add_widget(btn_layout)
        
        popup = Popup(title="Select PDF Document", content=content, size_hint=(0.9, 0.9))
        
        cancel_btn.bind(on_release=popup.dismiss)
        open_btn.bind(on_release=lambda x: self._on_popup_file_selected(fc.selection, popup))
        
        popup.open()

    def _on_popup_file_selected(self, selection, popup):
        if selection:
            popup.dismiss()
            self._on_file_selected(selection[0])

    def _on_file_selected(self, file_path):
        app = App.get_running_app()
        if hasattr(app, 'open_pdf'):
            app.open_pdf(file_path)

    def _on_recent_clicked(self, project_path):
        app = App.get_running_app()
        if hasattr(app, 'open_pdf'):
            app.open_pdf(project_path)
