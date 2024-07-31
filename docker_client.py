import docker
import sys
import subprocess
import os

class DockerClient:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"Error connecting to Docker daemon: {e}", flush=True)
            sys.exit(1)

    def list_containers(self, all=True):
        try:
            return self.client.containers.list(all=all)
        except docker.errors.APIError as e:
            print(f"Error listing containers: {e}", flush=True)
            return []

    def create_container_from_dockerfile(self, dockerfile_path):
        try:
            if not os.path.isdir(dockerfile_path):
                raise ValueError(f"{dockerfile_path} is not a valid directory.")
            image, build_logs = self.client.images.build(path=dockerfile_path, tag="mydockerimage")
            container = self.client.containers.run(image, detach=True)
            return container
        except Exception as e:
            print(f"Error occurred while creating container: {e}", flush=True)
            return None

    def deploy_compose_file(self, compose_file_path):
        try:
            if not os.path.isfile(compose_file_path):
                raise ValueError(f"{compose_file_path} is not a valid file.")
            subprocess.check_call(f"docker-compose -f {compose_file_path} up -d", shell=True)
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while deploying Docker Compose file: {e}", flush=True)

    def perform_container_action(self, container, action_func, action_name):
        try:
            action_func()
            # Fetch updated container info after action
            updated_container = self.client.containers.get(container.id)
            print(f"Container {container.name} {action_name} successfully.", flush=True)
            return updated_container
        except docker.errors.APIError as e:
            print(f"Error occurred while {action_name} container: {e}", flush=True)
            return None

# Singleton pattern to ensure a single DockerClient instance
def get_docker_client():
    global client
    if 'client' not in globals():
        client = DockerClient()
    return client

# For direct usage (if needed)
client = get_docker_client()
