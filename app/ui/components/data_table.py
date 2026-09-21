from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.graphics import Color, Rectangle, Line
from kivy.properties import ListProperty, ObjectProperty, NumericProperty, DictProperty, StringProperty
from kivy.metrics import dp, sp
from kivy.clock import Clock

class DataTableHeader(BoxLayout):
    def __init__(self, text, on_sort, **kwargs):
        super(DataTableHeader, self).__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(40)
        self.sort_asc = True
        self.on_sort_cb = on_sort
        self.field_name = text

        with self.canvas.before:
            Color(0.8, 0.8, 0.8, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.lbl = Label(text=text, color=(0,0,0,1), bold=True)
        self.add_widget(self.lbl)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.sort_asc = not self.sort_asc
            arrow = "▲" if self.sort_asc else "▼"
            self.lbl.text = f"{self.field_name} {arrow}"
            if self.on_sort_cb:
                self.on_sort_cb(self.field_name, self.sort_asc)
            return True
        return super(DataTableHeader, self).on_touch_down(touch)

class DataTableRow(BoxLayout):
    def __init__(self, record, field_names, on_edit, on_select, bg_color, **kwargs):
        super(DataTableRow, self).__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(40)
        self.record = record
        self.field_names = field_names
        self.on_edit_cb = on_edit
        self.on_select_cb = on_select

        with self.canvas.before:
            Color(*bg_color)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.checkbox = CheckBox(size_hint_x=None, width=dp(40))
        self.checkbox.bind(active=self._on_check)
        self.add_widget(self.checkbox)

        self.cells = {}
        for field in field_names:
            val = str(record.get(field, ''))
            lbl = Label(text=val, color=(0,0,0,1), text_size=(None, None), halign='left')
            lbl.bind(size=lbl.setter('text_size'))
            self.cells[field] = lbl
            
            cell_box = BoxLayout()
            cell_box.add_widget(lbl)
            cell_box.bind(on_touch_down=lambda instance, touch, f=field, v=val: self._on_cell_touch(touch, f, v, instance))
            
            self.add_widget(cell_box)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _on_check(self, instance, value):
        if self.on_select_cb:
            self.on_select_cb(self.record, value)

    def _on_cell_touch(self, touch, field, value, cell_box):
        if cell_box.collide_point(*touch.pos):
            if touch.is_double_tap:
                self._edit_cell(field, value, cell_box)
                return True
        return False

    def _edit_cell(self, field, value, cell_box):
        cell_box.clear_widgets()
        ti = TextInput(text=value, multiline=False)
        
        def on_focus(instance, focused):
            if not focused:
                self._save_cell(field, ti.text, cell_box)
                
        def on_enter(instance):
            self._save_cell(field, ti.text, cell_box)
            
        ti.bind(focus=on_focus, on_text_validate=on_enter)
        cell_box.add_widget(ti)
        Clock.schedule_once(lambda dt: setattr(ti, 'focus', True), 0.1)

    def _save_cell(self, field, new_value, cell_box):
        cell_box.clear_widgets()
        lbl = Label(text=new_value, color=(0,0,0,1), text_size=(None, None), halign='left')
        lbl.bind(size=lbl.setter('text_size'))
        cell_box.add_widget(lbl)
        
        if self.on_edit_cb and str(self.record.get(field)) != new_value:
            self.on_edit_cb(self.record.get('id'), field, new_value)
            self.record[field] = new_value

class DataTable(BoxLayout):
    records = ListProperty([])
    field_names = ListProperty([])
    selected_records = ListProperty([])
    sort_field = StringProperty("")
    sort_order = StringProperty("ASC")
    on_record_selected = ObjectProperty(None)
    on_record_edited = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(DataTable, self).__init__(**kwargs)
        self.orientation = 'vertical'

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Header Area
        self.header_area = BoxLayout(size_hint_y=None, height=dp(40))
        self.add_widget(self.header_area)

        # Scrollable Grid Area
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=1)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll_view.add_widget(self.grid)
        self.add_widget(self.scroll_view)

        # Footer
        self.footer = BoxLayout(size_hint_y=None, height=dp(30), padding=dp(5))
        self.lbl_count = Label(text="0 rows", color=(0,0,0,1), halign='left')
        self.footer.add_widget(self.lbl_count)
        self.add_widget(self.footer)

        self.bind(records=self._on_data_change, field_names=self._on_data_change)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def load_records(self, records: list, field_names: list):
        self.field_names = field_names
        self.records = records

    def sort_by(self, field_name: str, asc: bool):
        self.sort_field = field_name
        self.sort_order = "ASC" if asc else "DESC"
        self.records.sort(key=lambda x: str(x.get(field_name, '')), reverse=not asc)
        self._build_rows()

    def select_all(self, instance, value):
        if value:
            self.selected_records = list(self.records)
        else:
            self.selected_records = []
        for row in self.grid.children:
            if isinstance(row, DataTableRow):
                row.checkbox.active = value

    def get_selected_records(self) -> list:
        return self.selected_records

    def get_selected_record_ids(self) -> list:
        return [r.get('id') for r in self.selected_records if 'id' in r]

    def _on_cell_edited(self, record_id, field_name, new_value):
        if self.on_record_edited:
            self.on_record_edited(record_id, field_name, new_value)

    def _on_row_selected(self, record, is_selected):
        if is_selected:
            if record not in self.selected_records:
                self.selected_records.append(record)
        else:
            if record in self.selected_records:
                self.selected_records.remove(record)
                
        if self.on_record_selected:
            self.on_record_selected(record)

    def refresh(self):
        self._build_header()
        self._build_rows()

    def _on_data_change(self, instance, value):
        self.refresh()
        self.lbl_count.text = f"{len(self.records)} rows"

    def _build_header(self):
        self.header_area.clear_widgets()
        
        cb_all = CheckBox(size_hint_x=None, width=dp(40))
        cb_all.bind(active=self.select_all)
        self.header_area.add_widget(cb_all)
        
        for field in self.field_names:
            h = DataTableHeader(text=field, on_sort=self.sort_by)
            self.header_area.add_widget(h)

    def _build_rows(self):
        self.grid.clear_widgets()
        for i, record in enumerate(self.records):
            bg_color = (1, 1, 1, 1) if i % 2 == 0 else (0.95, 0.95, 0.95, 1)
            row = DataTableRow(
                record=record,
                field_names=self.field_names,
                on_edit=self._on_cell_edited,
                on_select=self._on_row_selected,
                bg_color=bg_color
            )
            self.grid.add_widget(row)
