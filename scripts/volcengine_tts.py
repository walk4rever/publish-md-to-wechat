#!/usr/bin/env python3
"""
Volcengine TTS Client for Video Publisher

Synthesizes text to speech using Volcengine (ByteDance) TTS WebSocket API.
Returns MP3 audio bytes.

Protocol: Binary WebSocket with gzip-compressed JSON payloads.
Endpoint: wss://openspeech.bytedance.com/api/v1/tts/ws_binary

Required env vars:
  VOLCANO_TTS_APPID         — App ID from Volcengine console
  VOLCANO_TTS_ACCESS_TOKEN  — Access token

Optional env vars:
  VOLCANO_TTS_CLUSTER       — Cluster name (default: volcano_tts)
  VOLCANO_TTS_VOICE_TYPE    — Voice model (default: zh_female_qingxin_moon_bigtts)
  VOLCANO_TTS_WS_URL        — WebSocket URL override
"""

import gzip
import json
import os
import ssl
import struct
import uuid
import logging
from dataclasses import dataclass
from typing import Optional

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger("VolcengineTTS")


@dataclass(frozen=True)
class TTSConfig:
    """TTS configuration, loaded from environment."""
    app_id: str
    access_token: str
    cluster: str = "volcano_tts"
    voice_type: str = "zh_female_qingxin_moon_bigtts"
    ws_url: str = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
    speed_ratio: float = 1.0
    volume_ratio: float = 1.0
    pitch_ratio: float = 1.0
    encoding: str = "mp3"
    verify_ssl: bool = True


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def load_tts_config() -> TTSConfig:
    """Load TTS config from environment variables.

    Raises:
        ValueError: If required env vars are missing.
    """
    app_id = os.environ.get("VOLCANO_TTS_APPID", "")
    access_token = os.environ.get("VOLCANO_TTS_ACCESS_TOKEN", "")

    if not app_id or not access_token:
        raise ValueError(
            "Missing required env vars: VOLCANO_TTS_APPID and VOLCANO_TTS_ACCESS_TOKEN. "
            "Get them from https://console.volcengine.com/speech/service/8"
        )

    return TTSConfig(
        app_id=app_id,
        access_token=access_token,
        cluster=os.environ.get("VOLCANO_TTS_CLUSTER", "volcano_tts"),
        voice_type=os.environ.get("VOLCANO_TTS_VOICE_TYPE", "zh_female_qingxin_moon_bigtts"),
        ws_url=os.environ.get("VOLCANO_TTS_WS_URL", "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"),
        speed_ratio=float(os.environ.get("VOLCANO_TTS_SPEED_RATIO", "1.0")),
        volume_ratio=float(os.environ.get("VOLCANO_TTS_VOLUME_RATIO", "1.0")),
        pitch_ratio=float(os.environ.get("VOLCANO_TTS_PITCH_RATIO", "1.0")),
        verify_ssl=_env_bool("VOLCANO_TTS_VERIFY_SSL", True),
    )


def _build_request_payload(text: str, config: TTSConfig) -> dict:
    """Build the TTS request JSON payload."""
    return {
        "app": {
            "appid": config.app_id,
            "token": config.access_token,
            "cluster": config.cluster,
        },
        "user": {
            "uid": "publish-md-to-wechat",
        },
        "audio": {
            "voice_type": config.voice_type,
            "encoding": config.encoding,
            "speed_ratio": config.speed_ratio,
            "volume_ratio": config.volume_ratio,
            "pitch_ratio": config.pitch_ratio,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "submit",
        },
    }


def _build_ws_frame(payload: dict) -> bytes:
    """Build a Volcengine TTS binary WebSocket frame.

    Frame format:
      [Header 4 bytes] [Payload size 4 bytes BE] [Gzipped JSON payload]

    Header byte breakdown:
      byte 0: (protocol_version << 4) | header_size  → 0x11 (v1, 1 word header)
      byte 1: (message_type << 4) | flags            → 0x10 (full client request, no flags)
      byte 2: (serialization << 4) | compression     → 0x11 (JSON + gzip)
      byte 3: reserved                               → 0x00
    """
    json_bytes = json.dumps(payload).encode("utf-8")
    compressed = gzip.compress(json_bytes)

    header = bytes([0x11, 0x10, 0x11, 0x00])
    size = struct.pack(">I", len(compressed))
    return header + size + compressed


