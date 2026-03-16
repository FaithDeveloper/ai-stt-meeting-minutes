# STT MCP (Speech-to-Text) – Open Web UI 연동

음성 파일을 업로드하면 **STT(Speech-to-Text)**로 변환하고 **마크다운(.md)**으로 정리하는 MCP 서버입니다.  
Open Web UI에서 mcpo를 통해 연동해 사용할 수 있습니다.

## 기능

- **음성 → 텍스트**: faster-whisper 기반 다국어 STT (한국어/영어/일본어/중국어 등)
- **마크다운 출력**: 구간별 타임스탬프 + 전문 정리
- **입력**: Base64 인코딩 음성 또는 음성 파일 URL
- **선택**: 결과를 지정한 경로에 `.md` 파일로 저장

**회의록 사용 시**: STT 결과는 **초안**입니다. 숫자·인명·전문 용어 등은 인식 오류가 있을 수 있으므로, 회의록으로 쓰실 때는 **필요한 부분을 수정해 사용**하시면 됩니다.

## STT 엔진 선택 (faster-whisper vs whisper.cpp vs 그 외)

| 방식 | 장점 | 단점 |
|------|------|------|
| **faster-whisper** (현재 기본) | Python만으로 설치·연동 간단, openai-whisper 대비 4배 빠르고 메모리 적음, GPU/CPU 모두 지원 | 모델 첫 로딩 시 다운로드 필요 |
| **whisper.cpp** | C++ 기반, 메모리·속도 최적화, Apple Silicon 등에서 잘 동작 | 별도 빌드·바이너리 필요, MCP와 연동하려면 서브프로세스 또는 HTTP 래퍼 필요 |
| **OpenAI Whisper (openai/whisper)** | 공식 구현, 사용 예제 많음 | 느리고 메모리 많이 사용 |

**권장**: 이 MCP는 **faster-whisper**를 기본으로 합니다.  
- 더 빠르고 가벼운 STT가 필요하면 → **faster-whisper** 유지  
- 이미 **whisper.cpp** 바이너리를 쓰고 있으면 → 별도 HTTP 서버(예: whisper.cpp의 `server` 예제)를 띄우고, 여기서는 `audio_url`로 그 서버 URL을 넘기는 방식으로 연동 가능 (아래 “whisper.cpp 연동” 참고).

### whisper.cpp 연동 (선택)

