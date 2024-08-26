import subprocess

class SwarmManager:
    def __init__(self, logger):
        self.logger = logger

    def run_command(self, command):
        """
        Run a shell command and return the output.
        """
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Error: {e.stderr}")
            return f"Error: {e.stderr}"

    def is_swarm_initialized(self):
        """
        Check if the Docker Swarm is already initialized.
        """
        try:
            output = self.run_command(["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"])
            if "active" in output:
                self.logger.log_info("Docker Swarm is already initialized.")
                return True
            return False
        except Exception as e:
            self.logger.log_error(f"Error checking Swarm status: {e}")
            return False

    def initialize_swarm(self):
        """
        Initialize Docker Swarm if it hasn't been initialized yet.
        """
        try:
            if not self.is_swarm_initialized():
                output = self.run_command(["docker", "swarm", "init"])
                self.logger.log_info("Docker Swarm initialized successfully.")
                self.logger.log_info(output)
                return output
            else:
                return "Swarm is already initialized."
        except Exception as e:
            self.logger.log_error(f"Error initializing Docker Swarm: {e}")
            return f"Error initializing Docker Swarm: {e}"

    def scale_service(self, service_name, replicas):
        """
        Scale a Docker service.
        """
        try:
            if not service_name or not replicas:
                self.logger.log_error("Service name and number of replicas are required.")
                return "Service name and number of replicas are required."

            command = ["docker", "service", "scale", f"{service_name}={replicas}"]
            output = self.run_command(command)
            
            if "no such service" in output.lower():
                self.logger.log_error(f"Service '{service_name}' not found.")
                return f"Error: Service '{service_name}' not found."

            self.logger.log_info(f"Service '{service_name}' scaled to {replicas} replicas.")
            self.logger.log_info(output)
            return output

        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Error scaling service '{service_name}': {e.stderr}")
            self.logger.log_error(f"Command output: {e.output}")
            self.logger.log_error(f"Return code: {e.returncode}")
            return f"Error scaling service: {e.stderr}"
        except Exception as e:
            self.logger.log_error(f"Unexpected error scaling service '{service_name}': {e}")
            return f"Unexpected error scaling service: {e}"



    def scale_service(self, service_name, replicas):
        """
        Scale a Docker service.
        """
        try:
            if not service_name or not replicas:
                return "Service Name and Number of Replicas are required."
            command = ["docker", "service", "scale", f"{service_name}={replicas}"]
            output = self.run_command(command)
            self.logger.log_info(f"Service '{service_name}' scaled to {replicas} replicas.")
            return f"Scale Service Output:\n{output}"
        except Exception as e:
            self.logger.log_error(f"Error scaling service: {e}")
            return f"Error scaling service: {e}"

    def view_nodes(self):
        """
        View the nodes in Docker Swarm.
        """
        try:
            output = self.run_command(["docker", "node", "ls"])
            self.logger.log_info("Listed Swarm nodes.")
            return f"Swarm Nodes Output:\n{output}"
        except Exception as e:
            self.logger.log_error(f"Error viewing nodes: {e}")
            return f"Error viewing nodes: {e}"
