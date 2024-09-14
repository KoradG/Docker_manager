# swarm.py
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
            self.logger.log_error(f"Command failed with return code {e.returncode}: {e.stderr}")
            return f"Error: {e.stderr}"

    def deploy_service(self, service_name, image_name):
        """
        Deploy a Docker service.
        """
        try:
            command = ["docker", "service", "create", "--name", service_name, image_name]
            output = self.run_command(command)
            self.logger.log_info(f"Service '{service_name}' deployed with image '{image_name}'.")
            return f"Deploy Service Output:\n{output}"
        except Exception as e:
            self.logger.log_error(f"Error deploying service: {e}")
            return f"Error deploying service: {e}"

    def is_swarm_manager(self):
        """
        Check if the current node is a Swarm manager.
        """
        try:
            output = self.run_command(["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"])
            if "active" in output:
                self.logger.log_info("Docker Swarm manager status confirmed.")
                return True
            else:
                self.logger.log_error("Docker Swarm is not active or not a manager.")
                return False
        except Exception as e:
            self.logger.log_error(f"Error checking Swarm manager status: {e}")
            return False

    def initialize_swarm(self):
        try:
            output = self.run_command(["docker", "swarm", "init"])
            self.logger.log_info("Docker Swarm initialized successfully.")
            self.logger.log_info(output)
            return output
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Error initializing Docker Swarm: {e.stderr}")
            return f"Error initializing Docker Swarm: {e.stderr}"
        except Exception as e:
            self.logger.log_error(f"Unexpected error initializing Docker Swarm: {e}")
            return f"Unexpected error initializing Docker Swarm: {e}"

    def scale_service(self, service_name, replicas):
        """
        Scale a Docker service.
        """
        if not self.is_swarm_manager():
            return "This node is not a Swarm manager. Cannot scale service."

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

    def leave_swarm(self):
        """
        Make this node leave the Swarm.
        """
        if not self.is_swarm_manager():
            return "This node is not a Swarm manager. Cannot leave Swarm."

        try:
            output = self.run_command(["docker", "swarm", "leave", "--force"])
            self.logger.log_info("Node left the Swarm successfully.")
            self.logger.log_info(output)
            return output
        except subprocess.CalledProcessError as e:
            self.logger.log_error(f"Error leaving Swarm: {e.stderr}")
            return f"Error leaving Swarm: {e.stderr}"
        except Exception as e:
            self.logger.log_error(f"Unexpected error leaving Swarm: {e}")
            return f"Unexpected error leaving Swarm: {e}"

    def view_nodes(self):
        """
        View the nodes in Docker Swarm.
        """
        if not self.is_swarm_manager():
            return "This node is not a Swarm manager. Cannot view nodes."

        try:
            output = self.run_command(["docker", "node", "ls"])
            self.logger.log_info("Listed Swarm nodes.")
            return f"Swarm Nodes Output:\n{output}"
        except Exception as e:
            self.logger.log_error(f"Error viewing nodes: {e}")
            return f"Error viewing nodes: {e}"
