from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.splitter import Splitter
from kivy.graphics import Color, Rectangle, Line
from kivy.properties import ObjectProperty, StringProperty, ListProperty, NumericProperty
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.app import App

try:
    from app.ui.components.pdf_viewer import PDFViewer
    from app.ui.components.search_bar import SearchBar
    from app.ui.components.search_results import SearchResults
    from app.ui.components.category_panel import CategoryPanel
    from app.ui.components.data_table import DataTable
    from app.ui.components.filter_panel import FilterPanel
    from app.ui.components.status_bar import StatusBar
except ImportError:
    # Fallback/mock for components if not implemented yet
    PDFViewer = lambda **kwargs: Label(text="PDF Viewer Mock", color=(0,0,0,1), **kwargs)
    SearchBar = lambda **kwargs: TextInput(hint_text="Search...", **kwargs)
    SearchResults = lambda **kwargs: Label(text="Search Results", color=(0,0,0,1), **kwargs)
    CategoryPanel = lambda **kwargs: Label(text="Categories Mock", color=(0,0,0,1), **kwargs)
    DataTable = lambda **kwargs: Label(text="Data Table Mock", color=(0,0,0,1), **kwargs)
    FilterPanel = lambda **kwargs: Label(text="Filter Mock", color=(0,0,0,1), **kwargs)
    StatusBar = lambda **kwargs: Label(text="Status Bar Mock", color=(0,0,0,1), **kwargs)

class WorkspaceScreen(Screen):
    """
    WorkspaceScreen handles the main application workspace, integrating multiple UI components.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'workspace'
        self.processing_service = None
        
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        main_layout = BoxLayout(orientation='vertical')
        
        # Top Bar
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=dp(5), spacing=dp(10))
        with top_bar.canvas.before:
            Color(0.2, 0.4, 0.8, 1)
            self.top_bar_rect = Rectangle(pos=top_bar.pos, size=top_bar.size)
        top_bar.bind(pos=self._update_top_rect, size=self._update_top_rect)
        
        title_lbl = Label(text="PDF Workspace", size_hint_x=None, width=dp(150), bold=True)
        open_btn = Button(text="Open", size_hint_x=None, width=dp(80), background_color=(0.3, 0.5, 0.9, 1))
        open_btn.bind(on_release=self.open_new_pdf)
        
        self.search_bar = SearchBar(size_hint_x=1)
        if isinstance(self.search_bar, TextInput):
            self.search_bar.bind(text=self._on_search_mock)
            
        export_btn = Button(text="Export", size_hint_x=None, width=dp(80), background_color=(0.3, 0.5, 0.9, 1))
        export_btn.bind(on_release=self._open_export)
        
        top_bar.add_widget(title_lbl)
        top_bar.add_widget(open_btn)
        top_bar.add_widget(self.search_bar)
        top_bar.add_widget(export_btn)
        
        main_layout.add_widget(top_bar)
        
        # Body (Horizontal Split)
        body_layout = BoxLayout(orientation='horizontal')
        
        # Sidebar
        sidebar_splitter = Splitter(sizable_from='right', size_hint_x=None, width=dp(250))
        sidebar_box = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(10))
        with sidebar_box.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.side_rect = Rectangle(pos=sidebar_box.pos, size=sidebar_box.size)
        sidebar_box.bind(pos=self._update_side_rect, size=self._update_side_rect)
        
        doc_label = Label(text="Documents", size_hint_y=None, height=dp(30), color=(0.1, 0.1, 0.1, 1), bold=True)
        self.category_panel = CategoryPanel(size_hint_y=0.6)
        
        stats_label = Label(text="Statistics", size_hint_y=None, height=dp(30), color=(0.1, 0.1, 0.1, 1), bold=True)
        self.stats_info = Label(text="Loading...", color=(0.3, 0.3, 0.3, 1), size_hint_y=0.4, valign='top')
        self.stats_info.bind(size=self.stats_info.setter('text_size'))
        
        sidebar_box.add_widget(doc_label)
        sidebar_box.add_widget(self.category_panel)
        sidebar_box.add_widget(stats_label)
        sidebar_box.add_widget(self.stats_info)
        sidebar_splitter.add_widget(sidebar_box)
        
        body_layout.add_widget(sidebar_splitter)
        
        # Main Content Area (Vertical Split)
        content_layout = BoxLayout(orientation='vertical', padding=dp(5), spacing=dp(5))
        
        self.data_table = DataTable(size_hint_y=0.6)
        table_splitter = Splitter(sizable_from='bottom')
        table_splitter.add_widget(self.data_table)
        
        self.pdf_viewer = PDFViewer(size_hint_y=0.4)
        
        content_layout.add_widget(table_splitter)
        content_layout.add_widget(self.pdf_viewer)
        
        body_layout.add_widget(content_layout)
        
        main_layout.add_widget(body_layout)
        
        # Bottom Status Bar
        self.status_bar = StatusBar(size_hint_y=None, height=dp(30))
        main_layout.add_widget(self.status_bar)
        
        self.add_widget(main_layout)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        
    def _update_top_rect(self, instance, value):
        self.top_bar_rect.pos = instance.pos
        self.top_bar_rect.size = instance.size
        
    def _update_side_rect(self, instance, value):
        self.side_rect.pos = instance.pos
        self.side_rect.size = instance.size

    def load_workspace(self, processing_service):
        """Initializes workspace view with a given processing service."""
        self.processing_service = processing_service
        self._refresh_data()
        
    def focus_search(self):
        if hasattr(self.search_bar, 'focus'):
            self.search_bar.focus = True
            
    def open_new_pdf(self, instance):
        app = App.get_running_app()
        app.screen_manager.current = 'home'
        
    def _open_export(self, instance):
        app = App.get_running_app()
        app.screen_manager.current = 'export'
        export_screen = app.screen_manager.get_screen('export')
        if hasattr(export_screen, 'load_export_options'):
            export_screen.load_export_options(self.processing_service)
            
    def _on_search_mock(self, instance, value):
        self._on_search(value)

    def _on_search(self, query):
        if not self.processing_service:
            return
        # Implement search routing
        pass

    def _on_category_selected(self, category_id):
        pass

    def _on_record_selected(self, record):
        if hasattr(self.pdf_viewer, 'go_to_page') and 'page' in record:
            self.pdf_viewer.go_to_page(record['page'])
            
    def _on_filter_changed(self, filters):
        pass

    def _refresh_data(self):
        if not self.processing_service:
            return
        self.stats_info.text = "Pages: 42\nRecords: 345"
        if hasattr(self.status_bar, 'text'):
            self.status_bar.text = "Status: Ready | 🔒 Local"
