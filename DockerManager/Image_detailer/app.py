from flask import Flask, request, render_template, jsonify, send_file, abort
import subprocess
import json
import docker
import plotly.graph_objs as go
import plotly.io as pio
import threading 
import requests


app = Flask(__name__)



class ImageD():
    def __init__(self):
        self.server_thread = None
        self.server_running = threading.Event()

    def image_details(self):
        """Start the Flask server if it's not already running and print URL."""
        print("Open http://localhost:5000 for image details!")
        
        if not self.server_running.is_set():  # Check if the server is already running
            self.run_image_detailer()

    def run_image_detailer(self):
        """Start the Flask server in a separate thread."""
        if not self.server_running.is_set():  # Only start the server if it's not already running
            self.server_thread = threading.Thread(target=self.start_flask_app)
            self.server_thread.daemon = True  # Ensure the server thread exits when the main thread exits
            self.server_thread.start()
            self.server_running.set()  # Indicate that the server is now running
            print("Flask server started.")

    def start_flask_app(self):
        """Run the Flask app."""
        app.run(debug=False, use_reloader=False)

    def stop_image_detailer(self):
        """Stop the Flask server by sending a shutdown request."""
        if self.server_running.is_set():
            try:
                requests.post('http://localhost:5000/shutdown')
                print("Shutdown request sent to Flask server.")
            except requests.exceptions.RequestException as e:
                print(f"Error shutting down server: {e}")
            finally:
                self.server_running.clear()  # Mark the server as stopped

    def closeEvent(self, event):
        """Stop the Flask server when the GUI is closed."""
        self.stop_image_detailer()
        if self.server_thread is not None:
            self.server_thread.join()  # Wait for the server thread to finish
        event.accept()

    def get_docker_images():
        try:
            # Run the 'docker images' command to list available images
            result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Error fetching images: {result.stderr}")
            
            # Split the output by newline to create a list of images
            images = result.stdout.splitlines()
            return images
        except Exception as e:
            print(f"Error fetching Docker images: {e}")
            return []


    def get_image_history(image_name):
        try:
            history_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}} {{{{.Size}}}} {{{{.CreatedAt}}}}' {image_name}"
            history_output = subprocess.check_output(history_cmd, shell=True).decode().splitlines()
            layers = []
            for line in history_output:
                parts = line.rsplit(' ', 2)
                if len(parts) == 3:
                    command, size, created_at = parts
                    size = size.strip()  # Remove any unnecessary characters
                    layers.append({
                        "command": command.strip(),
                        "size": size.strip(),
                        "created_at": created_at.strip()
                    })
                else:
                    layers.append({
                        "command": line.strip(),
                        "size": "N/A",
                        "created_at": "N/A"
                    })
            return layers
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving image history: {e}")
            return None

    def get_final_layer_size(image_name):
        """Retrieve the size of the final layer in the Docker image."""
        try:
            history_cmd = f"docker history --no-trunc --format '{{{{.Size}}}}' {image_name}"
            history_output = subprocess.check_output(history_cmd, shell=True).decode().splitlines()
            if history_output:
                return history_output[-1].strip()  # Remove any unnecessary characters
            else:
                return "N/A"
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving final layer size: {e}")
            return "N/A"
        

    def get_image_history(image_name):
        try:
            history_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}} {{{{.Size}}}} {{{{.CreatedAt}}}}' {image_name}"
            history_output = subprocess.check_output(history_cmd, shell=True).decode().splitlines()
            layers = []
            for line in history_output:
                parts = line.rsplit(' ', 2)
                if len(parts) == 3:
                    command, size, created_at = parts
                    size = size.strip()  # Remove any unnecessary characters
                    layers.append({
                        "command": command.strip(),
                        "size": size.strip(),
                        "created_at": created_at.strip()
                    })
                else:
                    layers.append({
                        "command": line.strip(),
                        "size": "N/A",
                        "created_at": "N/A"
                    })
            return layers
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving image history: {e}")
            return None


