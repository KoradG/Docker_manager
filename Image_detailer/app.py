from flask import Flask, request, render_template, jsonify, send_file, abort
import subprocess
import os
import zipfile
import json
import docker
import plotly.graph_objs as go
import plotly.io as pio

app = Flask(__name__)

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/image', methods=['GET', 'POST'])
def image():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        layers = get_image_history(image_name)
        if layers is None:
            return "Error retrieving image history", 500

        final_layer_size = get_final_layer_size(image_name)
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

@app.route('/image_tags', methods=['GET', 'POST'])
def image_tags():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            tags_cmd = "docker images --format '{{.Repository}}:{{.Tag}}'"
            tags_output = subprocess.check_output(tags_cmd, shell=True).decode().splitlines()
            tags = [tag for tag in tags_output if tag.startswith(image_name)]
            if not tags:
                tags = ["No tags found."]
            return render_template('image_tags.html', image_name=image_name, tags=tags)
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving tags: {e}")
            return "Error retrieving tags", 500
    return render_template('image_tags.html')

@app.route('/image_size_breakdown', methods=['GET', 'POST'])
def image_size_breakdown():
    image_name = None
    layers = []

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

    return render_template('image_size_breakdown.html', image_name=image_name, layers=layers)

@app.route('/environment_variables', methods=['GET', 'POST'])
def environment_variables():
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

        return render_template('environment_variables.html', image_name=image_name, env_vars=env_vars)
    return render_template('environment_variables.html')

@app.route('/layer_comparison', methods=['GET', 'POST'])
def layer_comparison():
    if request.method == 'POST':
        image_name1 = request.form.get('image_name1')
        image_name2 = request.form.get('image_name2')
        if not image_name1 or not image_name2:
            return "Both image names are required", 400

        try:
            layers1 = get_image_history(image_name1)
            layers2 = get_image_history(image_name2)
            if layers1 is None or layers2 is None:
                return "Error retrieving image history", 500

            return render_template('layer_comparison.html', 
                                   image_name1=image_name1, 
                                   image_name2=image_name2, 
                                   layers1=layers1, 
                                   layers2=layers2)
        except Exception as e:
            print(f"Error comparing layers: {e}")
            return "Error comparing layers", 500
    return render_template('layer_comparison.html')

@app.route('/interactive_visualizations', methods=['GET', 'POST'])
def interactive_visualizations():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            layers = get_image_history(image_name)
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
                textposition='outside'
            ))
            fig.update_layout(
                title=f'Layer Sizes for {image_name}',
                xaxis_title='Size (MB)',
                yaxis_title='Layer'
            )
            graph_html = pio.to_html(fig, full_html=False)

            return render_template('interactive_visualizations.html', 
                                   image_name=image_name, 
                                   plot_html=graph_html)
        except Exception as e:
            print(f"Error generating visualizations: {e}")
            return "Error generating visualizations", 500
    return render_template('interactive_visualizations.html')

@app.route('/logs_build_info', methods=['GET', 'POST'])
def logs_build_info():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            logs_cmd = f"docker history {image_name}"
            logs_output = subprocess.check_output(logs_cmd, shell=True).decode()
            return render_template('logs_build_info.html', 
                                   image_name=image_name, 
                                   logs=logs_output)
        except subprocess.CalledProcessError as e:
            print(f"Error retrieving logs/build info: {e}")
            return "Error retrieving logs/build info", 500
    return render_template('logs_build_info.html')

