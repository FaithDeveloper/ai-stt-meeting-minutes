#!/usr/bin/env python3
"""
STT(Speech-to-Text) MCP 서버 - Open Web UI 연동
음성 파일 업로드 → STT → 마크다운(.md)으로 정리
faster-whisper 기반 (선택: whisper.cpp 연동 방법은 README 참고)
"""

import asyncio
import base64
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

def _log(msg: str, **kwargs: Any) -> None:
    """MCP 동작 로그 (stderr 출력)"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    extra = " ".join(f"{k}={v!r}" for k, v in kwargs.items()) if kwargs else ""
    line = f"[{ts}] MCP {msg}" + (f" {extra}" if extra else "")
    print(line, file=sys.stderr, flush=True)

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    print(f"Error: 필수 패키지를 찾을 수 없습니다: {e}", file=sys.stderr)
    print("설치: pip install mcp httpx faster-whisper", file=sys.stderr)
    sys.exit(1)

# faster-whisper는 transcribe 시에만 로드 (첫 호출 시 모델 다운로드)
_whisper_model = None
DEFAULT_MODEL_SIZE = "base"  # base, small, medium, large-v3
SUPPORTED_LANGUAGES = ("ko", "en", "ja", "zh", "auto")

# STT 결과를 저장할 기본 폴더 (컴플 업로드 등 다음 단계에서 사용)
STT_OUTPUT_DIR = Path(__file__).resolve().parent / "stt"


def _get_whisper_model(size: str = DEFAULT_MODEL_SIZE):
    """faster-whisper 모델 로드 (lazy load)"""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _log("faster-whisper 모델 로딩", size=size)
            # CPU: int8, GPU 있으면 cuda 사용 가능
            _whisper_model = WhisperModel(
                size,
                device="cpu",
                compute_type="int8",
                download_root=os.path.join(os.path.expanduser("~"), ".cache", "faster-whisper"),
            )
            _log("faster-whisper 모델 로드 완료")
        except Exception as e:
            _log("faster-whisper 로드 실패", error=str(e))
            raise RuntimeError(f"STT 모델 로드 실패: {e}") from e
    return _whisper_model


def _decode_audio_to_path(audio_base64: Optional[str], audio_url: Optional[str]) -> str:
    """base64 또는 URL에서 오디오를 임시 파일로 저장하고 경로 반환"""
    if audio_base64:
        data = base64.b64decode(audio_base64)
        suffix = ".wav"
        # 간단히 헤더로 형식 추정
        if data[:4] == b"fLaC":
            suffix = ".flac"
        elif data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
            suffix = ".mp3"
        elif data[:4] == b"OggS":
            suffix = ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            return f.name

    if audio_url:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
            path = f.name
        try:
            resp = httpx.get(audio_url, timeout=60.0)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
        except Exception as e:
            if os.path.exists(path):
                os.unlink(path)
            raise ValueError(f"오디오 URL 다운로드 실패: {e}") from e

    raise ValueError("audio_base64 또는 audio_url 중 하나를 넣어주세요.")


def _get_meeting_date_from_url(audio_url: str) -> Optional[str]:
    """URL 의 Last-Modified 헤더에서 회의일(YYYY-MM-DD) 추출. 실패 시 None."""
    try:
        resp = httpx.head(audio_url, timeout=10.0)
        raw = resp.headers.get("Last-Modified")
        if not raw:
            return None
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


try:
    from filters import apply_filters
except ImportError:
    def apply_filters(text: str) -> str:
        return text or ""

try:
    from meeting_template import format_meeting_memo
except ImportError:
    def format_meeting_memo(content: str, **kwargs: Any) -> str:
        return content

try:
    from transcript_analyzer import extract_meeting_fields, polish_transcript
except ImportError:
    def extract_meeting_fields(content: str) -> tuple:
        return ("", "", [])

    def polish_transcript(content: str) -> str:
        return content


def _transcribe_sync(
    audio_path: str,
    language: str = "auto",
    model_size: str = DEFAULT_MODEL_SIZE,
    include_timestamps: bool = True,
) -> tuple[str, Optional[str]]:
    """동기 STT 실행. (markdown_text, detected_language) 반환."""
    model = _get_whisper_model(model_size)
    lang = None if language == "auto" else language
    segments_generator, info = model.transcribe(
        audio_path,
        language=lang,
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
    )
    segments = list(segments_generator)
    detected = getattr(info, "language", None) or "unknown"

    def _ts(s: float) -> str:
        m = int(s // 60)
        sec = s % 60
        return f"{m:02d}:{sec:05.2f}"

    lines = [
        "# 음성 기록 (STT)",
        "",
        f"- **언어**: {detected}",
        f"- **구간 수**: {len(segments)}",
        "",
        "---",
        "",
    ]
    if include_timestamps and segments:
        for s in segments:
            normalized_text = apply_filters(s.text.strip())
            lines.append(f"**[{_ts(s.start)} - {_ts(s.end)}]**")
            lines.append(normalized_text)
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 전문 (타임스탬프 없음)")
        lines.append("")
    
    # 전체 텍스트도 시간 표현 정규화
    full_text = " ".join(s.text.strip() for s in segments)
    full_text = apply_filters(full_text)
    
    # 단락 나누기 (문장 단위로 줄바꿈)
    for part in full_text.replace("。", "。\n").split("\n"):
        part = part.strip()
        if part:
            lines.append(part)
            lines.append("")

    return "\n".join(lines).strip(), detected


async def transcribe_audio(
    audio_base64: Optional[str] = None,
    audio_url: Optional[str] = None,
    language: str = "auto",
    model_size: str = DEFAULT_MODEL_SIZE,
    include_timestamps: bool = True,
    save_md_path: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    음성 → STT → 마크다운 텍스트.
    Open Web UI에서 음성 파일을 base64로 보내거나, audio_url로 전달 가능.
    """
    _log("transcribe_audio 진입", has_base64=bool(audio_base64), has_url=bool(audio_url))

    if not audio_base64 and not audio_url:
        return {
            "success": False,
            "error": "audio_base64 또는 audio_url 중 하나를 입력해주세요.",
            "markdown": "",
            "detected_language": None,
        }

    language = (language or "auto").strip().lower()
    if language not in ("auto",) and language not in SUPPORTED_LANGUAGES:
        language = "auto"
    model_size = (model_size or DEFAULT_MODEL_SIZE).strip().lower()
    if model_size not in ("tiny", "base", "small", "medium", "large-v2", "large-v3"):
        model_size = DEFAULT_MODEL_SIZE

    # 음성 URL 이 있으면 회의일 추출 시도 (Last-Modified)
    meeting_date: Optional[str] = None
    if audio_url:
        meeting_date = _get_meeting_date_from_url(audio_url)
        if meeting_date:
            _log("회의일 추출됨 (URL Last-Modified)", date=meeting_date)

    audio_path = None
    try:
        audio_path = _decode_audio_to_path(audio_base64, audio_url)
        _log("오디오 파일 준비됨", path=audio_path)

        # CPU 바운드이므로 스레드에서 실행
        loop = asyncio.get_event_loop()
        markdown_text, detected_lang = await loop.run_in_executor(
            None,
            lambda: _transcribe_sync(
                audio_path,
                language=language,
                model_size=model_size,
                include_timestamps=include_timestamps,
            ),
        )
        _log("transcribe 완료", detected_language=detected_lang, md_len=len(markdown_text))

        if title:
            markdown_text = f"# {title}\n\n" + markdown_text

        # STT 결과 다듬기 (LLM 설정 시: 오타·띄어쓰기·문법 보정)
        loop = asyncio.get_event_loop()
        markdown_text = await loop.run_in_executor(None, lambda: polish_transcript(markdown_text))
        if markdown_text:
            _log("STT 결과 LLM 교정 완료", md_len=len(markdown_text))

        # 텍스트 분석으로 주제·방안·회의 내용 요약 추출 (transcript_analyzer, STT_LLM_API_URL 설정 시)
        subject, action_items, content_bullets = await loop.run_in_executor(
            None, lambda: extract_meeting_fields(markdown_text)
        )
        if subject or action_items or content_bullets:
            _log("회의록 분석 완료", has_subject=bool(subject), has_action_items=bool(action_items), bullets=len(content_bullets or []))

        # 회의록 요약만 상단에, 원문은 하단 첨부로 한 파일에 한번에 저장
        raw_transcript = markdown_text  # 음성 기록 원문 (타임스탬프 포함)
        summary_md = format_meeting_memo(
            content="",
            date=meeting_date or "",
            subject=subject,
            action_items=action_items,
            content_bullets=content_bullets,
        )
        markdown_text = (
            summary_md
            + "\n\n---\n## 첨부: 음성 기록 원문\n\n"
            + raw_transcript
        )

        save_error = None
        stt_file_path = None

        # 1) stt 폴더에 첨부파일(고정 파일명)로 저장 — 요약 + 원문 한번에
        try:
            STT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stt_file_path = STT_OUTPUT_DIR / f"회의록_첨부_{ts}.md"
            saved_path_str = str(stt_file_path)
            footer = f"\n\n---\n✅ 파일 저장됨: `{saved_path_str}`"
            content_to_save = markdown_text + footer
            stt_file_path.write_text(content_to_save, encoding="utf-8")
            result_markdown = content_to_save
            _log("마크다운 저장 완료 (stt 폴더)", path=saved_path_str)
        except Exception as e:
            save_error = f"stt 폴더 저장 실패: {e}"
            result_markdown = markdown_text + f"\n\n---\n⚠️ 저장 실패 (결과는 정상): {save_error}"
            _log("마크다운 저장 실패 (stt)", path=str(STT_OUTPUT_DIR), error=str(e))

        # 2) 사용자가 save_md_path 를 지정한 경우 추가로 해당 경로에도 저장 (동일한 최종 형태)
        if save_md_path:
            try:
                save_path = Path(save_md_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                extra_footer = f"\n\n---\n✅ 파일 저장됨: `{save_md_path}`"
                save_path.write_text(markdown_text + extra_footer, encoding="utf-8")
                _log("마크다운 저장 완료 (지정 경로)", path=save_md_path)
            except Exception as e:
                save_error = (save_error or "") + f" / 지정 경로 저장 실패: {e}"
                if save_error and "저장 실패" not in result_markdown:
                    result_markdown = markdown_text + f"\n\n---\n⚠️ 저장 실패 (결과는 정상): {save_error}"
                _log("마크다운 저장 실패", path=save_md_path, error=str(e))

        result = {
            "success": True,
            "markdown": result_markdown,
            "detected_language": detected_lang,
            "saved_path": str(stt_file_path) if stt_file_path and stt_file_path.exists() else None,
        }
        if save_error:
            result["save_warning"] = save_error
        return result
    except ValueError as e:
        _log("transcribe_audio 오류", error=str(e))
        return {"success": False, "error": str(e), "markdown": "", "detected_language": None}
    except Exception as e:
        _log("transcribe_audio 오류", error=str(e))
        return {
            "success": False,
            "error": f"STT 처리 중 오류: {e}",
            "markdown": "",
            "detected_language": None,
        }
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except OSError:
                pass


# --- MCP 서버 ---
app = Server("stt-mcp")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """사용 가능한 툴 목록"""
    _log("list_tools 호출됨")
    return [
        Tool(
            name="transcribe_audio",
            description=(
                "음성을 텍스트(STT)로 변환합니다. "
                "사용자가 음성 파일 URL(예: http://localhost:8002/files/xxx.m4a)을 보내고 'STT해줘', '텍스트로 변환해줘', '음성 인식해줘'라고 하면 반드시 이 도구를 호출하고, audio_url에 그 URL을 넣으세요. "
                "audio_url 또는 audio_base64 중 하나는 필수입니다. 한국어/영어/일본어 지원."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "audio_base64": {
                        "type": "string",
                        "description": "Base64 인코딩된 음성 (선택)",
                    },
                    "audio_url": {
                        "type": "string",
                        "description": "음성 파일 URL. 사용자가 채팅에 붙여넣은 http://localhost:8002/files/... 형태의 URL을 그대로 넣으세요.",
                    },
                    "language": {
                        "type": "string",
                        "description": "언어 코드: auto(자동), ko, en, ja, zh 등. 기본값: auto",
                        "default": "auto",
                    },
                    "model_size": {
                        "type": "string",
                        "description": "모델 크기: tiny, base, small, medium, large-v3. 정확도↑ 메모리↑ (기본: base)",
                        "default": "base",
                    },
                    "include_timestamps": {
                        "type": "boolean",
                        "description": "구간별 타임스탬프 포함 여부",
                        "default": True,
                    },
                    "save_md_path": {
                        "type": "string",
                        "description": "결과를 저장할 .md 파일 경로 (선택)",
                    },
                    "title": {
                        "type": "string",
                        "description": "마크다운 상단 제목 (선택)",
                    },
                },
                "required": [],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """툴 실행"""
    _log("call_tool 진입", name=name)

    if name != "transcribe_audio":
        raise ValueError(f"알 수 없는 툴: {name}")

    audio_base64 = arguments.get("audio_base64") or None
    audio_url = arguments.get("audio_url") or None
    language = arguments.get("language") or "auto"
    model_size = arguments.get("model_size") or DEFAULT_MODEL_SIZE
    include_timestamps = arguments.get("include_timestamps", True)
    save_md_path = arguments.get("save_md_path") or None
    title = arguments.get("title") or None

    result = await transcribe_audio(
        audio_base64=audio_base64,
        audio_url=audio_url,
        language=language,
        model_size=model_size,
        include_timestamps=include_timestamps,
        save_md_path=save_md_path,
        title=title,
    )

    if result.get("success"):
        # markdown 에 이미 푸터(파일 저장됨/저장 실패)가 포함되어 있음 — stt 파일과 UI 표시 동일
        text = result["markdown"]
    else:
        text = f"❌ 오류: {result.get('error', '알 수 없는 오류')}"

    _log("call_tool 완료", name=name, success=result.get("success"))
    return [TextContent(type="text", text=text)]


async def main():
    """stdio MCP 서버 실행"""
    _log("서버 시작 (stdio)")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )
    _log("서버 종료")


if __name__ == "__main__":
    asyncio.run(main())
