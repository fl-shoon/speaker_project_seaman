import asyncio
import logging
import serial.tools.list_ports
import wave

logging.basicConfig(level=logging.INFO)
utils_logger = logging.getLogger(__name__)

exit_event = asyncio.Event()

def set_exit_event():
    exit_event.set()

def is_exit_event_set():
    return exit_event.is_set()

def create_empty_wav_file(file_path):
    with wave.open(file_path, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(44100)  # 44.1kHz sampling rate
        wav_file.writeframes(b'')  # Empty audio data

def extract_usb_device():
    rp2040_port = None
    pico_arduino_port = None
    
    ports = list(serial.tools.list_ports.comports())
    utils_logger.info(f"Available ports: {ports}")
    
    for port, desc, hwid in ports:
        if "RP2040 LCD 1.28" in desc:
            rp2040_port = port
        elif "PicoArduino" in desc:
            pico_arduino_port = port
    
    if rp2040_port is None:
        utils_logger.warning("RP2040 LCD 1.28 port not found. Defaulting to /dev/ttyACM1")
        rp2040_port = '/dev/ttyACM1'
    
    if pico_arduino_port is None:
        utils_logger.warning("PicoArduino port not found. Defaulting to /dev/ttyACM0")
        pico_arduino_port = '/dev/ttyACM0'
    
    utils_logger.info(f"Selected RP2040 LCD port: {rp2040_port}")
    utils_logger.info(f"Selected PicoArduino port: {pico_arduino_port}")
    
    return rp2040_port, pico_arduino_port 