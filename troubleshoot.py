import subprocess
import os

def apt_troubleshoot():
    """
    Diagnoses and attempts to fix common apt update issues on Raspberry Pi
    Returns tuple of (success: bool, message: str)
    """
    def run_command(command):
        try:
            result = subprocess.run(command, shell=True, check=True, 
                                  capture_output=True, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.output

    # Check if running as root
    if os.geteuid() != 0:
        return False, "This script needs to be run as root (sudo python3 troubleshoot.py)"

    # 1. Check if dpkg is locked
    print("Checking for locked dpkg...")
    if os.path.exists("/var/lib/dpkg/lock-frontend"):
        print("Found locked dpkg. Attempting to fix...")
        run_command("rm /var/lib/dpkg/lock-frontend")
        run_command("rm /var/lib/dpkg/lock")
        run_command("rm /var/cache/apt/archives/lock")
        run_command("dpkg --configure -a")

    # 2. Clean apt cache
    print("Cleaning apt cache...")
    success, output = run_command("apt-get clean")
    if not success:
        return False, f"Failed to clean apt cache: {output}"

    # 3. Remove problematic lists
    print("Removing potentially corrupted lists...")
    success, output = run_command("rm -rf /var/lib/apt/lists/*")
    if not success:
        return False, f"Failed to remove apt lists: {output}"

    # 4. Reconfigure package system
    print("Reconfiguring package system...")
    success, output = run_command("dpkg --configure -a")
    if not success:
        return False, f"Failed to reconfigure dpkg: {output}"

    # 5. Fix broken packages
    print("Fixing broken packages...")
    success, output = run_command("apt-get -f install")
    if not success:
        return False, f"Failed to fix broken packages: {output}"

    # 6. Update package lists
    print("Updating package lists...")
    success, output = run_command("apt-get update")
    if not success:
        return False, f"Failed to update package lists: {output}"

    return True, "Successfully fixed apt system"

if __name__ == "__main__":
    success, message = apt_troubleshoot()
    print(f"\nResult: {message}")