from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.app import App

class ProcessingScreen(Screen):
    """
    ProcessingScreen displays the status of PDF analysis.
    """
    current_step = NumericProperty(0)
    total_pages = NumericProperty(100)
    current_page = NumericProperty(0)
    percentage = NumericProperty(0)
    steps_status = ListProperty([0, 0, 0, 0, 0, 0]) # 0: pending, 1: current, 2: completed

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'processing'
        self.steps = [
            'Reading PDF', 
            'Detecting pages', 
            'Extracting text', 
            'Detecting tables', 
            'Detecting sections', 
            'Building search index'
        ]
        
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        main_layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        
        # Title
        title_label = Label(
            text="Analyzing document...", 
            font_size=sp(24), 
            bold=True, 
            color=(0.1, 0.1, 0.1, 1),
            size_hint=(1, 0.2)
        )
        main_layout.add_widget(title_label)

        # Steps Layout
        self.steps_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint=(1, 0.5))
        self.step_labels = []
        for step in self.steps:
            lbl = Label(
                text=f"○ {step}", 
                font_size=sp(16), 
                color=(0.4, 0.4, 0.4, 1),
                halign='left',
                valign='middle'
            )
            lbl.bind(size=lbl.setter('text_size'))
            self.step_labels.append(lbl)
            self.steps_layout.add_widget(lbl)
            
        main_layout.add_widget(self.steps_layout)

        # Progress Area
        progress_area = BoxLayout(orientation='vertical', size_hint=(1, 0.2), spacing=dp(10))
        
        self.page_label = Label(
            text="Processing page 0 / 0", 
            color=(0.2, 0.2, 0.2, 1),
            font_size=sp(14)
        )
        
        progress_bar_box = BoxLayout(orientation='horizontal', spacing=dp(10))
        self.progress_bar = ProgressBar(max=100, value=0, size_hint_x=0.8)
        self.percentage_label = Label(text="0%", color=(0.1, 0.1, 0.1, 1), size_hint_x=0.2)
        
        progress_bar_box.add_widget(self.progress_bar)
        progress_bar_box.add_widget(self.percentage_label)
        
        progress_area.add_widget(self.page_label)
        progress_area.add_widget(progress_bar_box)
        main_layout.add_widget(progress_area)

        # Cancel Button
        btn_box = BoxLayout(size_hint=(1, 0.1), padding=[dp(50), 0])
        cancel_btn = Button(
            text="Cancel", 
            size_hint=(None, None), 
            size=(dp(120), dp(40)),
            pos_hint={'center_x': 0.5}
        )
        cancel_btn.bind(on_release=self._cancel_processing)
        btn_box.add_widget(cancel_btn)
        main_layout.add_widget(btn_box)

        self.add_widget(main_layout)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_steps_status(self, instance, value):
        """Update labels when step statuses change."""
        for i, status in enumerate(value):
            if i < len(self.step_labels):
                lbl = self.step_labels[i]
                step_text = self.steps[i]
                if status == 2:
                    lbl.text = f"✓ {step_text}"
                    lbl.color = (0.2, 0.7, 0.2, 1) # Green
                elif status == 1:
                    lbl.text = f"● {step_text}..."
                    lbl.color = (0.2, 0.4, 0.8, 1) # Blue
                else:
                    lbl.text = f"○ {step_text}"
                    lbl.color = (0.4, 0.4, 0.4, 1) # Grey

    def update_progress(self, progress):
        """
        Updates UI based on progress object (dict or specific class).
        """
        if hasattr(progress, 'step_index'):
            step_idx = progress.step_index
            self.current_page = progress.page
            self.total_pages = progress.total_pages
            self.percentage = progress.percent
        else:
            step_idx = progress.get('step_index', 0)
            self.current_page = progress.get('page', 0)
            self.total_pages = progress.get('total_pages', 0)
            self.percentage = progress.get('percent', 0)

        new_status = [0] * len(self.steps)
        for i in range(len(self.steps)):
            if i < step_idx:
                new_status[i] = 2
            elif i == step_idx:
                new_status[i] = 1
            else:
                new_status[i] = 0
        self.steps_status = new_status

        self.page_label.text = f"Processing page {self.current_page} / {self.total_pages}"
        self.progress_bar.value = self.percentage
        self.percentage_label.text = f"{int(self.percentage)}%"

    def _cancel_processing(self, instance):
        app = App.get_running_app()
        if hasattr(app, 'cancel_processing'):
            app.cancel_processing()
