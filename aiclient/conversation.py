from utils.define import *
from openai import OpenAI, OpenAIError
from typing import List, Dict

import logging
import os
import time

logging.basicConfig(level=logging.INFO)
openai_logger = logging.getLogger(__name__)

class ConversationClient:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 3
        self.retry_delay = 5 
        self.audio_player = None
        self.gptContext = {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
            ユーザーが薬を飲んだかどうか一度だけぜひ確認してください。確認後は、他の話題に移ってください。
            会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
            ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""
        }

    def setAudioPlayer(self, audioPlayer):
        self.audio_player = audioPlayer

    def generate_ai_reply(self, new_message: str) -> str:
        for attempt in range(self.max_retries):
            try:
                if not self.conversation_history:
                    self.conversation_history = [self.gptContext]

                self.conversation_history.append({"role": "user", "content": new_message})

                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=self.conversation_history,
                    temperature=0.75,
                    max_tokens=500
                )
                ai_message = response.choices[0].message.content
                self.conversation_history.append({"role": "assistant", "content": ai_message})

                # Limit conversation history to last 10 messages to prevent token limit issues
                if len(self.conversation_history) > 11:  # 11 to keep the system message
                    self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

                return ai_message
            except OpenAIError as e:
                error_code = getattr(getattr(e, 'error', None), 'code', None) or getattr(e, 'type', None)
                if error_code == 'insufficient_quota':
                    openai_logger.error("OpenAI API quota exceeded. Please check your plan and billing details.")
                    return "申し訳ありません。現在システムに問題が発生しています。後でもう一度お試しください。"
                elif error_code == 'rate_limit_exceeded':
                    if attempt < self.max_retries - 1:
                        openai_logger.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                    else:
                        openai_logger.error("Max retries reached. Unable to complete the request.")
                        return "申し訳ありません。しばらくしてからもう一度お試しください。"
                else:
                    openai_logger.error(f"OpenAI API error: {e}")
                    return "申し訳ありません。エラーが発生しました。"

    def speech_to_text(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                response_format="text",
                language="ja"
            )
        return transcript

    def text_to_speech(self, text: str, output_file: str):
        try:
            response = self.client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",
                input=text,
                response_format="wav",
            )

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=4096):
                    f.write(chunk)
            self.audio_player.sync_audio_and_gif(output_file, SpeakingGif)
        except OpenAIError as e:
            openai_logger.error(f"Failed to generate speech: {e}")

    def process_audio(self, input_audio_file: str) -> bool:
        try:
            # Generate output filename
            base, ext = os.path.splitext(input_audio_file)
            output_audio_file = f"{base}_response{ext}"

            # Speech-to-Text
            stt_text = self.speech_to_text(input_audio_file)
            openai_logger.info(f"Transcript: {stt_text}")

            # LLM
            content_response = self.generate_ai_reply(stt_text)
            conversation_ended = '[END_OF_CONVERSATION]' in content_response
            content_response = content_response.replace('[END_OF_CONVERSATION]', '').strip()

            openai_logger.info(f"AI response: {content_response}")
            openai_logger.info(f"Conversation ended: {conversation_ended}")

            # Text-to-Speech
            if content_response:
                # Generate speech (TTS)
                try:
                    self.text_to_speech(content_response, output_audio_file)
                    openai_logger.info(f'Audio content written to file "{output_audio_file}"')
                except Exception as e:
                    openai_logger.error(f"Text-to-speech failed: {e}")
                    self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                    return True
            else:
                openai_logger.error("No AI response text generated")
                self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                return True
            
            return conversation_ended

        except OpenAIError as e:
            openai_logger.error(f"Error in process_audio: {e}")
            self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
            return True
        
    def process_text(self, auto_text: str) -> tuple[str, bool]:
        try:
            # LLM
            content_response = self.generate_ai_reply(auto_text)
            conversation_ended = '[END_OF_CONVERSATION]' in content_response
            content_response = content_response.replace('[END_OF_CONVERSATION]', '').strip()

            openai_logger.info(f"AI response: {content_response}")
            openai_logger.info(f"Conversation ended: {conversation_ended}")

            # Generate speech (TTS)
            output_audio_file = AIOutputAudio
            self.text_to_speech(content_response, output_audio_file)

            self.audio_player.sync_audio_and_gif(output_audio_file, SpeakingGif)
            return conversation_ended, output_audio_file

        except Exception as e:
            openai_logger.error(f"Error in process_audio: {e}")
            self.audio_player.sync_audio_and_gif(ErrorAudio, SpeakingGif)
            return True, ErrorAudio