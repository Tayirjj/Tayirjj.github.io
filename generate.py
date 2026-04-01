import io
import base64
import numpy as np
import scipy.io.wavfile as wavfile
import pyttsx3
from pydub import AudioSegment
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import torch

# تحميل نموذج MusicGen مرة واحدة
processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
model     = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
model.eval()


def generate_music(prompt: str, duration: int = 15) -> AudioSegment:
    """تحويل النص إلى موسيقى"""
    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt"
    )
    max_tokens = duration * model.config.audio_encoder.frame_rate

    with torch.no_grad():
        audio_values = model.generate(**inputs, max_new_tokens=int(max_tokens))

    sample_rate = model.config.audio_encoder.sampling_rate
    audio_np    = audio_values[0, 0].numpy()
    audio_np    = (audio_np * 32767).astype(np.int16)

    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, audio_np)
    buffer.seek(0)
    return AudioSegment.from_wav(buffer)


def generate_tts(lyrics: str) -> AudioSegment:
    """تحويل الكلمات إلى صوت"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)

    buffer = io.BytesIO()
    engine.save_to_file(lyrics, "temp_tts.wav")
    engine.runAndWait()

    return AudioSegment.from_wav("temp_tts.wav")


def run_song_generation(
    lyrics:      str,
    style:       str,
    genre:       str,
    topic:       str,
    output_type: str,  # "music_only" or "full_song"
    duration:    int 
) -> dict:

    # بناء الـ prompt لـ MusicGen
    music_prompt = f"{style} {genre} music about {topic}, instrumental"

    try:
        if output_type == "music_only":
            # موسيقى فقط
            music = generate_music(music_prompt, duration)
            final_audio = music

        elif output_type == "full_song":
            # كلمات + موسيقى
            music = generate_music(music_prompt, duration)
            vocals = generate_tts(lyrics)

            # دمج الصوت مع خفض صوت الموسيقى
            music  = music - 10  # خفض 10db
            vocals = vocals + 5  # رفع صوت الكلمات

            # دمج
            if len(vocals) > len(music):
                music = music * (len(vocals) // len(music) + 1)
            final_audio = music[:len(vocals)].overlay(vocals)

        else:
            return {"error": f"output_type must be 'music_only' or 'full_song'"}

        # تصدير
        buffer = io.BytesIO()
        final_audio.export(buffer, format="wav")
        buffer.seek(0)
        audio_b64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {
            "status":       "success",
            "audio_base64": audio_b64,
            "output_type":  output_type,
        }

    except Exception as e:
        import traceback
        return {"error": traceback.format_exc()}
