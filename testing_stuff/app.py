import os
import subprocess
import sys
import time

def is_running_in_docker():
    # Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return True
    
    # Check for Docker cgroup entries
    try:
        with open('/proc/self/cgroup', 'r') as f:
            for line in f:
                if 'docker' in line:
                    return True
    except Exception as e:
        print(f"Error checking cgroup info: {e}", flush=True)

    # Additional check to determine if the environment is Docker
    try:
        # Run a Docker command to check if Docker is available
        result = subprocess.run(['docker', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1)
        if result.returncode == 0:
            return True
    except Exception as e:
        print(f"Error running Docker command: {e}", flush=True)
    
    return False

if __name__ == '__main__':
    while True:
        if is_running_in_docker():
            print("Running inside a Docker container.", flush=True)
        else:
            print("Not running inside a Docker container.", flush=True)
        
        # Sleep for half a second before the next check
        time.sleep(0.5)
