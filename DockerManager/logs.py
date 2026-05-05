# logs.py
import logging
import traceback
import os


# Configure logging
logging.basicConfig(
    filename='event_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class Logger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.find_folder()   # FIX: was self.find_folder without parentheses – never called

    def find_folder(self):
        """Check if the 'logs' folder exists; create it if it does not."""
        logs_folder = 'logs'
        if not os.path.exists(logs_folder):
            os.makedirs(logs_folder)
            self.log_info(f"'{logs_folder}' folder created.")
        else:
            self.log_info(f"'{logs_folder}' folder already exists.")

    def log_error(self, message):
        self.logger.error(message)
        self.logger.error("Traceback: %s", traceback.format_exc())

    def log_info(self, message):
        self.logger.info(message)

    def log_debug(self, message):
        self.logger.debug(message)