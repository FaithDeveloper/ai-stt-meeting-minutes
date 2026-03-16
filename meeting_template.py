# -*- coding: utf-8 -*-
"""
회의록 양식 템플릿 (별도 파일로 관리 — 언제든 수정 가능)
- 이미지(회의록 작성)와 동일한 형태: 회의 기록 → 회의 내용(불릿) → 결과 → 회의 종료
- {{날짜}}, {{장소}} 등은 코드에서 채워 넣습니다.
"""

from typing import List, Optional

# 회의록 마크다운 템플릿 — 회의 기록 / 회의 내용 / 결과 / 회의 종료 형식
TEMPLATE_BASE = """# 회의록

**회의 기록**
- **회의일자**: {{날짜}}
- **장소**: {{장소}}
- **참석자**: {{참석자}}
- **주제**: {{주제}}

**회의 내용**
{{회의_내용}}

**결과**
{{결과}}

**회의 종료**
{{회의_종료}}
"""

# 치환 시 사용할 기본값 (비울 항목)
DEFAULTS = {
    "날짜": "",
    "장소": "",
    "참석자": "",
    "주제": "",
    "회의_내용": "",
    "결과": "",
    "회의_종료": "회의는 완료되었으며, 의견이 없는 것으로 보입니다.",
}


def _format_bullets(items: List[str]) -> str:
    """문자열 리스트를 마크다운 불릿 목록으로 반환"""
    if not items:
        return ""
    return "\n".join(f"- {s.strip()}" for s in items if s and s.strip())


def format_meeting_memo(
    content: str,
    date: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[str] = None,
    subject: Optional[str] = None,
    action_items: Optional[str] = None,
    content_bullets: Optional[List[str]] = None,
    meeting_end: Optional[str] = None,
) -> str:
    """
    STT 결과를 바탕으로 회의록 양식(회의 기록 / 회의 내용 / 결과 / 회의 종료)으로 채웁니다.
    content_bullets 가 있으면 '회의 내용'을 불릿으로, 없으면 content 는 사용하지 않고
    회의 내용란은 비우거나 기본 문구만 넣습니다. (이 형식에서는 요약 불릿을 권장)
    """
    out = TEMPLATE_BASE
    out = out.replace("{{날짜}}", (date or DEFAULTS["날짜"]).strip())
    out = out.replace("{{장소}}", (location or DEFAULTS["장소"]).strip())
    out = out.replace("{{참석자}}", (attendees or DEFAULTS["참석자"]).strip())
    out = out.replace("{{주제}}", (subject or DEFAULTS["주제"]).strip())

    meeting_content = _format_bullets(content_bullets) if content_bullets else (DEFAULTS["회의_내용"] or "")
    out = out.replace("{{회의_내용}}", meeting_content.strip() or "(내용 없음)")

    result_str = (action_items or DEFAULTS["결과"]).strip()
    out = out.replace("{{결과}}", result_str or "(결과 없음)")

    end_str = (meeting_end or DEFAULTS["회의_종료"]).strip()
    out = out.replace("{{회의_종료}}", end_str)
    return out
