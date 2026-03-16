# -*- coding: utf-8 -*-
"""
회의 녹음 원문(텍스트)을 분석해 주제·방안/결정사항을 추출합니다.
STT 결과 다듬기(교정)도 지원합니다.
- HTTP: OpenAI 호환 API(코파일럿·에이전트, Ollama, Open Web UI 등)
- CLI: 로컬 Copilot CLI (USE_COPILOT_CLI=True, API URL 비움)
- transcript_analyzer_config.py 에 고정값 넣어두면 그걸 사용 (환경변수보다 우선)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import List, Tuple


def _log(msg: str, **kwargs: object) -> None:
    """stderr 로그 (MCP/CLI 동작 추적용)"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    extra = " ".join(f"{k}={v!r}" for k, v in kwargs.items()) if kwargs else ""
    line = f"[{ts}] transcript_analyzer {msg}" + (f" {extra}" if extra else "")
    print(line, file=sys.stderr, flush=True)


try:
    import httpx
except ImportError:
    httpx = None

try:
    import transcript_analyzer_config as _cfg
    _CONFIG_URL = (getattr(_cfg, "DEFAULT_LLM_API_URL", None) or "").strip()
    _CONFIG_MODEL = (getattr(_cfg, "DEFAULT_LLM_MODEL", None) or "").strip()
    _CONFIG_KEY = (getattr(_cfg, "DEFAULT_LLM_API_KEY", None) or "").strip()
    _USE_COPILOT_CLI = getattr(_cfg, "USE_COPILOT_CLI", False)
except ImportError:
    _CONFIG_URL = _CONFIG_MODEL = _CONFIG_KEY = ""
    _USE_COPILOT_CLI = False

_COPILOT_CLI_CMD = os.environ.get("STT_COPILOT_CLI_CMD", "copilot")
_COPILOT_CLI_TIMEOUT = 120


def _copilot_cli_chat(prompt: str) -> str:
    """
    로컬 Copilot CLI 로 한 번에 프롬프트 전달 후 응답만 반환.
    copilot -s -p "..." (비대화형, 응답만 출력). 실패 시 빈 문자열.
    """
    if not prompt or not prompt.strip():
        return ""
    prompt = prompt.strip()[:50000]  # CLI 인자 길이 여유
    env = os.environ.copy()
    env["COPILOT_ALLOW_ALL"] = "1"  # 비대화형 모드에 필요

    _log("Copilot CLI 호출 시작", cmd=_COPILOT_CLI_CMD, prompt_len=len(prompt), timeout=_COPILOT_CLI_TIMEOUT)
    try:
        out = subprocess.run(
            [_COPILOT_CLI_CMD, "-s", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=_COPILOT_CLI_TIMEOUT,
            env=env,
        )
        if out.returncode != 0:
            _log("Copilot CLI 실패", returncode=out.returncode, stderr=(out.stderr or "").strip()[:500])
            return ""
        result = (out.stdout or "").strip()
        _log("Copilot CLI 완료", response_len=len(result))
        return result
    except FileNotFoundError:
        _log("Copilot CLI 실패", error="command not found", cmd=_COPILOT_CLI_CMD)
        return ""
    except subprocess.TimeoutExpired:
        _log("Copilot CLI 실패", error="timeout", timeout=_COPILOT_CLI_TIMEOUT)
        return ""
    except Exception as e:
        _log("Copilot CLI 실패", error=str(e))
        return ""


def _llm_chat(url: str, headers: dict, model: str, system: str, user_content: str, max_tokens: int = 4096) -> str:
    """OpenAI 호환 chat completions 호출. 응답 content만 반환, 실패 시 빈 문자열."""
    if not url or not user_content.strip():
        return ""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content.strip()[:16000]},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return ""
    choice = data.get("choices", [{}])[0]
    return ((choice.get("message") or {}).get("content") or "").strip()