1. [whisper.cpp](https://github.com/ggerganov/whisper.cpp) 빌드 후 `server` 실행.
2. 음성 파일을 해당 서버에 업로드해 텍스트를 받는 API를 사용.
3. 이 MCP의 `transcribe_audio`는 **audio_url**을 지원하므로,  
   Open Web UI에서 “음성 파일 URL”을 넘기거나,  
   중간에 파일 업로드 → URL 반환 서비스를 두고 그 URL을 `audio_url`로 넘기면 됩니다.  
   (즉, STT 연산은 whisper.cpp가 하고, MCP는 “URL 받아서 마크다운 정리·저장” 역할만 할 수 있음.)

현재 코드는 **faster-whisper**로 직접 STT까지 수행합니다.

---

## 설치

### 1. 요구사항

- **Python 3.10+**
- (선택) FFmpeg – 일부 포맷 변환 시 필요. faster-whisper는 PyAV를 쓰므로 대부분 포맷은 동작.

### 2. 자동 설치

```bash
cd /Users/kchshin/Documents/ai_worksapace/stt_mcp
chmod +x setup.sh start.sh
./setup.sh
```

### 3. 수동 설치

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install mcpo
```

---

## 실행

```bash
./start.sh
```

- **8001**: MCP 도구 (Open Web UI에 이 주소 등록)
- **8002**: 음성 업로드 페이지 (브라우저에서 http://localhost:8002 로 접속해 파일 올리고 URL 받기)

포트 변경 시:

```bash
MCP_PORT=8003 UPLOAD_PORT=8004 ./start.sh
```

---

## Open Web UI 말고 쓰기 (CLI / Cursor / Copilot)

**STT 실행 한 번 = 회의록 요약까지 한번에** 됩니다. 음성 파일만 넣으면 STT → 교정 → 주제/회의내용 추출 → 회의록 형식으로 저장이 한 번에 수행되고, `stt/회의록_첨부_YYYYMMDD_HHMMSS.md` 형식으로 저장되며(타임스탬프로 겹침 방지), **요약(상단)** 과 **음성 기록 원문(하단 첨부)** 가 함께 들어갑니다.

Open Web UI 없이 **터미널 CLI**, **Cursor MCP**, **Copilot**만으로도 사용할 수 있습니다.

### 1) CLI로 로컬 파일 직접 STT (가장 간단)

로컬 음성 파일 경로만 주면 STT를 실행하고, 결과는 **stdout**과 **`stt/회의록_첨부_YYYYMMDD_HHMMSS.md`**에 저장됩니다.

```bash
cd /Users/kchshin/Documents/ai_worksapace/stt_mcp
source .venv/bin/activate

# 기본 실행 (결과 출력 + stt/회의록_첨부_타임스탬프.md 저장)
python stt_cli.py recording.m4a

# 한국어 지정, 결과를 추가로 다른 경로에 저장
python stt_cli.py ./voice.mp3 --language ko -o ./result.md

# stdout 출력 없이 파일만 저장
python stt_cli.py meeting.m4a --no-print
```

| 옵션 | 설명 |
|------|------|
| `audio_file` | 음성 파일 경로 (.m4a, .mp3, .wav, .flac 등) |
| `-o`, `--output` | 추가로 저장할 .md 경로 (선택) |
| `-l`, `--language` | `auto`, `ko`, `en`, `ja`, `zh` (기본: auto) |
| `-m`, `--model-size` | `tiny`, `base`, `small`, `medium`, `large-v3` (기본: base) |
| `--no-print` | stdout에 출력하지 않고 파일만 저장 |

**Copilot / Cursor와 함께:** CLI로 STT를 돌린 뒤, 생성된 `stt/회의록_첨부_*.md`를 열고 Copilot이나 Cursor에 "이 회의록 요약해줘", "결정 사항만 뽑아줘"처럼 요청하면 됩니다.

### 2) Cursor에서 MCP로 STT 사용

Cursor가 이 MCP 서버를 **stdio**로 실행해 두면, 채팅에서 `transcribe_audio` 도구를 쓸 수 있습니다.

1. **Cursor 설정**  
   - **Settings** → **MCP** (또는 **Features** → **MCP**) 에서 서버 추가.
2. **서버 설정 예시** (프로젝트 루트가 `stt_mcp`일 때):

```json
{
  "mcpServers": {
    "stt-mcp": {
      "command": "/Users/kchshin/Documents/ai_worksapace/stt_mcp/.venv/bin/python",
      "args": ["/Users/kchshin/Documents/ai_worksapace/stt_mcp/stt_mcp.py"]
    }
  }
}
```

3. **사용 방법**  
   - **방법 A**: 터미널에서 `python stt_cli.py recording.m4a` 로 STT 실행 → `stt/회의록_첨부_타임스탬프.md` 생성 후, Cursor 채팅에서 "stt/회의록_첨부_*.md 내용 요약해줘" 등으로 대화.  
   - **방법 B**: 음성 파일 URL이 있을 때(예: 업로드 서버 8002에서 받은 URL) Cursor 채팅에 그 URL을 붙여넣고 **"이 음성 URL STT해줘"**라고 하면, Cursor가 `transcribe_audio(audio_url="...")` 를 호출해 결과를 보여줍니다.

### 3) Copilot과 함께

- **CLI 사용**: `python stt_cli.py recording.m4a` 로 STT 실행 후, 생성된 **`stt/회의록_첨부_타임스탬프.md`** 를 열고 Copilot(챗/CLI)에 "이 회의록 기반으로 메일 초안 써줘" 등 요청.
- **Copilot CLI** (`USE_COPILOT_CLI = True`): 회의록의 주제·방안·회의 내용 요약은 이미 `transcript_analyzer_config.py`에서 Copilot CLI로 추출되므로, STT만 CLI로 돌려도 회의록 형태로 저장됩니다.

---

## Open Web UI 연동

1. **mcpo**로 MCP를 HTTP(OpenAPI)로 노출했으므로, Open Web UI가 이 주소에 접근할 수 있어야 합니다.
2. Open Web UI **Admin** → **External Tools** (또는 **Connections** 등)에서:
   - **Type**: `OpenAPI`
   - **URL**: `http://localhost:8001`  
     (Docker 안에서 Open Web UI를 쓰면 `http://host.docker.internal:8001` 등으로 호스트 쪽 포트 지정)
3. 저장 후 채팅에서 **도구**로 `transcribe_audio`가 보이면,  
   “음성 파일을 STT해서 마크다운으로 정리해줘” 같은 요청 시 해당 툴을 호출하도록 하면 됩니다.

### ⚠️ "audio_base64 또는 audio_url을 입력해주세요" 오류 (첨부파일이 안 넘어갈 때)

Open Web UI는 채팅에 첨부한 파일을 STT 도구 인자로 자동 전달하지 않습니다.  
첨부만 하고 "이 음성 STT해줘"라고 해도 도구에는 음성 데이터가 전달되지 않아 위 오류가 납니다.

**해결:** 1) 브라우저에서 **http://localhost:8002** 열기 → 2) 음성 파일 업로드 → 3) 나온 **URL 복사** → 4) Open Web UI 채팅에 URL 붙여넣고 "이 음성 STT해줘" 요청.

