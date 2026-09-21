from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, NumericProperty
from kivy.metrics import dp, sp

class StatusBar(BoxLayout):
    status_text = StringProperty("Ready")
    page_count = NumericProperty(0)
    record_count = NumericProperty(0)
    privacy_mode = StringProperty("Local Only")

    def __init__(self, **kwargs):
        super(StatusBar, self).__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(30)
        self.padding = [dp(10), 0]
        self.spacing = dp(10)

        with self.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.lbl_status = Label(text=self.status_text, color=(1,1,1,1), halign='left')
        self.lbl_status.bind(size=self.lbl_status.setter('text_size'))
        
        self.lbl_pages = Label(text=f"Pages: {self.page_count}", size_hint_x=None, width=dp(100), color=(0.8,0.8,0.8,1))
        self.lbl_records = Label(text=f"Records: {self.record_count}", size_hint_x=None, width=dp(120), color=(0.8,0.8,0.8,1))
        
        # Privacy badge
        self.privacy_badge = BoxLayout(size_hint_x=None, width=dp(100), padding=dp(2))
        with self.privacy_badge.canvas.before:
            Color(0.2, 0.6, 0.2, 1) # Green
            self.badge_rect = Rectangle(pos=self.privacy_badge.pos, size=self.privacy_badge.size)
        self.privacy_badge.bind(pos=self._update_badge_rect, size=self._update_badge_rect)
        
        lbl_privacy = Label(text=f"🔒 {self.privacy_mode}", color=(1,1,1,1), bold=True)
        self.privacy_badge.add_widget(lbl_privacy)

        self.add_widget(self.lbl_status)
        self.add_widget(self.lbl_pages)
        self.add_widget(self.lbl_records)
        self.add_widget(self.privacy_badge)

        self.bind(status_text=self._on_status_change)
        self.bind(page_count=self._on_counts_change)
        self.bind(record_count=self._on_counts_change)
        self.bind(privacy_mode=self._on_privacy_change)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        
    def _update_badge_rect(self, instance, value):
        self.badge_rect.pos = instance.pos
        self.badge_rect.size = instance.size

    def _on_status_change(self, instance, value):
        self.lbl_status.text = value

    def _on_counts_change(self, instance, value):
        self.lbl_pages.text = f"Pages: {self.page_count}"
        self.lbl_records.text = f"Records: {self.record_count}"

    def _on_privacy_change(self, instance, value):
        pass

    def update_status(self, text):
        self.status_text = text

    def update_counts(self, pages, records):
        self.page_count = pages
        self.record_count = records