def _parse_tts_frame(data: bytes) -> dict:
    """Parse a Volcengine TTS response frame.

    Returns dict with keys:
      - audio: bytes or None
      - done: bool
      - error: str or None
    """
    if len(data) < 4:
        return {"audio": None, "done": True, "error": "Frame too short"}

    # byte 1: (message_type << 4) | flags
    message_type = (data[1] >> 4) & 0x0F
    # byte 2: (serialization << 4) | compression
    compression = data[2] & 0x0F

    header_size = (data[0] & 0x0F) * 4  # in bytes

    if message_type == 0x0B:
        # Audio-only response
        # Observed layout:
        #   [header][sequence(int32)][reserved(uint32)][payload_size(uint32)][audio bytes]
        # The server may also send an ACK-like frame:
        #   [header][sequence(int32)][reserved(uint32)]  (8 bytes after header, no audio)
        if len(data) < header_size + 8:
            return {"audio": None, "done": False, "error": None}

        sequence = struct.unpack(">i", data[header_size:header_size + 4])[0]

        # ACK/metadata frame (no payload size / no audio).
        if len(data) < header_size + 12:
            return {"audio": None, "done": sequence < 0, "error": None}

        payload_size = struct.unpack(">I", data[header_size + 8:header_size + 12])[0]
        audio_start = header_size + 12
        audio_data = data[audio_start:audio_start + payload_size]

        # sequence < 0 is usually the last chunk in ByteDance's protocol
        is_last = sequence < 0 or payload_size == 0
        return {"audio": audio_data, "done": is_last, "error": None}

    elif message_type == 0x0F:
        # Error response
        payload = data[header_size + 8:]
        if compression == 1:
            payload = gzip.decompress(payload)
        try:
            error_msg = json.loads(payload.decode("utf-8"))
            return {"audio": None, "done": True, "error": str(error_msg)}
        except Exception:
            return {"audio": None, "done": True, "error": payload.decode("utf-8", errors="replace")}

    elif message_type == 0x0C:
        # Frontend info / metadata frame — ignore
        return {"audio": None, "done": False, "error": None}

    return {"audio": None, "done": False, "error": None}


def synthesize(text: str, config: Optional[TTSConfig] = None) -> bytes:
    """Synthesize text to MP3 audio bytes.

    Args:
        text: Plain text to synthesize.
        config: TTS configuration. If None, loads from environment.

    Returns:
        MP3 audio bytes.

    Raises:
        ImportError: If websocket-client is not installed.
        ValueError: If config is invalid.
        RuntimeError: If TTS synthesis fails.
    """
    if websocket is None:
        raise ImportError(
            "websocket-client is required for TTS. Install: pip install websocket-client"
        )

    if config is None:
        config = load_tts_config()

    if not text.strip():
        return b""

    logger.info(f"Synthesizing {len(text)} chars with voice {config.voice_type}")

    payload = _build_request_payload(text, config)
    frame = _build_ws_frame(payload)

    # Connect and send
    ws_kwargs = {
        "header": [f"Authorization: Bearer;{config.access_token}"],
        "timeout": 30,
    }
    if not config.verify_ssl:
        ws_kwargs["sslopt"] = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

    ws = websocket.create_connection(config.ws_url, **ws_kwargs)

    try:
        ws.send_binary(frame)

        audio_chunks: list[bytes] = []
        idle_timeouts = 0

        while True:
            try:
                response = ws.recv()
            except websocket.WebSocketTimeoutException:
                idle_timeouts += 1
                # Avoid infinite wait if server doesn't send explicit done frame.
                if audio_chunks and idle_timeouts >= 2:
                    logger.debug("TTS stream timeout after audio received; finishing stream")
                    break
                if idle_timeouts >= 6:
                    raise RuntimeError("TTS stream timeout: no response from server")
                continue
            except websocket.WebSocketConnectionClosedException:
                break

            idle_timeouts = 0

            if isinstance(response, str):
                # Unexpected text frame
                logger.warning(f"Unexpected text frame: {response[:200]}")
                continue

            parsed = _parse_tts_frame(response)

            if parsed["error"]:
                raise RuntimeError(f"TTS error: {parsed['error']}")

            if parsed["audio"]:
                audio_chunks.append(parsed["audio"])

            if parsed["done"]:
                break

    finally:
        ws.close()

    result = b"".join(audio_chunks)
    logger.info(f"Synthesized {len(result)} bytes of audio")
    return result


def synthesize_scenes(
    narrations: list[str],
    output_dir: str,
    config: Optional[TTSConfig] = None,
) -> list[str]:
    """Synthesize multiple narration texts, saving each as an MP3 file.

    Args:
        narrations: List of plain text strings to synthesize.
        output_dir: Directory to save MP3 files.
        config: TTS configuration.

    Returns:
        List of output MP3 file paths.
    """
    if config is None:
        config = load_tts_config()

    os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []

    for i, text in enumerate(narrations):
        out_path = os.path.join(output_dir, f"scene_{i:03d}.mp3")

        if not text.strip():
            # Generate a short silence placeholder (empty MP3)
            # ffmpeg will handle duration from the image
            with open(out_path, 'wb') as f:
                f.write(b"")
            paths.append(out_path)
            continue

        audio_bytes = synthesize(text, config)
        with open(out_path, 'wb') as f:
            f.write(audio_bytes)

        logger.info(f"Scene {i+1}/{len(narrations)}: {out_path} ({len(audio_bytes)} bytes)")
        paths.append(out_path)

    return paths


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if len(sys.argv) < 2:
        print("Usage: python3 volcengine_tts.py <text> [output.mp3]")
        sys.exit(1)

    text = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "output.mp3"

    audio = synthesize(text)
    with open(out_path, 'wb') as f:
        f.write(audio)
    print(f"Saved {len(audio)} bytes → {out_path}")
