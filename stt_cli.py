#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STT CLI — Open Web UI 없이 로컬에서 음성 파일을 STT하고 결과를 얻습니다.
사용 예:
  python stt_cli.py recording.m4a
  python stt_cli.py ./voice.mp3 --language ko
  python stt_cli.py recording.m4a -o ./result.md
결과는 기본으로 stt/회의록_첨부_YYYYMMDD_HHMMSS.md 에 저장됩니다 (타임스탬프로 겹침 방지).
"""

import argparse
import asyncio
import base64
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="로컬 음성 파일을 STT(음성→텍스트)로 변환합니다. 결과는 stdout과 stt/회의록_첨부_타임스탬프.md에 저장됩니다."
    )
    parser.add_argument(
        "audio_file",
        type=Path,
        help="음성 파일 경로 (.m4a, .mp3, .wav, .flac 등)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="추가로 저장할 .md 파일 경로 (선택)",
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default="auto",
        choices=["auto", "ko", "en", "ja", "zh"],
        help="언어 (기본: auto)",
    )
    parser.add_argument(
        "-m", "--model-size",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper 모델 크기 (기본: base)",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="stdout에 마크다운 출력하지 않음 (파일만 저장)",
    )
    args = parser.parse_args()

    path = args.audio_file.resolve()
    if not path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {path}", file=sys.stderr)
        sys.exit(1)
    if not path.is_file():
        print(f"오류: 파일이 아닙니다: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = path.read_bytes()
    except Exception as e:
        print(f"오류: 파일 읽기 실패: {e}", file=sys.stderr)
        sys.exit(1)

    audio_base64 = base64.b64encode(raw).decode("ascii")

    async def run_stt() -> dict:
        from stt_mcp import transcribe_audio
        return await transcribe_audio(
            audio_base64=audio_base64,
            language=args.language,
            model_size=args.model_size,
            include_timestamps=True,
            save_md_path=str(args.output) if args.output else None,
        )

    result = asyncio.run(run_stt())

    if not result.get("success"):
        print(f"오류: {result.get('error', '알 수 없는 오류')}", file=sys.stderr)
        sys.exit(1)

    if not args.no_print:
        print(result.get("markdown", ""))

    saved = result.get("saved_path")
    if saved:
        print(f"\n[저장됨] {saved}", file=sys.stderr)
    if result.get("save_warning"):
        print(f"[경고] {result['save_warning']}", file=sys.stderr)


if __name__ == "__main__":
    main()
