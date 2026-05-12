import json
import logging
from pathlib import Path
from datetime import datetime

class Logger:
    def __init__(self, logs_dir: Path = None):
        self.logs_dir = logs_dir or Path("data/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("job_search_agent")
        if not self._logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(self.logs_dir / "agent.log"),
                    logging.StreamHandler()
                ]
            )

    def info(self, message: str):
        self._logger.info(message)

    def warning(self, message: str):
        self._logger.warning(message)

    def error(self, message: str):
        self._logger.error(message)

    def debug(self, message: str):
        self._logger.debug(message)

    def log_error(self, session_id: str, error: str):
        error_log = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error
        }
        with open(self.logs_dir / f"error_{session_id}.json", "w") as f:
            json.dump(error_log, f)

    def log_success(self, session_id: str, job_id: str, status: str, screenshot_dir: Path):
        success_log = {
            "session_id": session_id,
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "screenshot_dir": str(screenshot_dir)
        }
        with open(self.logs_dir / f"success_{session_id}.json", "w") as f:
            json.dump(success_log, f)