@app.route('/download_image_data', methods=['GET', 'POST'])
def download_image_data():
    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        sanitized_image_name = image_name.replace(':', '_').replace('/', '_')
        zip_filename = f"{sanitized_image_name}_data.zip"

        try:
            if os.path.exists(zip_filename):
                os.remove(zip_filename)

            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                history_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}} {{{{.Size}}}} {{{{.CreatedAt}}}}' {image_name}"
                history_output = subprocess.check_output(history_cmd, shell=True).decode()
                zipf.writestr('history.txt', history_output)

            if not os.path.exists(zip_filename):
                print(f"File {zip_filename} was not created")
                return "Error creating zip file", 500

            return send_file(zip_filename, as_attachment=True)
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e.output}")
            return "Error generating Docker history", 500
        except Exception as e:
            print(f"Error preparing download: {e}")
            return "Error preparing download", 500
        finally:
            if os.path.exists(zip_filename):
                os.remove(zip_filename)
    return render_template('download_image_data.html')

@app.route('/api/image', methods=['POST'])
def image_api():
    image_name = request.json.get('image_name')
    if not image_name:
        return jsonify({"error": "Image name is required"}), 400

    layers = get_image_history(image_name)
    if layers is None:
        return jsonify({"error": "Error retrieving image history"}), 500

    final_layer_size = get_final_layer_size(image_name)
    if final_layer_size is None:
        final_layer_size = "N/A"

    return jsonify({"image_name": image_name, "layers": layers, "final_layer_size": final_layer_size})

@app.route('/image_metadata', methods=['GET', 'POST'])
def image_metadata():
    metadata = None
    image_name = None

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

    return render_template('image_metadata.html', image_name=image_name, metadata=metadata)

@app.route('/dockerfile_snippets', methods=['GET'])
def dockerfile_snippets():
    image_name = request.args.get('image_name')
    
    if not image_name:
        return render_template('dockerfile_snippets.html', image_name=None, snippets=None)

    try:
        dockerfile_cmd = f"docker history --no-trunc --format '{{{{.CreatedBy}}}}' {image_name}"
        dockerfile_output = subprocess.check_output(dockerfile_cmd, shell=True).decode()
        snippets = dockerfile_output.splitlines()
        return render_template('dockerfile_snippets.html', image_name=image_name, snippets=snippets)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching Dockerfile snippets: {e}")
        return abort(400, description="Error fetching Dockerfile snippets")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return abort(500, description="An unexpected error occurred")

@app.route('/layer_changes', methods=['GET'])
def layer_changes():
    image_name = request.args.get('image_name')
    if not image_name:
        return "Image name is required", 400

    try:
        cmd = f"docker history --no-trunc --format '{{\"Layer\":\"{{.Id}}\", \"Change\":\"{{.CreatedBy}}\", \"Timestamp\":\"{{.CreatedAt}}\"}}' {image_name}"
        output = subprocess.check_output(cmd, shell=True).decode()
        layer_changes = json.loads(f"[{output.strip().rstrip(',')}]")
        return render_template('layer_changes.html', image_name=image_name, layer_changes=layer_changes)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return "Error retrieving data", 500
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return "Error processing data", 500

@app.route('/volume_network_info', methods=['GET', 'POST'])
def volume_network_info():
    image_name = None
    volumes = []
    networks = []

    if request.method == 'POST':
        image_name = request.form.get('image_name')
        if not image_name:
            return "Image name is required", 400

        try:
            client = docker.from_env()
            image = client.images.get(image_name)

            volumes = extract_volumes(image_name)
            networks = extract_networks(image_name)

        except docker.errors.ImageNotFound:
            return "Image not found", 404
        except Exception as e:
            print(f"Error retrieving information: {e}")
            return "Error retrieving information", 500

    return render_template('volume_network_info.html', image_name=image_name, volumes=volumes, networks=networks)



def extract_volumes(image_name):
    # Replace with real logic to extract volume information
    return [
        {"name": "/data", "details": "Data volume used for persistent storage."},
        {"name": "/logs", "details": "Log volume for application logs."}
    ]

def extract_networks(image_name):
    # Replace with real logic to extract network information
    return [
        {"name": "bridge", "details": "Default bridge network."},
        {"name": "host", "details": "Host network for direct communication with the host."}
    ]
    
if __name__ == '__main__':
    app.run(debug=True)
