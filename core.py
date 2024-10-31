from audio.player import AudioPlayer
from audio.recorder import PyRecorder
from utils.define import *
from display.display import DisplayModule
from transmission.serialModule import SerialModule
from utils.utils import is_exit_event_set
from wakeword.wakeword import WakeWord

import logging
import time

logging.basicConfig(level=logging.INFO)
core_logger = logging.getLogger(__name__)

class SpeakerCore:
    def __init__(self, args):
        self.args = args
        self.ai_client = args.aiclient
        self.serial_module = SerialModule()
        self.py_recorder = PyRecorder()

        self.display = DisplayModule(self.serial_module)
        self.audio_player = AudioPlayer(self.display)
        self.wake_word = WakeWord(args=args, audio_player=self.audio_player, serial_module=self.serial_module)
        
        self.initialize()

        core_logger.info("Speaker Core initialized successfully")

    def initialize(self):
        if not self.serial_module.open(USBPort):
            # FIXME: Send a failure notice post request to server later
            raise ConnectionError(f"Failed to open serial port {USBPort}")
        
    async def run(self, schedule_manager):
        try:
            while not is_exit_event_set():
                try:
                    if not hasattr(self, 'device_retry_count'):
                        self.device_retry_count = 0
                        
                    res, trigger_type = self.wake_word.listen_for_wake_word(
                        schedule_manager=schedule_manager, 
                        py_recorder=self.py_recorder
                    )
                    
                    # Reset retry count on successful operation
                    self.device_retry_count = 0
                    
                    if res:
                        if trigger_type and trigger_type == WakeWordType.TRIGGER:
                            await self.process_conversation()
                        
                        if trigger_type and trigger_type == WakeWordType.SCHEDULE:
                            await self.scheduled_conversation()
                    else:
                        if trigger_type is WakeWordType.OTHER:
                            self.cleanup()
                            break
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.device_retry_count += 1
                    core_logger.error(f"Error occurred wake word listening: {e}")
                    
                    if self.device_retry_count > 3:  # Max retries before reinitializing
                        core_logger.info("Too many device errors, reinitializing...")
                        self.cleanup()
                        await asyncio.sleep(2)
                        await self.reinitialize()
                        self.device_retry_count = 0
                    else:
                        await asyncio.sleep(1)
                        
        except Exception as e:
            core_logger.error(f"Error occurred in core: {e}")

    async def reinitialize(self):
        try:
            if self.py_recorder:
                self.py_recorder.stop_stream()
            
            # Create new instance
            self.py_recorder = PyRecorder()  
            self.wake_word = WakeWord(
                args=self.args, 
                audio_player=self.audio_player, 
                serial_module=self.serial_module
            )
            
            if not self.serial_module.isPortOpen:
                if not self.serial_module.open(USBPort):
                    raise ConnectionError(f"Failed to open serial port {USBPort}")
                    
            core_logger.info("Successfully reinitialized devices")
            
        except Exception as e:
            core_logger.error(f"Failed to reinitialize: {e}")
            raise

    async def process_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2

        while conversation_active and not is_exit_event_set():
            if not self.serial_port_check():
                break

            self.display.start_listening_display(SatoruHappy)
            frames = self.py_recorder.record_question(audio_player=self.audio_player)

            if not frames:
                silence_count += 1
                if silence_count >= max_silence:
                    core_logger.info("Maximum silence reached. Ending conversation.")
                    conversation_active = False
                continue
            else:
                silence_count = 0

            input_audio_file = AIOutputAudio
            self.py_recorder.save_audio(frames, input_audio_file)

            self.display.stop_listening_display()

            try:
                conversation_ended = self.ai_client.process_audio(input_audio_file)
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                core_logger.error(f"Error processing conversation: {e}")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                conversation_active = False

            await asyncio.sleep(0.1)

        self.display.fade_in_logo(SeamanLogo)

    async def scheduled_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2
        text_initiation = "こんにちは"

        try:
            conversation_ended, _ = self.ai_client.process_text(text_initiation)
            if conversation_ended:
                self.display.fade_in_logo(SeamanLogo)
                return

            while conversation_active and not is_exit_event_set():
                if not self.serial_port_check():
                    break

                self.display.start_listening_display(SatoruHappy)
                frames = self.py_recorder.record_question(audio_player=self.audio_player)

                if not frames:
                    silence_count += 1
                    if silence_count >= max_silence:
                        core_logger.info("Maximum silence reached. Ending conversation.")
                        conversation_active = False
                    continue
                else:
                    silence_count = 0

                input_audio_file = AIOutputAudio
                self.py_recorder.save_audio(frames, input_audio_file)

                self.display.stop_listening_display()

                try:
                    conversation_ended = self.ai_client.process_audio(input_audio_file)
                    if conversation_ended:
                        conversation_active = False
                except Exception as e:
                    core_logger.error(f"Error processing conversation: {e}")
                    self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                    conversation_active = False

                await asyncio.sleep(0.1)

        except Exception as e:
            core_logger.error(f"Error in scheduled conversation: {e}")
            self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
        finally:
            self.display.fade_in_logo(SeamanLogo)

    def serial_port_check(self):
        if not self.serial_module.isPortOpen:
            core_logger.info("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):
                if self.serial_module.open(USBPort):
                    core_logger.info("Successfully reopened serial connection.")
                    return True
                core_logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            core_logger.error("Failed to reopen serial connection after 3 attempts.")
            # FIXME: Send a failure notice post request to server later
            return False
        return True
    
    def cleanup(self):
        core_logger.info("Starting cleanup process...")
        try:
            if self.py_recorder:
                try:
                    self.py_recorder.stop_stream()
                except Exception as e:
                    core_logger.error(f"Error stopping recorder: {e}")
                    
            if self.display and self.serial_module and self.serial_module.isPortOpen:
                try:
                    self.display.send_white_frames()
                except Exception as e:
                    core_logger.error(f"Error sending white frames: {e}")
                    
            if self.serial_module:
                try:
                    self.serial_module.close()
                except Exception as e:
                    core_logger.error(f"Error closing serial module: {e}")
                    
        except Exception as e:
            core_logger.error(f"Error during cleanup: {e}")
        finally:
            core_logger.info("Cleanup process completed.")