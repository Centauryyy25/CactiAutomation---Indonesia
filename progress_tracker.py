# Di progress_tracker.py
from threading import Lock

class ProgressTracker:
    def __init__(self):
        self.lock = Lock()
        self.reset()
    
    def update(self, progress_type, updates):
        with self.lock:
            getattr(self, progress_type).update(updates)

# progress_tracker.py
class ProgressTracker:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reset()
        return cls._instance
    
    def reset(self):
        self.scraping = {
            'current': 0,
            'total': 1,
            'message': '',
            'status': 'idle',
            'current_file': ''
        }
        self.ocr = {
            'current': 0,
            'total': 1,
            'message': '',
            'status': 'idle',
            'current_file': ''
        }

progress = ProgressTracker()