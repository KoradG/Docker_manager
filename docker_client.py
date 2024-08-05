import docker
import sys
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

    def perform_container_action(self, container, action_func, action_name):
        try:
            action_func()
            updated_container = self.client.containers.get(container.id)
            print(f"Container {container.name} {action_name} successfully.", flush=True)
            return updated_container
        except docker.errors.APIError as e:
            print(f"Error occurred while {action_name} container: {e}", flush=True)
            return None

    def start_container(self, container):
        try:
            container.start()
        except docker.errors.APIError as e:
            print(f"Error starting container: {e}", flush=True)

    def stop_container(self, container):
        try:
            container.stop()
        except docker.errors.APIError as e:
            print(f"Error stopping container: {e}", flush=True)


    def pause_container(self, container):
        try:
            container.pause()
        except docker.errors.APIError as e:
            print(f"Error pausing container: {e}", flush=True)

    def unpause_container(self, container):
        try:
            container.unpause()
        except docker.errors.APIError as e:
            print(f"Error unpausing container: {e}", flush=True)

    def restart_container(self, container):
        try:
            container.restart()
        except docker.errors.APIError as e:
            print(f"Error restarting container: {e}", flush=True)

    def remove_container(self, container):
        try:
            container.remove(v=True, force=True)
        except docker.errors.APIError as e:
            print(f"Error removing container: {e}", flush=True)

    def inspect_container(self, container):
        try:
            return container.attrs
        except docker.errors.APIError as e:
            print(f"Error inspecting container: {e}", flush=True)
            return {}

    def container_stats(self, container):
        try:
            return self.client.containers.get(container.id).stats(stream=False)
        except docker.errors.APIError as e:
            print(f"Error retrieving container stats: {e}", flush=True)
            return {}

    # Image Management
    def list_images(self):
        try:
            images = self.client.images.list()
            return [{"id": img.id, "tags": img.tags if img.tags else []} for img in images]
        except docker.errors.APIError as e:
            print(f"Error listing images: {e}", flush=True)
            return []


    def remove_image(self, image_id):
            try:
                self.client.images.remove(image_id, force=True)
                print(f"Image {image_id} removed successfully.", flush=True)
            except docker.errors.APIError as e:
                print(f"Error removing image: {e}", flush=True)

    def tag_image(self, image_id, new_tag):
        try:
            image = self.client.images.get(image_id)
            image.tag(new_tag)
            print(f"Image {image_id} tagged with {new_tag}.", flush=True)
        except docker.errors.APIError as e:
            print(f"Error tagging image: {e}", flush=True)

    def push_image(self, image_tag, username, password):
        try:
            self.client.images.push(image_tag, auth_config={'username': username, 'password': password})
            print(f"Image {image_tag} pushed successfully.", flush=True)
        except docker.errors.APIError as e:
            print(f"Error pushing image: {e}", flush=True)

    def pull_image(self, image_name):
        try:
            self.client.images.pull(image_name)
            print(f"Image {image_name} pulled successfully.", flush=True)
        except docker.errors.APIError as e:
            print(f"Error pulling image: {e}", flush=True)

        
    # Network Management
    def list_networks(self):
        return self.client.networks.list()

    def remove_network(self, network_id):
        self.client.networks.get(network_id).remove()

    def inspect_network(self, network_id):
        if isinstance(network_id, str):
            return self.client.networks.get(network_id).attrs
        else:
            raise ValueError("Expected network_id to be a string")
        
    def create_network(self, network_name, driver=None):
        try:
            self.client.networks.create(name=network_name, driver=driver)
        except docker.errors.APIError as e:
            print(f"Error creating network: {e}", flush=True)


    # Volume Management
    def list_volumes(self):
        try:
            volumes = self.client.volumes.list()
            return [{"name": volume.name, "driver": volume.attrs['Driver'], "mountpoint": volume.attrs['Mountpoint']} for volume in volumes]
        except docker.errors.APIError as e:
            print(f"Error listing volumes: {e}", flush=True)
            return []
        
    def create_volume(self, volume_name, driver=None, **options):
        try:
            self.client.volumes.create(name=volume_name, driver=driver, **options)
        except docker.errors.APIError as e:
            print(f"Error creating volume: {e}", flush=True)

    def inspect_volume(self, volume_name):
        try:
            volume = self.client.volumes.get(volume_name)
            return volume.attrs
        except docker.errors.APIError as e:
            print(f"Error inspecting volume: {e}", flush=True)
            return {}

    def remove_volume(self, volume_name):
        try:
            self.client.volumes.get(volume_name).remove()
        except docker.errors.APIError as e:
            print(f"Error removing volume: {e}", flush=True)

    def prune_volumes(self):
        try:
            self.client.volumes.prune()
        except docker.errors.APIError as e:
            print(f"Error pruning volumes: {e}", flush=True)

    def build_image_from_dockerfile(self, dockerfile_path, tag):
        try:
            if not os.path.isdir(dockerfile_path):
                raise ValueError(f"{dockerfile_path} is not a valid directory.")
            self.client.images.build(path=dockerfile_path, tag=tag)
        except Exception as e:
            print(f"Error building image from Dockerfile: {e}", flush=True)

    def create_container(self, image_name, command, env_vars, ports, volumes, network):
        try:
            container = self.client.containers.create(
                image=image_name,
                command=command,
                environment=env_vars,
                ports=ports,
                volumes=volumes,
                network=network,
                detach=True
            )
            return container
        except docker.errors.APIError as e:
            print(f"Error creating container: {e}", flush=True)
            return None

    def exec_command_in_container(self, container, command):
        try:
            exec_instance = self.client.api.exec_create(container.id, command)
            output = self.client.api.exec_start(exec_instance)
            return output
        except docker.errors.APIError as e:
            print(f"Error executing command in container: {e}", flush=True)
            return ""

def get_docker_client():
    global client
    if 'client' not in globals():
        client = DockerClient()
    return client

client = get_docker_client()
