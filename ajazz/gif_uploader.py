"""
ajazz/gif_uploader.py
──────────────────────────────────────────────
GIF → RGB565 변환 후 HID로 마우스 도크 스크린에 전송.

파이프라인:
  GIF 파일
    ↓ Pillow: 프레임 추출 + 리사이즈
    ↓ RGB565 인코딩 (빅엔디안)
    ↓ HID 청크 전송 (56바이트씩)
    ↓ 도크 스크린 표시

⚠️  프로토콜 주의:
  - 스크린 해상도(SCREEN_WIDTH/HEIGHT)는 protocol.py에서 설정
  - IMG_CHUNK_SIZE, 커맨드 바이트도 모델별로 다를 수 있음
  - aks075-linux (C 소스) 프로토콜 구조와 유사 가정
"""

import hid
import math
import time
import logging
from pathlib import Path
from PIL import Image, ImageSequence

from .protocol import (
    find_devices,
    build_image_start,
    build_image_chunk,
    build_image_end,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    IMG_CHUNK_SIZE,
)

logger = logging.getLogger(__name__)

INTER_FRAME_DELAY = 0.05   # 프레임간 HID 전송 딜레이 (초)
INTER_CHUNK_DELAY = 0.002  # 청크간 딜레이 (USB 버퍼 오버플로우 방지)


def _rgb565(r: int, g: int, b: int) -> int:
    """RGB888 → RGB565 빅엔디안."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _frame_to_rgb565(frame: Image.Image) -> bytes:
    """PIL 이미지 프레임 → RGB565 바이트 시퀀스."""
    frame = frame.convert("RGB").resize(
        (SCREEN_WIDTH, SCREEN_HEIGHT), Image.LANCZOS
    )
    out = bytearray()
    pixels = frame.load()
    for y in range(SCREEN_HEIGHT):
        for x in range(SCREEN_WIDTH):
            r, g, b = pixels[x, y]
            v = _rgb565(r, g, b)
            out.append((v >> 8) & 0xFF)  # 빅엔디안 Hi
            out.append(v & 0xFF)          # 빅엔디안 Lo
    return bytes(out)


class GifUploader:
    def __init__(self, on_progress=None):
        """
        on_progress(current_frame, total_frames): 진행상황 콜백
        """
        self._on_progress = on_progress

    def upload(self, gif_path: str | Path) -> bool:
        """
        GIF를 마우스 도크에 업로드.
        성공 시 True, 실패 시 False.
        """
        gif_path = Path(gif_path)
        if not gif_path.exists():
            logger.error(f"File not found: {gif_path}")
            return False

        devices = find_devices()
        if not devices:
            logger.error("No Ajazz device found")
            return False

        try:
            frames = self._extract_frames(gif_path)
            logger.info(f"GIF: {len(frames)} frames, {gif_path.name}")
        except Exception as e:
            logger.error(f"GIF parse failed: {e}")
            return False

        dev_info = devices[0]
        dev = hid.device()
        try:
            dev.open_path(dev_info["path"])
            for frame_idx, frame_data in enumerate(frames):
                self._send_frame(dev, frame_idx, len(frames), frame_data)
                if self._on_progress:
                    self._on_progress(frame_idx + 1, len(frames))
                time.sleep(INTER_FRAME_DELAY)
            logger.info("GIF upload complete")
            return True
        except Exception as e:
            logger.error(f"GIF upload failed: {e}")
            return False
        finally:
            try: dev.close()
            except Exception: pass

    # ─────────────────────────────
    #  내부 로직
    # ─────────────────────────────

    def _extract_frames(self, path: Path) -> list[bytes]:
        """GIF에서 모든 프레임을 RGB565로 변환."""
        img = Image.open(path)
        frames = []
        for frame in ImageSequence.Iterator(img):
            frames.append(_frame_to_rgb565(frame))
        return frames

    def _send_frame(
        self,
        dev,
        frame_idx: int,
        total_frames: int,
        frame_data: bytes,
    ):
        # 1. 프레임 전송 시작
        dev.write(build_image_start(frame_idx, total_frames, SCREEN_WIDTH, SCREEN_HEIGHT))
        time.sleep(INTER_CHUNK_DELAY)

        # 2. 데이터 청크 전송
        total_chunks = math.ceil(len(frame_data) / IMG_CHUNK_SIZE)
        for chunk_idx in range(total_chunks):
            chunk = frame_data[chunk_idx * IMG_CHUNK_SIZE:(chunk_idx + 1) * IMG_CHUNK_SIZE]
            dev.write(build_image_chunk(chunk_idx, chunk))
            time.sleep(INTER_CHUNK_DELAY)

        # 3. 프레임 전송 완료
        dev.write(build_image_end(frame_idx))
        time.sleep(INTER_CHUNK_DELAY)

        logger.debug(f"Frame {frame_idx+1}/{total_frames} sent ({total_chunks} chunks)")
