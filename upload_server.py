#!/usr/bin/env python3
"""
음성 파일 업로드 API (Open Web UI 첨부파일 대안)
POST /upload → 파일 저장 후 URL 반환 → 채팅에서 이 URL을 audio_url로 사용하면 STT 가능
"""

import os
import uuid
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
# 업로드 디렉터리 (프로젝트 내)
UPLOAD_DIR = Path(__file__).resolve().parent / "uploaded_audio"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 반환 URL에 쓸 기준 (MCP가 이 URL로 다운로드하므로, MCP 서버에서 접근 가능한 주소여야 함)
UPLOAD_PORT = int(os.environ.get("UPLOAD_PORT", "8002"))
UPLOAD_HOST = os.environ.get("UPLOAD_HOST", "http://localhost")
PUBLIC_BASE = os.environ.get("UPLOAD_PUBLIC_URL", f"{UPLOAD_HOST.rstrip('/')}:{UPLOAD_PORT}")


def get_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(title="STT MCP 업로드", description="음성 파일을 올리면 URL을 반환합니다. 이 URL을 Open Web UI 채팅에 넣고 STT 요청하세요.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def upload_form():
        return """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>음성 업로드 - STT MCP</title></head>
        <body style="font-family: sans-serif; max-width: 520px; margin: 2rem auto; padding: 1rem;">
        <h1>🎤 음성 파일 업로드</h1>
        <p id="portCheck" style="padding: 8px; border-radius: 6px; margin-bottom: 1rem; font-size: 0.9rem;"></p>
        <p>파일을 올리면 URL이 나옵니다. 이 URL을 Open Web UI 채팅에 붙여넣고 「이 음성 STT해줘」라고 하세요.</p>
        <div>
          <input type="file" id="fileInput" accept="audio/*,.mp3,.m4a,.wav,.ogg,.flac" style="margin: 0.5rem 0;" />
          <button type="button" id="btnUpload" style="display: block; margin-top: 0.5rem;">업로드 후 URL 받기</button>
        </div>
        <div id="out" style="margin-top: 1rem; padding: 0.75rem; background: #f0f0f0; border-radius: 6px; word-break: break-all;"></div>
        <p style="color:#666; font-size: 0.9rem;">지원: MP3, M4A, WAV, OGG, FLAC 등</p>
        <script>
        console.log("[DEBUG] 페이지 로드됨. 현재 주소:", window.location.href);
        (function() {
          var port = window.location.port || (window.location.protocol === "https:" ? "443" : "80");
          console.log("[DEBUG] 포트 확인:", port);
          var el = document.getElementById("portCheck");
          if (port !== "8002") {
            el.style.background = "#fff3cd";
            el.style.border = "1px solid #ffc107";
            el.innerHTML = "⚠️ 지금 주소가 <strong>8002</strong>가 아닙니다 (현재: " + port + "). 업로드는 <a href='http://localhost:8002' style='font-weight:bold;'>http://localhost:8002</a> 에서만 됩니다. 8001은 MCP 도구 전용입니다.";
          } else {
            el.style.background = "#d4edda";
            el.style.border = "1px solid #28a745";
            el.textContent = "✓ 올바른 주소입니다 (음성 업로드용 8002).";
          }
        })();
        document.getElementById("btnUpload").onclick = async function() {
          console.log("[DEBUG] 업로드 버튼 클릭됨");
          var fileInput = document.getElementById("fileInput");
          console.log("[DEBUG] 파일 input:", fileInput);
          console.log("[DEBUG] 선택된 파일:", fileInput.files);
          if (!fileInput.files || !fileInput.files[0]) {
            console.log("[DEBUG] 파일 미선택");
            document.getElementById("out").textContent = "파일을 먼저 선택하세요.";
            return;
          }
          var out = document.getElementById("out");
          out.textContent = "업로드 중...";
          console.log("[DEBUG] FormData 생성 시작");
          try {
            var fd = new FormData();
            var f = fileInput.files[0];
            console.log("[DEBUG] 파일 정보:", f.name, f.size, f.type);
            var ext = (f.name && f.name.lastIndexOf(".") >= 0) ? f.name.slice(f.name.lastIndexOf(".")) : ".audio";
            console.log("[DEBUG] 확장자:", ext);
            fd.append("file", f, "audio" + ext);
            console.log("[DEBUG] fetch 시작 -> /upload");
            var r = await fetch("/upload", { method: "POST", body: fd });
            console.log("[DEBUG] fetch 응답:", r.status, r.statusText);
            var j = await r.json().catch(function(e) { 
              console.error("[DEBUG] JSON 파싱 실패:", e);
              return { detail: "응답 파싱 실패 (status " + r.status + ")" }; 
            });
            console.log("[DEBUG] 응답 JSON:", j);
            if (r.ok && j.url) {
              out.innerHTML = "<p>아래 URL을 복사해서 채팅에 붙여넣으세요:</p><input type='text' readonly style='width:100%; box-sizing:border-box; padding:6px;' id='u'><button type='button' id='btnCopy' style='margin-top:6px;'>복사</button>";
              document.getElementById("u").value = j.url;
              console.log("[DEBUG] URL 설정됨:", j.url);
              document.getElementById("btnCopy").onclick = function() {
                navigator.clipboard.writeText(document.getElementById("u").value);
                this.textContent = "복사됨!";
              };
            } else {
              var err = (typeof j.detail === "string") ? j.detail : (Array.isArray(j.detail) ? j.detail.map(function(x){ return x.msg || (x.loc && x.loc.join(" ")); }).join(", ") : JSON.stringify(j));
              console.error("[DEBUG] 업로드 실패:", err);
              out.textContent = "오류: " + err;
            }
          } catch (err) {
            console.error("[DEBUG] 예외 발생:", err);
            out.textContent = "오류: " + (err.message || String(err));
          }
        };
        console.log("[DEBUG] 버튼 이벤트 연결 완료");
        </script>
        </body>
        </html>
        """

    @app.post("/upload")
    async def upload(file: UploadFile = File(..., description="음성 파일")):
        print(f"[UPLOAD] 요청 수신. filename={getattr(file, 'filename', 'UNKNOWN')}", flush=True)
        # 한글 등 비ASCII 파일명도 안전하게 처리 (확장자만 사용)
        raw_name = getattr(file, "filename", None) or ""
        try:
            ext = (Path(raw_name).suffix or ".audio").lower()
        except Exception:
            ext = ".audio"
        if ext not in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm", ".mp4", ".3gp", ".caf", ".audio"):
            ext = ".audio"
        fid = str(uuid.uuid4()) + ext
        path = UPLOAD_DIR / fid
        print(f"[UPLOAD] 저장 경로: {path}", flush=True)
        try:
            content = await file.read()
            print(f"[UPLOAD] 파일 크기: {len(content)} bytes", flush=True)
            if len(content) == 0:
                raise HTTPException(400, "빈 파일입니다.")
            path.write_bytes(content)
            print(f"[UPLOAD] 저장 완료", flush=True)
        except Exception as e:
            print(f"[UPLOAD] 저장 실패: {e}", flush=True)
            raise HTTPException(500, f"저장 실패: {e}")
        url = f"{PUBLIC_BASE.rstrip('/')}/files/{fid}"
        print(f"[UPLOAD] 반환 URL: {url}", flush=True)
        return {"url": url, "id": fid, "message": "이 URL을 채팅에 붙여넣고 '이 음성 STT해줘'라고 하세요."}

    @app.get("/files/{fid}")
    async def serve_file(fid: str):
        # 경로 이탈 방지
        if ".." in fid or "/" in fid or "\\" in fid:
            raise HTTPException(400, "잘못된 경로")
        path = UPLOAD_DIR / fid
        if not path.exists() or not path.is_file():
            raise HTTPException(404, "파일 없음")
        headers = {}
        try:
            from email.utils import formatdate
            mtime = path.stat().st_mtime
            headers["Last-Modified"] = formatdate(mtime, usegmt=True)
        except Exception:
            pass
        return FileResponse(path, filename=fid, headers=headers if headers else None)

    return app


app = get_app()
