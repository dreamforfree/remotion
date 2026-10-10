import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import wave

import gemini_tts


def wav_data():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(24000)
        file.writeframes(b"\0\0" * 24000)
    return buffer.getvalue()


class TtsTest(unittest.TestCase):
    def test_request_and_wav(self):
        data = wav_data()
        response = {"steps": [{"type": "model_output", "content": [
            {"type": "audio", "data": base64.b64encode(data).decode()}]}]}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as call:
            config = {"model": "gemini-3.8-flash-tts", "voice": "Kore", "style": "普通话"}
            self.assertEqual(gemini_tts.generate("测试", config, "test-placeholder"), data)
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, gemini_tts.ENDPOINT)
        self.assertNotIn("test-placeholder", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-placeholder")
        self.assertEqual(json.loads(request.data)["input"][0]["content"][0]["text"], "测试")

    def test_reject_empty_or_non_wav(self):
        with self.assertRaises(ValueError):
            gemini_tts.audio_bytes({"steps": []})
        with self.assertRaises(ValueError):
            gemini_tts.audio_bytes({"steps": [{"type": "model_output", "content": [
                {"type": "audio", "data": base64.b64encode(b"wrong").decode()}]}]})

    def test_output_duration_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "voice.wav"
            text = Path(folder) / "text.txt"
            text.write_text("测试配音", encoding="utf-8")
            argv = ["gemini_tts.py", "--text", str(text), "--out", str(output)]
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-placeholder"}), patch("sys.argv", argv), patch("gemini_tts.generate", return_value=wav_data()) as generate:
                gemini_tts.main()
                metadata = json.loads(output.with_suffix(".json").read_text())
                self.assertEqual(metadata["durationInFrames"], 30)
                self.assertEqual(metadata["durationSeconds"], 1)
                self.assertNotIn("test-placeholder", output.with_suffix(".json").read_text())
                with self.assertRaises(ValueError):
                    gemini_tts.main()
                self.assertEqual(generate.call_count, 1)

    def test_speed_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            text = Path(folder) / "text.txt"
            text.write_text("测试", encoding="utf-8")
            output = Path(folder) / "voice.wav"
            argv = ["gemini_tts.py", "--text", str(text), "--out", str(output), "--speed", "1.2"]
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-placeholder"}), patch("sys.argv", argv), patch("gemini_tts.generate", return_value=wav_data()):
                gemini_tts.main()
            metadata = json.loads(output.with_suffix(".json").read_text())
            self.assertLess(metadata["durationSeconds"], 1)
            self.assertGreater(metadata["durationSeconds"], 0.75)

    def test_check_never_calls_api(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-placeholder"}), patch("sys.argv", ["gemini_tts.py", "--check"]), patch("gemini_tts.generate") as call:
            gemini_tts.main()
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
