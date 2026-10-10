#!/usr/bin/env python3
"""Generate a WAV through Gemini TTS; uses Python's standard library only."""
import argparse
import base64
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"


def audio_bytes(response):
    chunks = [c for s in response.get("steps", [])
              if s.get("type") == "model_output"
              for c in s.get("content", []) if c.get("type") == "audio"]
    if not chunks:
        raise ValueError("API 未返回音频，请检查模型是否支持 TTS")
    audio = chunks[-1]
    data = base64.b64decode(audio["data"], validate=True)
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("API 返回的音频不是 WAV，请使用支持 WAV 输出的模型")
    return data


def generate(text, config, key):
    body = {
        "model": config["model"],
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": text,
            "annotations": [{"type": "speech_metadata", "style": config["style"]}]
        }]}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": config["voice"]}]}
    }
    # urllib honors HTTPS_PROXY. Keep authentication in the HTTPS header,
    # so Codex network-secret substitution can work without exposing the key.
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return audio_bytes(json.load(response))
    except ValueError:
        raise ValueError("请求配置或音频响应无效，请检查网络密钥和 TTS 模型") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", type=Path)
    parser.add_argument("--out", type=Path, default=Path("output/voice.wav"))
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--speed", type=float, default=1.0,
                        help="精确变速并保留音高，例如 1.2；需要 ffmpeg")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--check", action="store_true", help="仅检查配置，不调用 API")
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("未配置 GEMINI_API_KEY，请在云端环境中添加网络密钥")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for name in ("model", "voice", "style"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"config.json 缺少 {name}")
    if args.speed < 0.5 or args.speed > 2 or args.fps <= 0:
        raise ValueError("speed 需在 0.5–2 之间，fps 必须为正数")
    if args.check:
        print(f"配置已就绪；模型 {config['model']}；未发送 API 请求")
        return
    if args.text is None:
        parser.error("生成配音需要 --text 文稿路径")
    text = args.text.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("口播稿为空")
    metadata_path = args.out.with_suffix(".json")
    if args.out.exists() or metadata_path.exists():
        raise ValueError("输出已存在，请换一个文件名，避免覆盖已有成果")
    if args.speed != 1 and not shutil.which("ffmpeg"):
        raise ValueError("精确变速需要先安装 ffmpeg")
    data = generate(text, config, key)
    if args.speed != 1:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            target = Path(folder) / "speed.wav"
            source.write_bytes(data)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i",
                            str(source), "-filter:a", f"atempo={args.speed}",
                            "-c:a", "pcm_s16le", str(target)], check=True)
            data = target.read_bytes()
    with wave.open(io.BytesIO(data), "rb") as wav:
        seconds = wav.getnframes() / wav.getframerate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as file:
        file.write(data)
    metadata = {"audioFile": args.out.name, "durationSeconds": seconds,
                "fps": args.fps, "durationInFrames": math.ceil(seconds * args.fps),
                "model": config["model"], "voice": config["voice"],
                "speed": args.speed, "transcript": text,
                "captionTiming": "not_generated"}
    with metadata_path.open("x", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    print(f"已保存 {args.out}，时长 {seconds:.2f} 秒；字幕时间轴需另行对齐")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        # Never echo response bodies: they can contain credential details.
        reasons = {400: "请求参数或模型不兼容", 401: "密钥认证失败",
                   403: "权限、地区或计费限制", 404: "模型或接口不存在",
                   429: "配额不足或调用太频繁"}
        print(f"Gemini HTTP {error.code}：{reasons.get(error.code, '服务错误')}；未打印密钥或响应正文", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError:
        print("连接 Gemini 失败，请检查云端环境的代理和允许域名", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(f"配音失败：{error}", file=sys.stderr)
        sys.exit(1)