| 용도 | 주소 |
|------|------|
| Open Web UI에 등록할 MCP 도구 URL | http://localhost:8001 |
| 음성 업로드 후 URL 받는 페이지 | http://localhost:8002 |

### 음성 파일 전달 방식

- **audio_url** (권장): **http://localhost:8002** 업로드 페이지에서 음성을 올리고 받은 URL을 채팅에 붙여넣으면 됩니다. (위 "첨부파일이 안 넘어갈 때" 참고)
- **audio_base64**: 외부 시스템이 음성 바이트를 Base64로 인코딩해 넘길 때 사용. Open Web UI 채팅 첨부는 자동으로 전달되지 않습니다.

(Open Web UI 쪽에서 “업로드된 파일”을 base64나 URL로 어떻게 넘기는지는 해당 버전 문서를 참고하면 됩니다.)

---

### 예정: API 업로드 → MCP STT (Android / iOS 녹음 파일)

나중에 **별도 API**를 두고, 안드로이드/iOS 앱에서 **녹음 파일을 첨부해 업로드**하면, 그 API가 MCP를 호출해 STT 변환까지 하는 구성을 생각하고 계시면 아래처럼 연결하면 됩니다.

**흐름**

1. **모바일** (Android/iOS) → 녹음 파일을 **당신 API**로 업로드 (multipart/form-data 등).
2. **API 서버** → 업로드된 파일을 받은 뒤 둘 중 하나로 MCP에 전달:
   - **방식 A**: 파일을 저장하고 공개 URL을 만든 뒤 → MCP `transcribe_audio(audio_url="...")` 호출.
   - **방식 B**: 업로드 바이트를 Base64로 인코딩 → MCP `transcribe_audio(audio_base64="...")` 호출.
3. **MCP** → STT 수행 후 마크다운 텍스트(또는 `save_md_path`로 .md 저장) 반환.
4. **API** → 이 결과를 그대로 클라이언트에 응답하거나, DB/스토리지에 저장.

**모바일 녹음 포맷**

| 플랫폼 | 흔한 포맷 | 비고 |
|--------|-----------|------|
| **Android** | M4A(AAC), 3GP, MP4, OGG, WAV | MediaRecorder 기본은 3GP/M4A 등 |
| **iOS** | M4A(AAC), CAF, WAV | AVFoundation 기본은 M4A(AAC) |

faster-whisper(PyAV)는 **M4A, MP3, WAV, OGG, FLAC** 등 일반 포맷을 지원하므로, Android/iOS 기본 녹음 포맷은 그대로 넘겨도 됩니다.  
특이 포맷(예: AMR)만 올라오면 API 단에서 FFmpeg 등으로 M4A/WAV로 한 번 변환한 뒤 MCP에 넘기면 됩니다.

---

## 제공 툴: `transcribe_audio`

