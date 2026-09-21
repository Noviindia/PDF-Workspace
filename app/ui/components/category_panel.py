from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.treeview import TreeView, TreeViewLabel, TreeViewNode
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle
from kivy.properties import ListProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp, sp

class CategoryItem(BoxLayout, TreeViewNode):
    def __init__(self, category_data, on_select, **kwargs):
        super(CategoryItem, self).__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(30)
        self.category_data = category_data
        self.on_select_cb = on_select

        name = category_data.get('name', 'Unknown')
        count = category_data.get('count', 0)

        self.add_widget(Label(text="📁", size_hint_x=None, width=dp(30)))
        
        lbl_name = Label(text=name, color=(0,0,0,1), halign='left')
        lbl_name.bind(size=lbl_name.setter('text_size'))
        self.add_widget(lbl_name)
        
        self.add_widget(Label(text=str(count), size_hint_x=None, width=dp(40), color=(0.5, 0.5, 0.5, 1)))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_select_cb:
                self.on_select_cb(self.category_data)
            return True
        return super(CategoryItem, self).on_touch_down(touch)


class CategoryPanel(BoxLayout):
    categories = ListProperty([])
    on_category_selected = ObjectProperty(None)
    selected_category_id = NumericProperty(-1)

    def __init__(self, **kwargs):
        super(CategoryPanel, self).__init__(**kwargs)
        self.orientation = 'vertical'

        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(40), padding=dp(5))
        lbl_title = Label(text="Categories", color=(0,0,0,1), bold=True, halign='left')
        lbl_title.bind(size=lbl_title.setter('text_size'))
        btn_add = Button(text="+", size_hint_x=None, width=dp(30))
        btn_add.bind(on_release=lambda x: self.add_category())

        header.add_widget(lbl_title)
        header.add_widget(btn_add)
        self.add_widget(header)

        # Tree View
        self.scroll_view = ScrollView(size_hint=(1, 1))
        self.tree_view = TreeView(hide_root=True, size_hint_y=None)
        self.tree_view.bind(minimum_height=self.tree_view.setter('height'))
        self.scroll_view.add_widget(self.tree_view)
        self.add_widget(self.scroll_view)

        # Context actions
        self.actions_bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5), padding=dp(5))
        btn_ren = Button(text="Rename")
        btn_ren.bind(on_release=lambda x: self.rename_category(self.selected_category_id) if self.selected_category_id != -1 else None)
        btn_del = Button(text="Delete")
        btn_del.bind(on_release=lambda x: self.delete_category(self.selected_category_id) if self.selected_category_id != -1 else None)
        btn_mer = Button(text="Merge")
        btn_mer.bind(on_release=lambda x: self.merge_categories())
        
        self.actions_bar.add_widget(btn_ren)
        self.actions_bar.add_widget(btn_del)
        self.actions_bar.add_widget(btn_mer)
        self.add_widget(self.actions_bar)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def load_categories(self, categories: list):
        self.categories = categories
        self._build_tree()

    def _build_tree(self):
        for node in list(self.tree_view.iterate_all_nodes()):
            self.tree_view.remove_node(node)
            
        for cat in self.categories:
            item = CategoryItem(category_data=cat, on_select=self._on_category_clicked)
            self.tree_view.add_node(item)

    def add_category(self):
        print("Add category dialog")

    def rename_category(self, cat_id):
        print(f"Rename category {cat_id}")

    def delete_category(self, cat_id):
        print(f"Delete category {cat_id}")

    def merge_categories(self):
        print("Merge categories")

    def _on_category_clicked(self, category):
        self.selected_category_id = category.get('id', -1)
        if self.on_category_selected:
            self.on_category_selected(category)

    def refresh(self):
        self._build_tree()