def polish_transcript(content: str) -> str:
    """
    STT 결과를 LLM으로 다듬습니다. 오타·띄어쓰기·문장 부호·문법을 보정하고,
    말한 내용과 구조는 유지합니다. API/CLI 미설정 또는 실패 시 원문을 그대로 반환합니다.
    """
    if not content or not content.strip():
        return content

    base_url = (_CONFIG_URL or os.environ.get("STT_LLM_API_URL", "")).strip().rstrip("/")
    use_cli = _USE_COPILOT_CLI and not base_url

    if use_cli:
        _log("Copilot CLI로 STT 다듬기 시작", content_len=len(content))
        prompt = """당신은 음성 인식(STT) 결과를 교정하는 도우미입니다.
- 오타, 잘못된 단어, 띄어쓰기, 문장 부호, 문법을 자연스럽게 고쳐주세요.
- 말한 내용과 의미, 순서는 바꾸지 마세요. 해석이나 요약을 하지 마세요.
- 제목(# 등)이나 타임스탬프가 있으면 형식만 유지한 채 해당 문장만 교정하세요.
- 답변에는 교정된 텍스트만 출력하고, 설명이나 부가 문구는 넣지 마세요.

아래 STT 원문을 교정한 결과만 출력하세요.

---
"""
        prompt += content.strip()[:16000]
        result = _copilot_cli_chat(prompt)
        if result:
            _log("Copilot CLI STT 다듬기 완료", result_len=len(result))
            return result
        _log("Copilot CLI STT 다듬기 실패, 원문 유지", content_len=len(content))
        return content

    if not base_url or httpx is None:
        return content

    api_key = (_CONFIG_KEY or os.environ.get("STT_LLM_API_KEY", "")).strip()
    if "/v1" in base_url:
        url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        url = f"{base_url.rstrip('/')}/v1/chat/completions"

    model = (_CONFIG_MODEL or os.environ.get("STT_LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    system = """당신은 음성 인식(STT) 결과를 교정하는 도우미입니다.
- 오타, 잘못된 단어, 띄어쓰기, 문장 부호, 문법을 자연스럽게 고쳐주세요.
- 말한 내용과 의미, 순서는 바꾸지 마세요. 해석이나 요약을 하지 마세요.
- 제목(# 등)이나 타임스탬프가 있으면 형식만 유지한 채 해당 문장만 교정하세요.
- 답변에는 교정된 텍스트만 출력하고, 설명이나 부가 문구는 넣지 마세요."""

    result = _llm_chat(url, headers, model, system, content, max_tokens=8192)
    return result if result else content


def extract_meeting_fields(content: str) -> Tuple[str, str, List[str]]:
    """
    회의 녹음 원문 텍스트에서 주제, 방안/결정사항, 회의 내용 요약(불릿 리스트)을 추출합니다.
    반환: (주제, 결과/방안, 회의_내용_불릿_리스트)
    LLM API/CLI가 설정되지 않았거나 실패하면 ("", "", []) 반환.
    """
    if not content or not content.strip():
        return ("", "", [])

    base_url = (_CONFIG_URL or os.environ.get("STT_LLM_API_URL", "")).strip().rstrip("/")
    use_cli = _USE_COPILOT_CLI and not base_url

    json_rules = """규칙:
1. "주제": 회의 주제를 한 문장으로 요약. 없으면 빈 문자열 "".
2. "방안": 회의에서 결정된 사항·결과를 한 문장 또는 짧게. 없으면 "".
3. "회의_내용": 회의 흐름을 요약한 문장들의 배열. 예: ["회의를 시작하고 오늘 주제는 ...", "AI 도구 선택에 대해 의견을 나누었다.", ...] — 5~15개 정도로 논의 흐름이 드러나게.
4. 답변은 반드시 JSON 한 덩어리만 출력. 다른 설명 금지."""

    if use_cli:
        _log("Copilot CLI로 주제/방안/회의내용 추출 시작", content_len=len(content))
        prompt = "당신은 회의록 요약 도우미입니다. 아래 규칙대로 JSON 한 덩어리만 출력하세요.\n\n"
        prompt += json_rules + "\n\n원문:\n"
        prompt += content.strip()[:12000]
        text = _copilot_cli_chat(prompt)
        if not text:
            _log("Copilot CLI 주제/방안 추출 실패", content_len=len(content))
            return ("", "", [])
        _log("Copilot CLI 주제/방안 추출 완료", response_len=len(text))
    else:
        if not base_url or httpx is None:
            return ("", "", [])

        api_key = (_CONFIG_KEY or os.environ.get("STT_LLM_API_KEY", "")).strip()
        if "/v1" in base_url:
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = f"{base_url.rstrip('/')}/v1/chat/completions"

        model = (_CONFIG_MODEL or os.environ.get("STT_LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        prompt = "다음은 회의 녹음 원문입니다. 아래 규칙대로 JSON만 출력하세요.\n\n"
        prompt += json_rules + "\n\n원문:\n"
        prompt += content.strip()[:12000]
        system = "당신은 회의록 요약 도우미입니다. 요청된 JSON 형식으로만 답하세요."
        text = _llm_chat(url, headers, model, system, prompt, max_tokens=2048)
        if not text:
            return ("", "", [])

    # JSON 블록만 추출 (중첩 객체 허용하도록 재귀적이지 않은 단순 매칭)
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        text = json_match.group(0)
    try:
        out = json.loads(text)
        subject = (out.get("주제") or out.get("subject") or "").strip()
        action = (out.get("방안") or out.get("action_items") or out.get("방안/결정사항") or "").strip()
        raw_bullets = out.get("회의_내용") or out.get("content_bullets") or out.get("회의내용") or []
        if isinstance(raw_bullets, list):
            content_bullets = [str(x).strip() for x in raw_bullets if x]
        else:
            content_bullets = []
        return (subject, action, content_bullets)
    except Exception:
        return ("", "", [])
