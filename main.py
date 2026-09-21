"""
PDF Workspace - Main Application Entry Point
A fully local, offline PDF workspace and converter application.
"""

import os
import sys

# Check platform and launch mode
IS_ANDROID = ('ANDROID_ARGUMENT' in os.environ or 'ANDROID_ENTRYPOINT' in os.environ)
USE_KIVY = '--kivy' in sys.argv or IS_ANDROID

if not USE_KIVY:
    try:
        from app.ui.desktop_app import run_desktop_app
        initial_pdf = None
        for arg in sys.argv[1:]:
            if not arg.startswith('-') and os.path.exists(arg):
                initial_pdf = arg
                break
        run_desktop_app(initial_pdf)
        sys.exit(0)
    except Exception as e:
        print(f"Desktop GUI error ({e}), attempting fallback...")

# Set environment before importing Kivy
os.environ['KIVY_LOG_LEVEL'] = 'info'

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.clock import Clock
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.utils import platform

# Try KivyMD for Material Design
try:
    from kivymd.app import MDApp
    HAS_KIVYMD = True
except ImportError:
    HAS_KIVYMD = False

from app.ui.screens.home_screen import HomeScreen
from app.ui.screens.processing_screen import ProcessingScreen
from app.ui.screens.workspace_screen import WorkspaceScreen
from app.ui.screens.export_screen import ExportScreen
from app.services.project_service import ProjectService
from app.services.processing_service import ProcessingService
from app.ui.theme import COLORS, get_color


