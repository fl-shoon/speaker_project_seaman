from core import SpeakerCore
from fireclient.fireclient import FireClient
# from aiclient.openai_api import OpenAIClient
from aiclient.conversation import ConversationClient
from utils.define import *
from utils.scheduler import ScheduleManager
from utils.utils import set_exit_event

import asyncio
import argparse
import logging
import os
import signal

logging.basicConfig(level=logging.INFO)
main_logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    main_logger.info(f"Received {signum} signal. Initiating graceful shutdown...")
    set_exit_event()

async def main():
    # aiClient = OpenAIClient()
    # await aiClient.initialize()

    aiClient = ConversationClient()

    parser = argparse.ArgumentParser()
    # Pico
    parser.add_argument('--access_key', help='AccessKey for Porcupine', default=os.environ["PICO_ACCESS_KEY"])
    parser.add_argument('--keyword_paths', nargs='+', help="Paths to keyword model files", default=[PicoWakeWordSatoru])
    parser.add_argument('--model_path', help='Path to Porcupine model file', default=PicoLangModel)
    parser.add_argument('--sensitivities', nargs='+', help="Sensitivities for keywords", type=float, default=[0.5])

    # OpenAi
    parser.add_argument('--aiclient', help='Asynchronous openAi client', default=aiClient)

    args = parser.parse_args()

    speaker = SpeakerCore(args)
    fire_client = FireClient()
    schedule_manager = ScheduleManager(serial_module=speaker.serial_module, fire_client=fire_client)
    aiClient.setAudioPlayer(speaker.audio_player)

    try:
        await speaker.run(schedule_manager)

    except KeyboardInterrupt:
        main_logger.info("KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        main_logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # await speaker.ai_client.close()
        speaker.cleanup()
        
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(main())