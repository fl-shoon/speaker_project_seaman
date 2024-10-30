from display.setting import SettingMenu
from pico.pico import PicoVoiceTrigger
from utils.define import *
from utils.scheduler import run_pending
from utils.utils import is_exit_event_set

from pvrecorder import PvRecorder

import logging
import numpy as np
import time

logging.basicConfig(level=logging.INFO)
wakeword_logger = logging.getLogger(__name__)

class WakeWord:
    def __init__(self, args, audio_player, serial_module):
        self.audio_player = audio_player
        self.serial_module = serial_module
        self.pv_recorder = None 
        self.play_trigger = None
        self.porcupine = PicoVoiceTrigger(args)
        self.setting_menu = SettingMenu(audio_player=self.audio_player, serial_module=self.serial_module)
        
    def initialize_recorder(self):
        if self.pv_recorder is None:
            try:
                self.pv_recorder = PvRecorder(frame_length=self.porcupine.frame_length)
            except Exception as e:
                wakeword_logger.error(f"Failed to initialize recorder: {e}")
                raise

    def check_buttons(self):
        try:
            inputs = self.serial_module.get_inputs()
            if inputs and 'result' in inputs:
                result = inputs['result']
                buttons = result.get('buttons', [])

                if len(buttons) > 1 and buttons[1]:  # RIGHT button
                    response = self.setting_menu.display_menu()
                    if response:
                        return response
                    time.sleep(0.2)
            return None
        except Exception as e:
            wakeword_logger.error(f"Error in check_buttons: {e}")
            return None
        
    def listen_for_wake_word(self, schedule_manager, py_recorder):
        try:
            self.initialize_recorder()
            self.pv_recorder.start()

            frame_bytes = []
            calibration_interval = 5
            last_button_check_time = time.time()
            last_calibration_time = time.time()
            button_check_interval = 1.5 # 1.5 -> check buttons every 1.5 seconds
            detections = -1

            while not is_exit_event_set():
                run_pending()

                if schedule_manager.check_scheduled_conversation():
                    return True, WakeWordType.SCHEDULE

                audio_frame = self.pv_recorder.read()
                audio_frame_bytes = np.array(audio_frame, dtype=np.int16).tobytes()
                frame_bytes.append(audio_frame_bytes)

                current_time = time.time() # timestamp

                if current_time - last_calibration_time >= calibration_interval:
                    py_recorder.calibrate_energy_threshold(frame_bytes)

                    frame_bytes = []
                    last_calibration_time = current_time

                if self.play_trigger is None:
                    self.audio_player.play_trigger_with_logo(TriggerAudio, SeamanLogo)
                    self.play_trigger = True
                
                detections = self.porcupine.process(audio_frame)
                wake_word_triggered = detections >= 0
                
                if wake_word_triggered:
                    wakeword_logger.info("Wake word detected")
                    self.audio_player.play_audio(ResponseAudio)
                    return True, WakeWordType.TRIGGER
                
                if current_time - last_button_check_time >= button_check_interval:
                    res = self.check_buttons()
                    
                    if res == 'exit':
                        self.audio_player.play_trigger_with_logo(TriggerAudio, SeamanLogo)
                    
                    last_button_check_time = current_time

        except KeyboardInterrupt:
            return False, WakeWordType.OTHER
        except Exception as e:
            wakeword_logger.error(f"Error in wake word detection: {e}")
            raise
        finally:
            self.cleanup_recorder()

        return False, None
    
    def cleanup_recorder(self):
        if self.pv_recorder:
            try:
                self.pv_recorder.stop()
                self.pv_recorder.delete()
                self.pv_recorder = None
            except Exception as e:
                wakeword_logger.error(f"Error cleaning up recorder: {e}")