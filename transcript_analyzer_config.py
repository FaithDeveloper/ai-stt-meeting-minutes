# -*- coding: utf-8 -*-
"""
회의록 분석용 LLM 고정 설정 (환경변수보다 우선)
- 여기 한 번만 넣어두면 매번 export 할 필요 없음.
- 코파일럿(에이전트) 등 사용 중인 API 주소·모델을 넣으면 됨.
- 비우면 분석 안 함 (주제/방안은 빈 채로 나옴).

로컬 Copilot CLI 사용: USE_COPILOT_CLI = True 로 두고 API URL 은 비우면,
설치된 GitHub Copilot CLI(copilot -p -s)로 다듬기/주제·방안 추출을 수행합니다.
"""

# LLM API 주소 (OpenAI 호환). 예: Ollama "http://localhost:11434/v1", 코파일럿/에이전트 주소 등
# 비우고 USE_COPILOT_CLI = True 면 로컬 Copilot CLI 사용
DEFAULT_LLM_API_URL = ""

# 사용할 모델명 (HTTP API 쓸 때만 사용. Copilot CLI 모드는 CLI 설정 따름)
DEFAULT_LLM_MODEL = ""

# API 키 (필요할 때만)
DEFAULT_LLM_API_KEY = ""

# True 면 API URL 대신 로컬 Copilot CLI(copilot -p -s) 사용. 로그인·모델은 CLI 설정 따름
USE_COPILOT_CLI = True