| 인자 | 타입 | 설명 |
|------|------|------|
| `audio_base64` | string | Base64 인코딩된 음성 데이터 (Open Web UI 업로드 시 사용) |
| `audio_url` | string | 음성 파일 다운로드 URL |
| `language` | string | `auto`, `ko`, `en`, `ja`, `zh` 등 (기본: `auto`) |
| `model_size` | string | `tiny`, `base`, `small`, `medium`, `large-v3` (기본: `base`) |
| `include_timestamps` | boolean | 구간별 타임스탬프 포함 여부 (기본: true) |
| `save_md_path` | string | 결과를 저장할 .md 파일 경로 (선택) |
| `title` | string | 마크다운 상단 제목 (선택) |

- **audio_base64** 와 **audio_url** 중 **하나는 반드시** 넣어야 합니다.

### 출력 예시 (마크다운)

```markdown
# 음성 기록 (STT)

- **언어**: ko
- **구간 수**: 12

---

**[00:00.00 - 00:02.50]**  
안녕하세요 오늘 회의 내용을 정리해 보겠습니다.

**[00:02.50 - 00:05.00]**  
첫 번째 안건은 예산 검토입니다.

---

## 전문 (타임스탬프 없음)

안녕하세요 오늘 회의 내용을 정리해 보겠습니다. 첫 번째 안건은 예산 검토입니다.
```

---

## STT 후처리 필터 (`filters.py`)

STT 결과에 적용하는 **정규식 치환 규칙**은 코드가 아니라 **별도 파일**에서 관리합니다.

- **파일**: `filters.py`
- **내용**: `RULES` 리스트에 `(정규식 패턴, 치환 문자열)` 튜플을 순서대로 나열
- **적용**: STT 결과(구간별 텍스트 + 전문)에 대해 `apply_filters()`가 위 규칙을 순서대로 적용

규칙 추가/삭제/순서 변경은 **이 파일만 수정**하면 되며, MCP 서버 재시작 후 반영됩니다.  
예: `"12시 반"` → `"12시 30분"`, `"10하는 시인 56분"` → `"10시 56분"` 등 시간 표현 정규화가 기본 포함되어 있습니다.

---

## 회의록 양식 (`meeting_template.py`)

STT 결과는 **일반적인 회의록 양식**으로 감싸져서 나갑니다. 양식은 **별도 파일**에서 관리하므로 언제든 수정할 수 있습니다.

- **파일**: `meeting_template.py`
- **내용**: `TEMPLATE`(마크다운 문자열)와 `DEFAULTS`(비울 항목 기본값)
- **항목**: 회의일(날짜), 장소, 참석자, 주제, 내용(녹음 원문), 방안/결정사항
- **회의일**: 음성 파일 URL인 경우 서버의 `Last-Modified`에서 추출 가능하면 자동 기입, 아니면 비움. 업로드 서버(8002)는 파일 제공 시 `Last-Modified`를 붙이므로, 업로드한 파일로 STT 시 회의일이 채워질 수 있습니다.
- **주제·방안/결정사항**: 녹음 원문(텍스트)을 **LLM으로 분석**해서 채웁니다. `STT_LLM_API_URL`이 설정되어 있을 때만 동작하며, 방안/결정사항이 없으면 해당 섹션은 **넣지 않습니다**.
- **장소·참석자**: 기본은 비어 있음. `meeting_template.py`의 `TEMPLATE_BASE`나 `DEFAULTS`를 바꾸면 형식·기본값을 변경할 수 있습니다.

**회의록 주제/방안 자동 채우기 — LLM 고정 설정 (선택)**

회의록의 "주제", "방안/결정사항"을 **녹음 원문을 분석해서** 채우려면, 쓸 LLM을 한 번만 지정해 두면 됩니다. **로컬 Ollama를 안 써도 되고**, 코파일럿(에이전트) 등 사용 중인 API 주소만 넣으면 됩니다.

**방법 1: 고정 설정 파일 (권장)**  
`transcript_analyzer_config.py` 를 열어서 아래만 채우면 됩니다. 환경변수 안 써도 됨.

```python
DEFAULT_LLM_API_URL = "여기에_코파일럿_또는_에이전트_API_주소"  # 예: http://localhost:11434/v1
DEFAULT_LLM_MODEL = "사용할_모델명"
DEFAULT_LLM_API_KEY = ""  # 필요할 때만
```

- 비우면 분석 안 함(주제·방안 빈 채).  
- 한 번 넣어두면 그걸로 고정이라 **로컬 Ollama 따로 안 써도 됨** (코파일럿/에이전트 주소 넣은 경우).

