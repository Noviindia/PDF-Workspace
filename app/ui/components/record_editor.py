from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.properties import DictProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp, sp

class RecordEditor(Popup):
    record_data = DictProperty({})
    record_id = NumericProperty(-1)
    on_save = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(RecordEditor, self).__init__(**kwargs)
        self.title = "Edit Record"
        self.size_hint = (0.8, 0.8)
        
        self.main_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.form_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.form_layout.bind(minimum_height=self.form_layout.setter('height'))
        self.scroll_view.add_widget(self.form_layout)
        
        self.main_layout.add_widget(self.scroll_view)
        
        # Buttons
        btn_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=lambda x: self._cancel())
        
        btn_save = Button(text="Save", background_color=(0.2, 0.6, 0.2, 1))
        btn_save.bind(on_release=lambda x: self._save())
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
        
        self.main_layout.add_widget(btn_layout)
        self.content = self.main_layout

        self.inputs = {}

    def load_record(self, record_id, data_dict, original_text=''):
        self.record_id = record_id
        self.record_data = data_dict
        self.form_layout.clear_widgets()
        self.inputs = {}

        if original_text:
            orig_lbl = Label(
                text=f"Original Text:\n{original_text}",
                color=(0.7, 0.7, 0.7, 1),
                text_size=(self.width - dp(40), None),
                halign='left',
                size_hint_y=None
            )
            orig_lbl.bind(texture_size=orig_lbl.setter('size'))
            self.form_layout.add_widget(orig_lbl)

        for key, value in data_dict.items():
            if key == 'id' or key.startswith('_'):
                continue
                
            field_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(60))
            
            lbl_color = (1,1,1,1)
            lbl_text = key.capitalize()
            
            if isinstance(value, dict) and value.get('confidence', 1.0) < 0.8:
                lbl_color = (1, 0.6, 0, 1) # Orange
                lbl_text += " ⚠ Low confidence"
                val = str(value.get('value', ''))
            else:
                val = str(value)
                
            lbl = Label(text=lbl_text, color=lbl_color, halign='left', size_hint_y=None, height=dp(20))
            lbl.bind(size=lbl.setter('text_size'))
            field_box.add_widget(lbl)
            
            ti = TextInput(text=val, multiline=False, size_hint_y=None, height=dp(35))
            self.inputs[key] = ti
            field_box.add_widget(ti)
            
            self.form_layout.add_widget(field_box)

    def _save(self):
        updated_data = {}
        for key, ti in self.inputs.items():
            updated_data[key] = ti.text
            
        if self.on_save:
            self.on_save(self.record_id, updated_data)
        self.dismiss()

    def _cancel(self):
        self.dismiss()
