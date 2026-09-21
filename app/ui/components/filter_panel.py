from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import DictProperty, ObjectProperty, ListProperty
from kivy.metrics import dp, sp

class FilterPanel(BoxLayout):
    active_filters = DictProperty({})
    on_filters_changed = ObjectProperty(None)
    categories = ListProperty([])

    def __init__(self, **kwargs):
        super(FilterPanel, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(10)

        with self.canvas.before:
            Color(0.92, 0.92, 0.92, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(30))
        header.add_widget(Label(text="Filters", color=(0,0,0,1), bold=True, halign='left'))
        btn_clear = Button(text="Clear All", size_hint_x=None, width=dp(80))
        btn_clear.bind(on_release=lambda x: self.clear_filters())
        header.add_widget(btn_clear)
        self.add_widget(header)

        # Controls
        grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(5))
        grid.bind(minimum_height=grid.setter('height'))

        # Category filter
        grid.add_widget(Label(text="Category:", color=(0,0,0,1), size_hint_y=None, height=dp(30)))
        self.spin_cat = Spinner(text="All", values=["All"], size_hint_y=None, height=dp(30))
        grid.add_widget(self.spin_cat)

        # Page range
        grid.add_widget(Label(text="Page Range:", color=(0,0,0,1), size_hint_y=None, height=dp(30)))
        box_page = BoxLayout(spacing=dp(5), size_hint_y=None, height=dp(30))
        self.ti_page_from = TextInput(hint_text="From", input_filter="int", multiline=False)
        self.ti_page_to = TextInput(hint_text="To", input_filter="int", multiline=False)
        box_page.add_widget(self.ti_page_from)
        box_page.add_widget(self.ti_page_to)
        grid.add_widget(box_page)

        self.add_widget(grid)

        # Apply button
        btn_apply = Button(text="Apply Filters", size_hint_y=None, height=dp(40))
        btn_apply.bind(on_release=lambda x: self.apply_filters())
        self.add_widget(btn_apply)

        # Active filters chips area
        self.chips_area = GridLayout(cols=3, spacing=dp(5), size_hint_y=None)
        self.chips_area.bind(minimum_height=self.chips_area.setter('height'))
        self.add_widget(self.chips_area)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def load_filter_options(self, categories, field_names):
        self.categories = categories
        self.spin_cat.values = ["All"] + [c.get('name', '') for c in categories]

    def apply_filters(self):
        filters = {}
        if self.spin_cat.text != "All":
            filters['category'] = self.spin_cat.text
            
        p_from = self.ti_page_from.text
        p_to = self.ti_page_to.text
        if p_from or p_to:
            filters['page_range'] = (int(p_from) if p_from else 1, int(p_to) if p_to else 9999)

        self.active_filters = filters
        self._update_chips()
        
        if self.on_filters_changed:
            self.on_filters_changed(self.active_filters)

    def clear_filters(self):
        self.spin_cat.text = "All"
        self.ti_page_from.text = ""
        self.ti_page_to.text = ""
        self.active_filters = {}
        self._update_chips()
        if self.on_filters_changed:
            self.on_filters_changed(self.active_filters)

    def _update_chips(self):
        self.chips_area.clear_widgets()
        for k, v in self.active_filters.items():
            self._add_filter_chip(k, str(v))

    def _add_filter_chip(self, filter_type, value):
        chip = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(5))
        with chip.canvas.before:
            Color(0.8, 0.8, 0.9, 1)
            RoundedRectangle(pos=chip.pos, size=chip.size, radius=[dp(5)])
            
        lbl = Label(text=f"{filter_type}: {value}", color=(0,0,0,1))
        btn = Button(text="✕", size_hint_x=None, width=dp(30), background_color=(0,0,0,0), color=(1,0,0,1))
        btn.bind(on_release=lambda x: self._remove_filter(filter_type))
        
        chip.add_widget(lbl)
        chip.add_widget(btn)
        
        def update_chip_rect(instance, val, c=chip):
            c.canvas.before.children[1].pos = instance.pos
            c.canvas.before.children[1].size = instance.size
        chip.bind(pos=update_chip_rect, size=update_chip_rect)
        
        self.chips_area.add_widget(chip)

    def _remove_filter(self, filter_type):
        if filter_type in self.active_filters:
            del self.active_filters[filter_type]
            if filter_type == 'category':
                self.spin_cat.text = "All"
            elif filter_type == 'page_range':
                self.ti_page_from.text = ""
                self.ti_page_to.text = ""
                
            self._update_chips()
            if self.on_filters_changed:
                self.on_filters_changed(self.active_filters)

    def get_active_filters(self) -> dict:
        return self.active_filters