**방법 2: 환경변수**  
고정 파일 대신 터미널에서 `export STT_LLM_API_URL="..."` 등으로 넣어도 됩니다. 고정 파일이 있으면 그게 우선입니다.

**방법 3: 로컬 Copilot CLI**  
로컬에 [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/cli-command-reference)가 설치·로그인되어 있다면, API URL을 비우고 `transcript_analyzer_config.py`에서 `USE_COPILOT_CLI = True` 로 두면 됩니다. 다듬기와 주제/방안 추출이 `copilot -s -p "..."` 비대화형 호출로 동작합니다. 모델·권한은 CLI 설정을 따릅니다. (`STT_COPILOT_CLI_CMD` 환경변수로 실행 파일 경로 지정 가능.)

---

**사내 코파일럿/에이전트(월 요금 서비스) 쓰는 경우 — 어떻게 돌리게 되나**

1. **IT/관리자에게 받을 것**  
   - **API Base URL** (예: `https://copilot.회사도메인.com/v1`)  
   - **모델명** (해당 서비스에서 쓰는 채팅 모델 이름)  
   - **API 키** (해당 서비스가 인증용 키를 줄 경우만)

2. **여기 프로젝트에서 넣는 곳**  
   - `transcript_analyzer_config.py` 열기  
   - `DEFAULT_LLM_API_URL` = IT가 준 **API Base URL**  
   - `DEFAULT_LLM_MODEL` = IT가 준 **모델명**  
   - 필요하면 `DEFAULT_LLM_API_KEY` = IT가 준 **API 키**

3. **실제로 어떻게 돌아가는지**  
   - 사용자가 음성 올리고 “회의록 만들어줘” 요청  
   - MCP가 음성 → STT → **회의 원문 텍스트**까지 만듦  
   - 그 **텍스트**를 위에 넣어둔 사내 API 주소로 **HTTP 요청** 한 번 보냄 (주제/방안 추출 요청)  
   - 사내 서버가 주제·방안만 골라서 응답  
   - MCP가 그걸 회의록 양식에 넣어서 `stt/` 폴더에 저장·반환  

   즉, **사내 서비스가 “회의 원문 보내주면 주제/방안만 추출해 주는 API”**를 제공해야 하고, 그 **API 주소를 config에 넣어두면** 그렇게 돌리게 됩니다.  
   IT에게 문의할 때 **“OpenAI 채팅 API 호환(chat/completions) 주소가 있나요?”**라고 하면 됩니다.

"음성 파일 갖고 회의록 만들어줘"라고 하면 기존처럼 STT 도구가 호출되고, 결과가 위 회의록 양식(분석 반영)으로 나옵니다.

---

## STT 결과 저장 (`stt/` 폴더)

STT가 성공하면 **결과 마크다운이 항상 `stt/` 폴더**에 저장됩니다.

- **파일명**: `회의록_첨부_YYYYMMDD_HHMMSS.md` (타임스탬프로 여러 회의록 겹침 방지)
- **경로**: 프로젝트 루트 기준 `stt/회의록_첨부_20260216_143052.md` 형태
- **용도**: CLI/Cursor/Copilot에서 바로 이 파일을 열어 요약·추가 편집할 수 있습니다. 도구 응답의 `saved_path`에 전체 경로가 포함됩니다.

---

## 문제 해결

### "No module named 'faster_whisper'"

```bash
source .venv/bin/activate
pip install faster-whisper
```

### "No module named 'mcp'"

```bash
pip install mcp httpx
```

### 첫 실행이 느림

faster-whisper가 선택한 `model_size`(예: base) 모델을 처음 한 번 다운로드합니다.  
기본 캐시 경로: `~/.cache/faster-whisper/`.

### 포트가 이미 사용 중

```bash
PORT=8002 ./start.sh
```

---

## 기술 스택

- **Python 3.10+**
- **mcp** – Model Context Protocol
- **faster-whisper** – STT (CTranslate2 기반)
- **httpx** – HTTP 클라이언트 (URL 오디오 다운로드)
- **mcpo** – MCP → OpenAPI 브리지 (Open Web UI 연동)

---

## 라이선스

MIT