class PDFWorkspaceApp(MDApp if HAS_KIVYMD else App):
    """Main PDF Workspace Application."""

    title = 'PDF Workspace'
    
    # Application state
    processing_service = ObjectProperty(None, allownone=True)
    current_project_path = StringProperty('')
    is_processing = BooleanProperty(False)
    privacy_label = StringProperty('🔒 Local Only')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_service = ProjectService()
        self.screen_manager = None

    def build(self):
        """Build the application UI."""
        # Configure theme
        if HAS_KIVYMD:
            self.theme_cls.theme_style = "Light"
            self.theme_cls.primary_palette = "Blue"
        
        # Set window properties for desktop development
        if platform not in ('android', 'ios'):
            Window.size = (1200, 800)
            Window.minimum_width = 800
            Window.minimum_height = 600
        
        # Create screen manager
        self.screen_manager = ScreenManager(transition=SlideTransition(duration=0.3))
        
        # Add screens
        self.screen_manager.add_widget(HomeScreen(name='home'))
        self.screen_manager.add_widget(ProcessingScreen(name='processing'))
        self.screen_manager.add_widget(WorkspaceScreen(name='workspace'))
        self.screen_manager.add_widget(ExportScreen(name='export'))
        
        # Bind keyboard shortcuts
        if platform not in ('android', 'ios'):
            Window.bind(on_keyboard=self._on_keyboard)
        
        return self.screen_manager

    def _on_keyboard(self, window, key, scancode, codepoint, modifier):
        """Handle keyboard shortcuts."""
        # Cmd/Ctrl modifier
        ctrl = 'meta' in modifier if platform == 'macosx' else 'ctrl' in modifier
        
        if ctrl:
            if codepoint == 'o':  # Open PDF
                self._open_file_chooser()
                return True
            elif codepoint == 'f':  # Focus search
                self._focus_search()
                return True
            elif codepoint == 's':  # Save project
                self._save_project()
                return True
            elif codepoint == 'e':  # Export
                self._show_export()
                return True
        
        if key == 27:  # Escape
            self._handle_escape()
            return True
        
        return False

    def open_pdf(self, file_path: str):
        """Import a PDF file and start processing."""
        if not os.path.exists(file_path):
            self._show_error(f"File not found: {file_path}")
            return
        
        if not file_path.lower().endswith('.pdf'):
            self._show_error("Please select a PDF file.")
            return
        
        # Create project directory
        pdf_name = os.path.splitext(os.path.basename(file_path))[0]
        
        if platform == 'android':
            from android.storage import app_storage_path  # type: ignore
            base_dir = app_storage_path()
        else:
            base_dir = os.path.join(os.path.expanduser('~'), '.pdfworkspace', 'projects')
        
        project_path = os.path.join(base_dir, pdf_name)
        
        # Handle duplicate names
        counter = 1
        original_path = project_path
        while os.path.exists(project_path):
            project_path = f"{original_path}_{counter}"
            counter += 1
        
        try:
            # Create project
            self.processing_service = self.project_service.create_project(
                project_path, name=pdf_name
            )
            self.current_project_path = project_path
            
            # Switch to processing screen
            self.screen_manager.current = 'processing'
            processing_screen = self.screen_manager.get_screen('processing')
            
            # Start async processing
            self.is_processing = True
            self.processing_service.import_pdf_async(
                file_path,
                progress_callback=lambda p: Clock.schedule_once(
                    lambda dt, prog=p: processing_screen.update_progress(prog), 0
                ),
                completion_callback=lambda doc_id, error=None: Clock.schedule_once(
                    lambda dt, d=doc_id, e=error: self._on_processing_complete(d, e), 0
                )
            )
            
            # Add to recent projects
            self.project_service.add_to_recent(project_path, pdf_name)
            
        except Exception as e:
            self._show_error(f"Failed to start processing: {str(e)}")

    def open_project(self, project_path: str):
        """Open an existing project."""
        try:
            self.processing_service = self.project_service.open_project(project_path)
            self.current_project_path = project_path
            
            # Go directly to workspace
            workspace = self.screen_manager.get_screen('workspace')
            workspace.load_workspace(self.processing_service)
            self.screen_manager.current = 'workspace'
            
            # Update recent
            name = os.path.basename(project_path)
            self.project_service.add_to_recent(project_path, name)
            
        except Exception as e:
            self._show_error(f"Failed to open project: {str(e)}")

    def _on_processing_complete(self, doc_id, error=None):
        """Called when PDF processing is complete."""
        self.is_processing = False
        
        if error:
            self._show_error(f"Processing failed: {str(error)}")
            self.screen_manager.current = 'home'
            return
        
        if doc_id is None:
            self._show_error("Processing was cancelled.")
            self.screen_manager.current = 'home'
            return
        
        # Load workspace
        workspace = self.screen_manager.get_screen('workspace')
        workspace.load_workspace(self.processing_service)
        self.screen_manager.current = 'workspace'

    def cancel_processing(self):
        """Cancel ongoing PDF processing."""
        if self.processing_service:
            self.processing_service.cancel_processing()
        self.is_processing = False

    def show_export(self):
        """Show the export screen."""
        if not self.processing_service:
            self._show_error("No document loaded.")
            return
        export_screen = self.screen_manager.get_screen('export')
        export_screen.load_export_options(self.processing_service)
        self.screen_manager.current = 'export'

    def go_home(self):
        """Navigate to home screen."""
        self.screen_manager.current = 'home'

    def go_workspace(self):
        """Navigate back to workspace."""
        if self.processing_service:
            self.screen_manager.current = 'workspace'

    def _open_file_chooser(self):
        """Open file chooser dialog."""
        current_screen = self.screen_manager.current
        if current_screen == 'home':
            home = self.screen_manager.get_screen('home')
            home.open_file_chooser()
        elif current_screen == 'workspace':
            workspace = self.screen_manager.get_screen('workspace')
            workspace.open_new_pdf()

    def _focus_search(self):
        """Focus the search bar."""
        if self.screen_manager.current == 'workspace':
            workspace = self.screen_manager.get_screen('workspace')
            workspace.focus_search()

    def _save_project(self):
        """Save current project."""
        if self.processing_service:
            try:
                repo = self.processing_service.get_repository()
                repo.set_meta('last_saved', 
                    __import__('datetime').datetime.now().isoformat())
                self._show_info("Project saved.")
            except Exception as e:
                self._show_error(f"Save failed: {str(e)}")

    def _show_export(self):
        """Show export screen."""
        self.show_export()

    def _handle_escape(self):
        """Handle escape key."""
        if self.screen_manager.current == 'export':
            self.go_workspace()
        elif self.screen_manager.current == 'processing' and self.is_processing:
            self.cancel_processing()

    def _show_error(self, message: str):
        """Show error message to user."""
        if HAS_KIVYMD:
            from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
            try:
                MDSnackbar(
                    MDSnackbarText(text=message),
                    y="24dp",
                    pos_hint={"center_x": 0.5},
                    size_hint_x=0.8,
                ).open()
            except Exception:
                print(f"ERROR: {message}")
        else:
            print(f"ERROR: {message}")

    def _show_info(self, message: str):
        """Show info message to user."""
        if HAS_KIVYMD:
            from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
            try:
                MDSnackbar(
                    MDSnackbarText(text=message),
                    y="24dp",
                    pos_hint={"center_x": 0.5},
                    size_hint_x=0.8,
                ).open()
            except Exception:
                print(f"INFO: {message}")
        else:
            print(f"INFO: {message}")

    def on_stop(self):
        """Clean up when app closes."""
        if self.processing_service:
            self.processing_service.close()

    def get_app_storage_path(self) -> str:
        """Get the application storage path."""
        if platform == 'android':
            from android.storage import app_storage_path  # type: ignore
            return app_storage_path()
        else:
            path = os.path.join(os.path.expanduser('~'), '.pdfworkspace')
            os.makedirs(path, exist_ok=True)
            return path


def main():
    """Run the PDF Workspace application."""
    PDFWorkspaceApp().run()


if __name__ == '__main__':
    main()
