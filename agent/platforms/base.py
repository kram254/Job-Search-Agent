from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BasePlatformHandler(ABC):
    def __init__(self):
        self.session_id = None
        self.logger = None
        self.selected_cv_path = None

    @abstractmethod
    def detect(self, url: str, page_snapshot: str) -> bool:
        pass

    @abstractmethod
    def detect_login(self, page) -> bool:
        pass

    @abstractmethod
    def submit_application(self, browser):
        pass

    def get_human_filled_value(self, field_id: str) -> str:
        # Placeholder for retrieving values from HITL gate
        return ""
