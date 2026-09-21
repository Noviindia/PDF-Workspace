import os
import json
from typing import Optional, List, Dict
from datetime import datetime

class ProjectService:
    """
    Project management service.
    """

    def __init__(self):
        """
        Initialize the project service.
        """
        config_dir = os.environ.get('PDFWORKSPACE_DIR')
        if not config_dir:
            try:
                base = os.path.expanduser('~')
                config_dir = os.path.join(base, '.pdfworkspace')
                os.makedirs(config_dir, exist_ok=True)
            except (PermissionError, OSError):
                config_dir = os.path.join(os.getcwd(), '.pdfworkspace')
                os.makedirs(config_dir, exist_ok=True)
        else:
            os.makedirs(config_dir, exist_ok=True)

        self._config_dir = config_dir
        self._recent_file = os.path.join(self._config_dir, 'recent.json')


    def create_project(self, project_path: str, name: str = '') -> 'ProcessingService':
        """
        Create a new project directory structure and initialize the processing service.
        
        Args:
            project_path (str): The absolute path to the new project.
            name (str): The name of the project.
            
        Returns:
            ProcessingService: An initialized processing service for the new project.
        """
        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, 'source'), exist_ok=True)
        os.makedirs(os.path.join(project_path, 'exports'), exist_ok=True)
        
        self.add_to_recent(project_path, name or os.path.basename(project_path))
        
        from app.services.processing_service import ProcessingService
        return ProcessingService(project_path)

    def open_project(self, project_path: str) -> 'ProcessingService':
        """
        Open an existing project and initialize its processing service.
        
        Args:
            project_path (str): The absolute path to the existing project.
            
        Returns:
            ProcessingService: An initialized processing service for the project.
            
        Raises:
            ValueError: If the project path or database does not exist.
        """
        if not os.path.exists(project_path):
            raise ValueError(f"Project path does not exist: {project_path}")
            
        if not self.is_valid_project(project_path):
            raise ValueError(f"Valid project not found at: {project_path}")
            
        self.add_to_recent(project_path, os.path.basename(project_path))
        
        from app.services.processing_service import ProcessingService
        return ProcessingService(project_path)

    def get_recent_projects(self, max_count: int = 10) -> List[Dict]:
        """
        Get a list of recently opened projects.
        
        Args:
            max_count (int): Maximum number of recent projects to return.
            
        Returns:
            List[Dict]: List of dictionaries containing path, name, and last_opened.
        """
        if not os.path.exists(self._recent_file):
            return []
            
        try:
            with open(self._recent_file, 'r', encoding='utf-8') as f:
                projects = json.load(f)
                
            # Filter out projects whose paths no longer exist
            valid_projects = [p for p in projects if os.path.exists(p.get('path', ''))]
            
            # If some projects were filtered out, save the updated list
            if len(valid_projects) != len(projects):
                self._save_recent_projects(valid_projects)
                
            return valid_projects[:max_count]
        except (json.JSONDecodeError, IOError):
            return []

    def add_to_recent(self, project_path: str, name: str) -> None:
        """
        Add a project to the recent projects list.
        
        Args:
            project_path (str): The path to the project.
            name (str): The name of the project.
        """
        projects = []
        if os.path.exists(self._recent_file):
            try:
                with open(self._recent_file, 'r', encoding='utf-8') as f:
                    projects = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
                
        # Remove if already exists to update its timestamp and move to top
        projects = [p for p in projects if p.get('path') != project_path]
        
        projects.insert(0, {
            'path': project_path,
            'name': name,
            'last_opened': datetime.now().isoformat()
        })
        
        # Keep max 20 entries
        projects = projects[:20]
        self._save_recent_projects(projects)
        
    def _save_recent_projects(self, projects: List[Dict]) -> None:
        """
        Save the recent projects list to disk.
        
        Args:
            projects (List[Dict]): The list of recent projects.
        """
        try:
            with open(self._recent_file, 'w', encoding='utf-8') as f:
                json.dump(projects, f, indent=2)
        except IOError:
            pass

    def is_valid_project(self, path: str) -> bool:
        """
        Check if a given path is a valid project directory.
        
        Args:
            path (str): The path to check.
            
        Returns:
            bool: True if valid, False otherwise.
        """
        return os.path.exists(os.path.join(path, 'project.db'))
