from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import ListProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp, sp

class SearchResultItem(BoxLayout):
    def __init__(self, result_data, on_select, **kwargs):
        super(SearchResultItem, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(80)
        self.padding = dp(10)
        self.spacing = dp(5)
        self.result_data = result_data
        self.on_select_cb = on_select

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(5)])
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Header: Text match and category
        header = BoxLayout(size_hint_y=None, height=dp(20))
        text_match = result_data.get('text', 'Unknown')
        category = result_data.get('category', 'Uncategorized')
        page = result_data.get('page', 1)

        lbl_text = Label(text=f"[b]{text_match}[/b]", markup=True, color=(0,0,0,1), text_size=(None, None), halign='left')
        lbl_text.bind(size=lbl_text.setter('text_size'))
        
        lbl_meta = Label(text=f"Page {page} • {category}", size_hint_x=None, width=dp(120), color=(0.4, 0.4, 0.4, 1), halign='right')

        header.add_widget(lbl_text)
        header.add_widget(lbl_meta)

        # Context snippet
        snippet = result_data.get('context', 'No context available')
        lbl_snippet = Label(
            text=snippet,
            color=(0.3, 0.3, 0.3, 1),
            text_size=(None, None),
            halign='left',
            valign='top'
        )
        lbl_snippet.bind(size=lbl_snippet.setter('text_size'))

        self.add_widget(header)
        self.add_widget(lbl_snippet)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_select_cb:
                self.on_select_cb(self.result_data)
            return True
        return super(SearchResultItem, self).on_touch_down(touch)

class SearchResults(BoxLayout):
    results = ListProperty([])
    on_result_selected = ObjectProperty(None)
    result_count = NumericProperty(0)

    def __init__(self, **kwargs):
        super(SearchResults, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(5)

        with self.canvas.before:
            Color(0.9, 0.9, 0.9, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Header
        self.header = BoxLayout(size_hint_y=None, height=dp(30), padding=[dp(5), 0])
        self.lbl_count = Label(text="0 results found", color=(0.2, 0.2, 0.2, 1), halign='left')
        self.lbl_count.bind(size=self.lbl_count.setter('text_size'))
        self.header.add_widget(self.lbl_count)
        self.add_widget(self.header)

        # Results List
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, padding=dp(5))
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll_view.add_widget(self.grid)
        self.add_widget(self.scroll_view)

        self.bind(results=self._on_results_change)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def update_results(self, results: list):
        self.results = results

    def clear(self):
        self.results = []

    def _on_results_change(self, instance, value):
        self.grid.clear_widgets()
        self.result_count = len(self.results)
        self.lbl_count.text = f"{self.result_count} results found"

        for res in self.results:
            item = SearchResultItem(result_data=res, on_select=self._on_result_clicked)
            self.grid.add_widget(item)

    def _on_result_clicked(self, result):
        if self.on_result_selected:
            self.on_result_selected(result)