@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Flask server gracefully."""
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/image', methods=['GET', 'POST'])
def image():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        layers = ImageD.get_image_history(image_name)
        if layers is None:
            return "Error retrieving image history", 500

        final_layer_size = ImageD.get_final_layer_size(image_name)
        if final_layer_size is None:
            final_layer_size = "N/A"

        return render_template('image.html', image_name=image_name, layers=layers, final_layer_size=final_layer_size)
    return render_template('image.html')

@app.route('/images')
def images_list():
    """Retrieve and display a list of Docker images."""
    try:
        images_cmd = "docker images --format '{{.Repository}}:{{.Tag}}'"
        images_output = subprocess.check_output(images_cmd, shell=True).decode().splitlines()
        images = [image for image in images_output]
        return render_template('images_list.html', images=images)
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving Docker images: {e}")
        return "Error retrieving images", 500


@app.route('/image_size_breakdown', methods=['GET', 'POST'])
def image_size_breakdown():
    image_name = None
    layers = []
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name = request.form.get('image_name')
    elif request.method == 'GET':
        image_name = request.args.get('image_name')

    if image_name:
        try:
            history_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}} {{{{.Size}}}} {{{{.CreatedAt}}}}' {image_name}"
            history_output = subprocess.check_output(history_cmd, shell=True).decode().splitlines()
            for line in history_output:
                parts = line.rsplit(' ', 2)
                if len(parts) == 3:
                    command, size, created_at = parts
                    layers.append({
                        "command": command.strip(),
                        "size": size.strip(),
                        "created_at": created_at.strip()
                    })
                else:
                    layers.append({
                        "command": line.strip(),
                        "size": "N/A",
                        "created_at": "N/A"
                    })
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving size breakdown: {e}")
            return "Error retrieving size breakdown", 500

    return render_template('image_size_breakdown.html', 
                        image_name=image_name, 
                        layers=layers,
                        available_images=available_images)


@app.route('/environment_variables', methods=['GET', 'POST'])
def environment_variables():
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    env_vars = None
    image_name = None

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            env_cmd = f"docker inspect --format '{{{{.Config.Env}}}}' {image_name}"
            env_output = subprocess.check_output(env_cmd, shell=True).decode()
            env_vars = [var.strip() for var in env_output.split('[')[-1].strip(']').split(',')]
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving environment variables: {e}")
            return "Error retrieving environment variables", 500
        except Exception as e:
            print(f"Unexpected error: {e}")
            return "Unexpected error", 500

    return render_template('environment_variables.html', 
                        image_name=image_name, 
                        env_vars=env_vars, 
                        available_images=available_images)

@app.route('/layer_comparison', methods=['GET', 'POST'])
def layer_comparison():
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name1 = request.form.get('image_name1')
        image_name2 = request.form.get('image_name2')
        if not image_name1 or not image_name2:
            return "Both image names are required", 400

        try:
            layers1 = self.get_image_history(image_name1)
            layers2 = self.get_image_history(image_name2)
            if layers1 is None or layers2 is None:
                return "Error retrieving image history", 500

            return render_template('layer_comparison.html', 
                                image_name1=image_name1, 
                                image_name2=image_name2, 
                                layers1=layers1, 
                                layers2=layers2, 
                                available_images=available_images)
        except Exception as e:
            print(f"Error comparing layers: {e}")
            return "Error comparing layers", 500

    return render_template('layer_comparison.html', available_images=available_images)


@app.route('/interactive_visualizations', methods=['GET', 'POST'])
def interactive_visualizations():
    image_name = None
    plot_html = None
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            layers = ImageD.get_image_history(image_name)
            if layers is None:
                return "Error retrieving image history", 500

            sizes = []
            commands = []
            for i, layer in enumerate(layers):
                size_str = layer['size']
                if 'MB' in size_str:
                    try:
                        size = float(size_str.replace('MB', '').strip())
                        sizes.append(size)
                    except ValueError:
                        sizes.append(0)
                else:
                    sizes.append(0)
                commands.append(f"Layer {i + 1}")

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=commands,
                x=sizes,
                orientation='h',
                text=sizes,
                textposition='outside',
                marker=dict(color='#007bff', line=dict(color='#0056b3', width=1.5))
            ))

            fig.update_layout(
                title=f'Layer Sizes for {image_name}',
                xaxis_title='Size (MB)',
                yaxis_title='Layer',
                xaxis=dict(
                    title_font=dict(size=14, family='Arial, sans-serif'),
                    tickfont=dict(size=12, family='Arial, sans-serif')
                ),
                yaxis=dict(
                    title_font=dict(size=14, family='Arial, sans-serif'),
                    tickfont=dict(size=12, family='Arial, sans-serif')
                ),
                plot_bgcolor='white',
                paper_bgcolor='#f9f9f9',
                margin=dict(l=40, r=40, t=40, b=40),
                height=600
            )

            graph_html = pio.to_html(fig, full_html=False)

            return render_template('interactive_visualizations.html', 
                                image_name=image_name, 
                                plot_html=graph_html, 
                                available_images=available_images)
        except Exception as e:
            print(f"Error generating visualizations: {e}")
            return "Error generating visualizations", 500

    return render_template('interactive_visualizations.html', available_images=available_images)


@app.route('/logs_build_info', methods=['GET', 'POST'])
def logs_build_info():
    image_name = None
    logs = None
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            logs_cmd = f"docker history {image_name}"
            logs_output = subprocess.check_output(logs_cmd, shell=True).decode()
            logs = logs_output
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving logs/build info: {e}")
            return "Error retrieving logs/build info", 500

    return render_template('logs_build_info.html', image_name=image_name, logs=logs, available_images=available_images)



@app.route('/api/image', methods=['POST'])
def image_api():
    image_name = request.json.get('image_name')
    if not image_name:
        return jsonify({"error": "Image name is required"}), 400

    layers = ImageD.get_image_history(image_name)
    if layers is None:
        return jsonify({"error": "Error retrieving image history"}), 500

    final_layer_size = ImageD.get_final_layer_size(image_name)
    if final_layer_size is None:
        final_layer_size = "N/A"

    return jsonify({"image_name": image_name, "layers": layers, "final_layer_size": final_layer_size})

@app.route('/image_metadata', methods=['GET', 'POST'])
def image_metadata():
    metadata = None
    image_name = None
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            metadata_cmd = f"docker inspect {image_name}"
            metadata_output = subprocess.check_output(metadata_cmd, shell=True).decode()
            metadata = metadata_output
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving metadata: {e}")
            return "Error retrieving metadata", 500

    return render_template('image_metadata.html', image_name=image_name, metadata=metadata, available_images=available_images)


@app.route('/dockerfile_snippets', methods=['GET'])
def dockerfile_snippets():
    image_name = request.args.get('image_name')
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return abort(500, description="Error retrieving available images")

    if not image_name:
        return render_template('dockerfile_snippets.html', image_name=None, snippets=None, available_images=available_images)

    try:
        dockerfile_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}}' {image_name}"
        dockerfile_output = subprocess.check_output(dockerfile_cmd, shell=True).decode()
        snippets = dockerfile_output.splitlines()
        return render_template('dockerfile_snippets.html', image_name=image_name, snippets=snippets, available_images=available_images)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching Dockerfile snippets: {e}")
        return abort(400, description="Error fetching Dockerfile snippets")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return abort(500, description="An unexpected error occurred")


@app.route('/volume_network_info', methods=['GET', 'POST'])
def volume_network_info():
    image_name = None
    volumes = []
    networks = []
    available_images = []

    try:
        client = docker.from_env()
        available_images = [image.tags[0] for image in client.images.list() if image.tags]
    except Exception as e:
        print(f"Error retrieving available images: {e}")
        return "Error retrieving available images", 500

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            volumes = extract_volumes(image_name)
            networks = extract_networks(image_name)
        except docker.errors.ImageNotFound:
            return "Image not found", 404
        except Exception as e:
            print(f"Error retrieving information: {e}")
            return "Error retrieving information", 500

    return render_template('volume_network_info.html', 
                        image_name=image_name, 
                        volumes=volumes, 
                        networks=networks, 
                        available_images=available_images)



def extract_volumes(image_name):
    try:
        # Run docker volume ls to get a list of volumes
        volumes_list_cmd = "docker volume ls --format '{{.Name}}'"
        volumes_list_output = subprocess.check_output(volumes_list_cmd, shell=True).decode().splitlines()
        
        volumes = []
        for volume in volumes_list_output:
            # Run docker volume inspect to get details for each volume
            inspect_cmd = f"docker volume inspect {volume}"
            inspect_output = subprocess.check_output(inspect_cmd, shell=True).decode()
            volume_info = json.loads(inspect_output)
            if volume_info:
                volume_details = volume_info[0]  # Inspect command returns a list
                volumes.append({
                    "name": volume_details['Name'],
                    "details": f"Mountpoint: {volume_details['Mountpoint']}, Driver: {volume_details['Driver']}"
                })
        return volumes
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving volume information: {e}")
        return []
    

def extract_networks(image_name):
    try:
        # Run docker network ls to get a list of networks
        networks_list_cmd = "docker network ls --format '{{.Name}}'"
        networks_list_output = subprocess.check_output(networks_list_cmd, shell=True).decode().splitlines()
        
        networks = []
        for network in networks_list_output:
            # Run docker network inspect to get details for each network
            inspect_cmd = f"docker network inspect {network}"
            inspect_output = subprocess.check_output(inspect_cmd, shell=True).decode()
            network_info = json.loads(inspect_output)
            if network_info:
                network_details = network_info[0]  # Inspect command returns a list
                networks.append({
                    "name": network_details['Name'],
                    "details": f"Driver: {network_details['Driver']}, Scope: {network_details['Scope']}"
                })
        return networks
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving network information: {e}")
        return []


@app.route('/vulnerabilities', methods=['GET', 'POST'])
def vulnerabilities():
    available_images = ImageD.get_docker_images()  # Get the list of available Docker images

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            # Run Trivy scan
            result = subprocess.run(['trivy', 'image', '--format', 'json', image_name], capture_output=True, text=True)
            if result.returncode != 0:
                return f"Error scanning image: {result.stderr}", 500

            # Parse JSON output from Trivy
            vulnerabilities = json.loads(result.stdout)
            return render_template('vulnerabilities.html', image_name=image_name, vulnerabilities=vulnerabilities, available_images=available_images)
        
        except Exception as e:
            print(f"Error running Trivy: {e}")
            return "Error running vulnerability scan", 500

    return render_template('vulnerabilities.html', image_name=None, vulnerabilities=None, available_images=available_images)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)