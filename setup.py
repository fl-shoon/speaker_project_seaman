import subprocess
import sys
import os
import venv
import argparse

class RaspberryPiSetup:
    def __init__(self, venv_path=".venv"):
        self.venv_path = venv_path
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        self.pip_path = os.path.join(self.venv_path, "bin", "pip")

    def run_command(self, command):
        try:
            result = subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {command}")
            print(f"Error message: {e}")
            return False, e.output

    def is_venv_created(self):
        return os.path.exists(self.venv_path) and os.path.exists(self.python_path)
    
    def create_virtual_environment(self):
        if self.is_venv_created():
            print(f"Virtual environment already exists at {self.venv_path}")
            return True
        
        print(f"Creating virtual environment at {self.venv_path}...")
        try:
            venv.create(self.venv_path, with_pip=True)
        except Exception as e:
            print(f"Error creating virtual environment: {e}")
            print("Attempting to create virtual environment using system command...")
            success, _ = self.run_command(f"python3 -m venv {self.venv_path}")
            return success 
        return True

    def install_package(self, package_name):
        print(f"Installing {package_name}...")
        return self.run_command(f"{self.pip_path} install {package_name}")

    def update_system(self):
        print("Updating system...")
        self.run_command("sudo apt-get update")
        self.run_command("sudo apt-get upgrade -y")

    def install_system_dependencies(self):
        print("Installing system dependencies...")
        dependencies = ["python3-dev", "python3-pip", "portaudio19-dev", "libatlas-base-dev", "fonts-ipafont", "fonts-noto-cjk"]
        for dep in dependencies:
            if not self.run_command(f"sudo apt-get install -y {dep}"):
                print(f"Failed to install system dependency: {dep}")
                return False
        return True

    def install_python_packages(self):
        print("Installing Python packages from requirements.txt...")
        requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
        if not os.path.exists(requirements_path):
            print(f"Error: requirements.txt not found at {requirements_path}")
            return False
        
        success, output = self.run_command(f"{self.pip_path} install -r {requirements_path}")
        if not success:
            print("Failed to install Python packages from requirements.txt")
            print(f"Error output: {output}")
            return False
        return True
    
    def check_pulse_audio_installation(self):
        success, output = self.run_command("dpkg -s pulseaudio")
        return success and "Status: install ok installed" in output
    
    def setup_pulse_audio(self):
        print("Setting up PulseAudio...")
        self.run_command("sudo apt-get install pulseaudio")
        self.run_command(f"sudo usermod -a -G audio $USER")
        # Configure ALSA
        alsa_conf = """
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:0,0"
    }
    capture.pcm {
        type plug
        slave.pcm "hw:1,0"
    }
}
"""
        with open('/tmp/asound.conf', 'w') as f:
            f.write(alsa_conf)
        self.run_command("sudo mv /tmp/asound.conf /etc/asound.conf")

        self.run_command("sudo /etc/init.d/alsa-utils restart")
        self.run_command("pulseaudio --start")

    def setup(self, update_system=False):
        if update_system:
            self.update_system()
        if not self.install_system_dependencies():
            print("Failed to install system dependencies. Exiting.")
            return False
        if not self.create_virtual_environment():
            print("Failed to create virtual environment. Exiting.")
            return False
        if not self.install_python_packages():
            print("Failed to install Python packages. Exiting.")
            return False
        if not self.check_pulse_audio_installation():
            self.setup_pulse_audio()
        else:
            print("PulseAudio is already installed and configured.")

        print("Setup completed successfully!")
        print(f"To activate the virtual environment, run: source {os.path.join(self.venv_path, 'bin', 'activate')}")
        return True
    
def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Setup Script")
    parser.add_argument("--update-system", action="store_true", help="Update system before installation")
    args = parser.parse_args()

    setup = RaspberryPiSetup()
    if not setup.setup(update_system=args.update_system):
        sys.exit(1)

if __name__ == "__main__":
    main()