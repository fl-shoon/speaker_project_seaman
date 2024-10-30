from contextlib import contextmanager
from PIL import Image, ImageEnhance
from pygame import mixer

import io 
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
display_logger = logging.getLogger(__name__)

@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    try:
        null = os.open(os.devnull, os.O_RDWR)
        save_stdout, save_stderr = os.dup(1), os.dup(2)
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(save_stdout, 1)
        os.dup2(save_stderr, 2)
        os.close(null)

class DisplayModule:
    def __init__(self, serial_module):
        self.serial_module = serial_module
        self.fade_in_steps = 7

    def fade_in_logo(self, logo_path):
        img = Image.open(logo_path)
        width, height = img.size
        
        for i in range(self.fade_in_steps):
            alpha = int(255 * (i + 1) / self.fade_in_steps)
            current_brightness = self.serial_module.current_brightness * (i + 1) / self.fade_in_steps

            faded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            faded_img.paste(img, (0, 0))
            faded_img.putalpha(alpha)

            rgb_img = Image.new("RGB", faded_img.size, (0, 0, 0))
            rgb_img.paste(faded_img, mask=faded_img.split()[3])

            enhancer = ImageEnhance.Brightness(rgb_img)
            brightened_img = enhancer.enhance(current_brightness)

            img_byte_arr = io.BytesIO()
            brightened_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            self.serial_module.send_image_data(img_byte_arr)
            time.sleep(0.01)

    def update_gif(self, gif_path):
        frames = self.serial_module.prepare_gif(gif_path)
        all_frames = self.serial_module.precompute_frames(frames)
        
        frame_index = 0
        while mixer.music.get_busy():
            frame = Image.open(io.BytesIO(all_frames[frame_index]))
            
            brightened_frame = self.serial_module.apply_brightness(frame)
            
            img_byte_arr = io.BytesIO()
            brightened_frame.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            self.serial_module.send_image_data(img_byte_arr)
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(0.1)

    def display_image(self, image_path):
        try:
            img = Image.open(image_path)
            width, height = img.size

            if img.mode != 'RGB':
                img = img.convert('RGB')

            if (width, height) != (240, 240):
                img = img.resize((240, 240))

            brightened_img = self.serial_module.apply_brightness(img)

            img_byte_arr = io.BytesIO()
            brightened_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            self.serial_module.send_image_data(img_byte_arr)

        except Exception as e:
            display_logger.warning(f"Error in display_image: {e}")

    def start_listening_display(self, image_path):
        self.display_image(image_path)

    def stop_listening_display(self):
        self.serial_module.send_white_frames()

    def send_white_frames(self):
        self.serial_module.send_white_frames()