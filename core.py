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
        while not is_exit_event_set():
            try:
                res, trigger_type = self.wake_word.listen_for_wake_word(schedule_manager=schedule_manager, py_recorder=self.py_recorder)
                
                if res and trigger_type == WakeWorkType.TRIGGER:
                    await self.process_conversation()
                
                if res and trigger_type == WakeWorkType.SCHEDULE:
                    await self.scheduled_conversation()
                
                await asyncio.sleep(1)
            except Exception as e:
                core_logger.error(f"Error occured in core: {e}")
                await asyncio.sleep(1)

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
                conversation_ended = await self.ai_client.process_audio(input_audio_file)
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                core_logger.error(f"Error processing conversation: {e}")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)

    async def scheduled_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2
        text_initiation ="こんにちは"
        input_audio_file = None

        while conversation_active and not is_exit_event_set():
            if not self.serial_port_check():
                break

            # do recording only when the AI initiated conversation has finished once
            if input_audio_file:
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

                self.py_recorder.save_audio(frames, input_audio_file)

                self.display.stop_listening_display()

            try:
                # continue the dual conversation
                if input_audio_file:
                    conversation_ended = await self.ai_client.process_audio(input_audio_file)
                # this will run only once when the scheduled time has reached
                else:
                    conversation_ended, audio_file = await self.ai_client.process_text(text_initiation)
                    input_audio_file = audio_file
                    
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                core_logger.error(f"Error processing conversation: {e}")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                conversation_active = False

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
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.display and self.serial_module and self.serial_module.isPortOpen:
            self.display.send_white_frames()
        if self.serial_module:
            self.serial_module.close()
        core_logger.info("Cleanup process completed.")