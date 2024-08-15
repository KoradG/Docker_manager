import docker
import os
import logging
import traceback

# Configure logging
logging.basicConfig(filename='event_log.log', level=logging.ERROR,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class DockerClientError(Exception):
    """Custom exception for DockerClient errors."""
    pass

def handle_docker_api_error(func):
    """Decorator to handle Docker API errors."""
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except docker.errors.APIError as e:
            self.log_error(f"Error in {func.__name__}: {e}")
            raise DockerClientError(f"Error in {func.__name__}.") from e
    return wrapper

class DockerClient:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.log_error(f"Error connecting to Docker daemon: {e}")
            raise DockerClientError("Unable to connect to Docker daemon.")

    def log_error(self, message):
        logging.error(message)
        logging.error("Traceback: %s", traceback.format_exc())

    @handle_docker_api_error
    def list_containers(self, all=True):
        return self.client.containers.list(all=all)

    @handle_docker_api_error
    def create_image_from_dockerfile(self, dockerfile_path, tag):
        if not os.path.isdir(dockerfile_path):
            raise ValueError(f"{dockerfile_path} is not a valid directory.")
        try:
            image, build_logs = self.client.images.build(path=dockerfile_path, tag=tag, rm=True)
            for log in build_logs:
                if 'stream' in log:
                    print(log['stream'], end='', flush=True)
            print(f"Image built from Dockerfile and tagged as {tag}.", flush=True)
            return image
        except ValueError as e:
            self.log_error(f"Invalid Dockerfile path: {e}")
            raise
        except docker.errors.BuildError as e:
            self.log_error(f"Error building image from Dockerfile: {e}")
            raise DockerClientError("Error building image from Dockerfile.")
        except docker.errors.APIError as e:
            self.log_error(f"API Error while building image: {e}")
            raise DockerClientError("API Error while building image.")

    @handle_docker_api_error
    def create_container(self, image_name, command=None, env_vars=None, ports=None, volumes=None, network=None, extra_params=None):
        container = self.client.containers.create(
            image=image_name,
            command=command,
            environment=env_vars,
            ports=ports,
            volumes=volumes,
            network=network,
            detach=True,
            **(extra_params or {})
        )
        print(f"Container created with image {image_name}.", flush=True)
        return container

    @handle_docker_api_error
    def perform_container_action(self, container, action_func, action_name):
        action_func()
        updated_container = self.client.containers.get(container.id)
        print(f"Container {container.name} {action_name} successfully.", flush=True)
        return updated_container

    @handle_docker_api_error
    def start_container(self, container):
        return self.perform_container_action(container, container.start, "started")

    @handle_docker_api_error
    def stop_container(self, container):
        return self.perform_container_action(container, container.stop, "stopped")

    @handle_docker_api_error
    def pause_container(self, container):
        return self.perform_container_action(container, container.pause, "paused")

    @handle_docker_api_error
    def unpause_container(self, container):
        return self.perform_container_action(container, container.unpause, "unpaused")

    @handle_docker_api_error
    def restart_container(self, container):
        return self.perform_container_action(container, container.restart, "restarted")

    @handle_docker_api_error
    def remove_container(self, container):
        container.remove(v=True, force=True)
        print(f"Container {container.name} removed successfully.", flush=True)

    @handle_docker_api_error
    def inspect_container(self, container):
        return container.attrs

    @handle_docker_api_error
    def container_stats(self, container):
        return self.client.containers.get(container.id).stats(stream=False)

    # Image Management
    @handle_docker_api_error
    def list_images(self):
        images = self.client.images.list()
        return [{"id": img.id, "tags": img.tags if img.tags else []} for img in images]

    @handle_docker_api_error
    def remove_image(self, image_id):
        self.client.images.remove(image_id, force=True)
        print(f"Image {image_id} removed successfully.", flush=True)

    @handle_docker_api_error
    def tag_image(self, image_id, new_tag):
        image = self.client.images.get(image_id)
        image.tag(new_tag)
        print(f"Image {image_id} tagged with {new_tag}.", flush=True)

    @handle_docker_api_error
    def push_image(self, image_tag, username, password):
        self.client.images.push(image_tag, auth_config={'username': username, 'password': password})
        print(f"Image {image_tag} pushed successfully.", flush=True)

    @handle_docker_api_error
    def pull_image(self, image_name):
        self.client.images.pull(image_name)
        print(f"Image {image_name} pulled successfully.", flush=True)

    # Network Management
    @handle_docker_api_error
    def list_networks(self):
        return self.client.networks.list()

    @handle_docker_api_error
    def remove_network(self, network_id):
        self.client.networks.get(network_id).remove()
        print(f"Network {network_id} removed successfully.", flush=True)

    @handle_docker_api_error
    def inspect_network(self, network_id):
        if isinstance(network_id, str):
            return self.client.networks.get(network_id).attrs
        else:
            raise ValueError("Expected network_id to be a string")

    @handle_docker_api_error
    def create_network(self, network_name, driver=None, options=None):
        self.client.networks.create(name=network_name, driver=driver, **(options or {}))
        print(f"Network {network_name} created successfully.", flush=True)

    # Volume Management
    @handle_docker_api_error
    def list_volumes(self):
        volumes = self.client.volumes.list()
        return [{"name": volume.name, "driver": volume.attrs['Driver'], "mountpoint": volume.attrs['Mountpoint']} for volume in volumes]

    @handle_docker_api_error
    def create_volume(self, volume_name, driver=None, **options):
        self.client.volumes.create(name=volume_name, driver=driver, **options)
        print(f"Volume {volume_name} created successfully.", flush=True)

    @handle_docker_api_error
    def inspect_volume(self, volume_name):
        volume = self.client.volumes.get(volume_name)
        return volume.attrs

    @handle_docker_api_error
    def remove_volume(self, volume_name):
        self.client.volumes.get(volume_name).remove()
        print(f"Volume {volume_name} removed successfully.", flush=True)

    @handle_docker_api_error
    def prune_volumes(self):
        self.client.volumes.prune()
        print("Volumes pruned successfully.", flush=True)

class DockerClientSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DockerClientSingleton, cls).__new__(cls, *args, **kwargs)
            cls._instance.client = DockerClient()
        return cls._instance

    def get_client(self):
        return self.client

# Update the get_docker_client function
def get_docker_client():
    return DockerClientSingleton().get_client()
