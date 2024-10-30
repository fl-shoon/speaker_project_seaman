from contextlib import contextmanager
from pygame import mixer

import os
import pygame
import sys
import threading

@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    _stdout = sys.stdout
    _stderr = sys.stderr
    null = open(os.devnull, 'w')
    try:
        sys.stdout = null
        sys.stderr = null
        yield
    finally:
        sys.stdout = _stdout
        sys.stderr = _stderr
        null.close()

class AudioPlayer:
    def __init__(self, display):
        self.display = display
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        with suppress_stdout_stderr():
            pygame.init()
            mixer.init()
        self.is_playing = mixer.music.get_busy()
        self.current_volume = 0.2

    def set_audio_volume(self, volume):
        self.current_volume = max(0.0, min(1.0, volume))

    def play_audio(self, filename):
        with suppress_stdout_stderr():
            mixer.music.load(filename)
            mixer.music.play()
            mixer.music.set_volume(self.current_volume)

    def play_trigger_with_logo(self, trigger_audio, logo_path):
        self.play_audio(trigger_audio)
        
        fade_thread = threading.Thread(target=self.display.fade_in_logo, args=(logo_path,))
        fade_thread.start()

        while mixer.music.get_busy():
            with suppress_stdout_stderr():
                pygame.time.Clock().tick(10)

        fade_thread.join()

    def sync_audio_and_gif(self, audio_file, gif_path):
        self.play_audio(audio_file)
        
        gif_thread = threading.Thread(target=self.display.update_gif, args=(gif_path,))
        gif_thread.start()

        clock = pygame.time.Clock()
        while mixer.music.get_busy():
            with suppress_stdout_stderr():
                clock.tick(10)

        gif_thread.join()
        self.display.send_white_frames()