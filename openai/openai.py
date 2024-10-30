from utils.define import *
from typing import List, Dict, AsyncGenerator

import aiohttp
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
openai_logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.api_key = os.environ["OPENAI_API_KEY"]
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 3
        self.retry_delay = 5
        self.http_client = None
        self.audio_player = None
        self.gptContext = {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
                        ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
                        会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
                        ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}

    async def initialize(self):
        self.http_client = aiohttp.ClientSession()

    def setAudioPlayer(self, audioPlayer):
        self.audio_player = audioPlayer

    async def close(self):
        if self.http_client:
            await self.http_client.close()

    async def service_openAI(self, endpoint: str, payload: Dict, files: Dict = None) -> AsyncGenerator[bytes, None]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"https://api.openai.com/v1/{endpoint}"

        total_attempts = 0
        while total_attempts < self.max_retries:
            try:
                if files:
                    data = aiohttp.FormData()
                    for key, value in payload.items():
                        data.add_field(key, str(value))
                    for key, (filename, file) in files.items():
                        data.add_field(key, file, filename=filename)

                conn = aiohttp.TCPConnector(force_close=True)
                async with aiohttp.ClientSession(connector=conn) as session:
                    async with session.post(
                        url,
                        headers=headers,
                        data=data if files else None,
                        json=payload if not files else None,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response.raise_for_status()
                        content_length = int(response.headers.get('Content-Length', 0))
                        received_length = 0
                        buffer = bytearray()

                        async for chunk in response.content.iter_chunked(8192):
                            received_length += len(chunk)
                            buffer.extend(chunk)
                            
                            if content_length > 0 and received_length > content_length:
                                raise aiohttp.ClientPayloadError("Received more data than expected")

                        if content_length > 0 and received_length < content_length:
                            raise aiohttp.ClientPayloadError(
                                f"Incomplete response: got {received_length} bytes, expected {content_length}"
                            )

                        yield bytes(buffer)
                        break  

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                total_attempts += 1
                if total_attempts < self.max_retries:
                    delay = self.retry_delay * (2 ** (total_attempts - 1))  
                    openai_logger.info(f"Loading audio in {delay} seconds.......")
                    # openai_logger.warning(
                    #     f"Attempt {total_attempts} failed: {str(e)}. Retrying in {delay} seconds..."
                    # )
                    await asyncio.sleep(delay)
                else:
                    openai_logger.error(f"All attempts failed: {str(e)}")
                    raise
    
    async def generate_ai_reply(self, new_message: str) -> AsyncGenerator[str, None]:
        if not self.conversation_history:
            self.conversation_history = [self.gptContext]

        self.conversation_history.append({"role": "user", "content": new_message})
        payload = {"model": "gpt-4", "messages": self.conversation_history, "temperature": 0.75, "max_tokens": 500, "stream": True}

        ai_response_text = ""
        response_buffer = ""

        async for chunk in self.service_openAI("chat/completions", payload):
            response_buffer += chunk.decode('utf-8')
            while True:
                try:
                    split_index = response_buffer.index('\n\n')
                    line = response_buffer[:split_index].strip()
                    response_buffer = response_buffer[split_index + 2:]
                    
                    if line.startswith("data: "):
                        if line == "data: [DONE]":
                            break
                        json_str = line[6:] 
                        chunk_data = json.loads(json_str)
                        content = chunk_data['choices'][0]['delta'].get('content', '')
                        if content:
                            ai_response_text += content
                            yield content
                except ValueError:  
                    break
                except json.JSONDecodeError as e:
                    openai_logger.error(f"JSON decode error: {e}")
                    openai_logger.error(f"Problematic JSON string: {json_str}")
                    break

        self.conversation_history.append({"role": "assistant", "content": ai_response_text})

        if len(self.conversation_history) > 11:
            self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

    async def speech_to_text(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as audio_file:
            files = {"file": ("audio.wav", audio_file)}
            payload = {"model": "whisper-1", "response_format": "text", "language": "ja"}
            response_text = ""
            
            async for chunk in self.service_openAI("audio/transcriptions", payload, files):
                transcript_chunk = chunk.decode('utf-8')
                response_text += transcript_chunk

            return response_text

    async def text_to_speech(self, text: str, output_file: str):
        payload = {"model": "tts-1-hd", "voice": "nova", "input": text, "response_format": "wav"}
        
        temp_file = f"{output_file}.temp"
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                buffer = bytearray()
                async for chunk in self.service_openAI("audio/speech", payload):
                    buffer.extend(chunk)
                
                with open(temp_file, "wb") as f:
                    f.write(buffer)
                
                if os.path.getsize(temp_file) > 0:
                    os.replace(temp_file, output_file)
                    openai_logger.info(f'Audio content written to file "{output_file}"')
                    return
                else:
                    raise aiohttp.ClientError("Empty response received")
                    
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    delay = self.retry_delay * (2 ** retry_count)
                    openai_logger.warning(f"TTS attempt {retry_count} failed: {e}. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    openai_logger.error(f"TTS failed after {max_retries} attempts: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    raise

    async def process_audio(self, input_audio_file: str) -> bool:
        try:
            base, ext = os.path.splitext(input_audio_file)
            output_audio_file = f"{base}_response{ext}"

            # Transcribe audio (STT)
            try:
                response_text = await self.speech_to_text(input_audio_file)
                openai_logger.info(f"Result from stt: {response_text}")
            except Exception as e:
                openai_logger.error(f"Speech-to-text failed: {e}")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                return True

            # Generate response (Chat)
            ai_response_text = ""
            try:
                async for response_chunk in self.generate_ai_reply(response_text):
                    ai_response_text += response_chunk
            except aiohttp.ClientPayloadError as e:
                openai_logger.error(f"Error during AI response generation: {e}")
                if not ai_response_text:
                    self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                    return True
                openai_logger.info("Using partial response as fallback")
            except Exception as e:
                openai_logger.error(f"Unexpected error during AI response generation: {e}")
                if not ai_response_text:
                    self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                    return True

            conversation_ended = '[END_OF_CONVERSATION]' in ai_response_text
            ai_response_text = ai_response_text.replace('[END_OF_CONVERSATION]', '').strip()

            openai_logger.info(f"AI response: {ai_response_text}")
            openai_logger.info(f"Conversation ended: {conversation_ended}")

            if ai_response_text:
                # Generate speech (TTS)
                try:
                    await self.text_to_speech(ai_response_text, output_audio_file)
                    self.audio_player.sync_audio_and_gif(output_audio_file, SpeakingGif)
                except Exception as e:
                    openai_logger.error(f"Text-to-speech failed: {e}")
                    self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                    return True
            else:
                openai_logger.error("No AI response text generated")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                return True

            return conversation_ended

        except Exception as e:
            openai_logger.error(f"Error in process_audio: {e}")
            self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
            return True
    
    async def process_text(self, auto_text: str) -> tuple[str, bool]:
        try:
            # Generate response (Chat)
            ai_response_text = ""
            async for response_chunk in self.generate_ai_reply(auto_text):
                ai_response_text += response_chunk

            conversation_ended = '[END_OF_CONVERSATION]' in ai_response_text
            ai_response_text = ai_response_text.replace('[END_OF_CONVERSATION]', '').strip()

            openai_logger.info(f"AI response: {ai_response_text}")
            openai_logger.info(f"Conversation ended: {conversation_ended}")

            # Generate speech (TTS)
            output_audio_file = AIOutputAudio
            await self.text_to_speech(ai_response_text, output_audio_file)

            # await asyncio.to_thread(self.audio_player.sync_audio_and_gif, output_audio_file, SpeakingGif)
            self.audio_player.sync_audio_and_gif(output_audio_file, SpeakingGif)
            return conversation_ended, output_audio_file

        except Exception as e:
            openai_logger.error(f"Error in process_audio: {e}")
            self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
            return True, ErrorAudio