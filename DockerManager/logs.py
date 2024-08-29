# logs.py
import logging
import traceback
import sys
import os


# Configure logging
logging.basicConfig(filename='event_log.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Logger:
    def __init__(self):
        # Initialize the logger
        self.find_folder
        self.logger = logging.getLogger(__name__)

        
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


    def handle_docker_api_error(func):
        """Decorator to handle Docker API errors."""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except docker.errors.APIError as e:
                self.log_error(f"Error in {func.__name__}: {e}")
                raise DockerClientError(f"Error in {func.__name__}.") from e
        return wrapper
