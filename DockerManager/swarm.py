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

    def initialize_swarm(self):
        """
        Initialize Docker Swarm.
        """
        try:
            output = self.run_command(["docker", "swarm", "init"])
            self.logger.log_info("Docker Swarm initialized successfully.")
            self.logger.log_info(output)
            return output
        except Exception as e:
            self.logger.log_error(f"Error initializing Docker Swarm: {e}")
            return f"Error initializing Docker Swarm: {e}"
        
    def deploy_service(self, service_name, image_name):
        """
        Deploy a Docker service.
        """
        try:
            if service_name and image_name:
                output = self.run_command(["docker", "service", "create", "--name", service_name, image_name])
                self.logger.log_info(f"Service '{service_name}' deployed successfully.")
                self.logger.log_info(output)
                return output
            else:
                return "Service name and image name are required."
        except Exception as e:
            self.logger.log_error(f"Error deploying service: {e}")
            return f"Error deploying service: {e}"

    def scale_service(self, service_name, replicas):
        """
        Scale a Docker service.
        """
        try:
            if not service_name or not replicas:
                return "Service Name and Number of Replicas are required."
            command = ["docker", "service", "scale", f"{service_name}={replicas}"]
            output = self.run_command(command)
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
            return f"Swarm Nodes Output:\n{output}"
        except Exception as e:
            self.logger.log_error(f"Error viewing nodes: {e}")
            return f"Error viewing nodes: {e}"
