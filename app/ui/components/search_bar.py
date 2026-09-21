from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp, sp
from kivy.clock import Clock

class SearchBar(BoxLayout):
    search_text = StringProperty("")
    on_search = ObjectProperty(None)
    search_delay = NumericProperty(0.3)

    def __init__(self, **kwargs):
        super(SearchBar, self).__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(5)
        self.padding = dp(5)
        self.size_hint_y = None
        self.height = dp(40)
        self._search_event = None

        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(5)])
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.icon = Label(text="🔍", size_hint_x=None, width=dp(30), color=(0.4, 0.4, 0.4, 1))
        
        self.text_input = TextInput(
            hint_text="Search anything...",
            multiline=False,
            background_color=(0,0,0,0),
            foreground_color=(0,0,0,1),
            padding=[dp(5), dp(10), dp(5), dp(10)]
        )
        self.text_input.bind(text=self._on_text_changed)
        
        self.clear_btn = Button(
            text="✕",
            size_hint_x=None,
            width=dp(30),
            background_color=(0,0,0,0),
            color=(0.5, 0.5, 0.5, 1)
        )
        self.clear_btn.bind(on_release=lambda x: self.clear())

        self.add_widget(self.icon)
        self.add_widget(self.text_input)
        self.add_widget(self.clear_btn)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def focus(self):
        self.text_input.focus = True

    def clear(self):
        self.text_input.text = ""
        self.search_text = ""
        if self.on_search:
            self.on_search("")

    def _on_text_changed(self, instance, value):
        self.search_text = value
        if self._search_event:
            self._search_event.cancel()
        self._search_event = Clock.schedule_once(self._trigger_search, self.search_delay)

    def _trigger_search(self, dt):
        if self.on_search:
            self.on_search(self.search_text)
