# logs.py
import logging
import traceback

# Configure logging
logging.basicConfig(filename='event_log.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Logger:
    def __init__(self):
        # Initialize the logger
        self.logger = logging.getLogger(__name__)

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
