#!/bin/bash

export $(env -i \
    HOME="$HOME" \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    USER="$USER" \
    TERM="$TERM" \
    LANG="en_GB.UTF-8" \
    LC_CTYPE="UTF-8" \
    XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    PULSE_RUNTIME_PATH="$PULSE_RUNTIME_PATH" \
    DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
    env | cut -d= -f1)

exec > >(tee -a "/tmp/seaman_ai_speaker.log") 2>&1

echo "Starting runApp.sh at $(date)"
echo "Current user: $(whoami)"
echo "Current directory: $(pwd)"
# echo "Environment variables:"
# env

if ! pulseaudio --check; then
    echo "Starting PulseAudio..."
    pulseaudio --start --exit-idle-time=-1 &
    sleep 2
else
    echo "PulseAudio is already running."
fi

run_setup() {
    echo "Running setup..."
    python3 setup.py
    if [ $? -ne 0 ]; then
        echo "Setup failed. Please check the error messages above."
        exit 1
    fi
}

cleanup() {
    echo "Cleaning up..."
    if [ ! -z "$PYTHON_PID" ]; then
        echo "Sending termination signal to Python script..."
        kill -TERM "$PYTHON_PID"

        # Wait for the Python script to finish its cleanup
        echo "Waiting for Python script to finish cleanup..."
        wait "$PYTHON_PID"
        echo "Python script has finished."
    fi
    deactivate
    exit 0
}

trap cleanup SIGINT SIGTERM

if [ ! -d ".venv" ]; then
    run_setup
else
    echo "Virtual environment found. Checking for updates..."
    read -p "Do you want to run setup again? (y/n) " choice
    case "$choice" in 
        y|Y ) run_setup;;
        * ) echo "Skipping setup.";;
    esac
fi

source .venv/bin/activate

export OPENAI_API_KEY='key'
export PICO_ACCESS_KEY='another-key'
export SPEAKER_ID='example-speaker-id'
export FIREBASE_API_KEY='api-key'
export FIREBASE_PROJECT_ID='project-id'
export FIREBASE_AUTH_EMAIL='example@gmail.com'
export FIREBASE_AUTH_PASSWORD='example-password'

run_main_program() {
    echo "Starting AI Speaker System..."
    python3 app.py &
    PYTHON_PID=$!
    wait $PYTHON_PID
    exit_code=$?

    if [ $exit_code -eq 1 ]; then
        echo "Error occurred. Checking if it's due to a missing module..."
        if grep -q "ModuleNotFoundError" error.log; then
            echo "Module not found. Running setup again..."
            run_setup
            run_main_program
        else
            echo "AI Speaker System exited with code $exit_code."
        fi
    elif [ $exit_code -eq 130 ] || [ $exit_code -eq 143 ]; then
        echo "AI Speaker System was interrupted. Shutting down..."
    fi
}

run_main_program

echo "AI Speaker System has shut down."

cleanup