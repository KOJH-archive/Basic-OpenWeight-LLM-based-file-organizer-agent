from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_PROVIDER = "Ollama"
DEFAULT_ENDPOINTS = {
    "Ollama": "http://127.0.0.1:11434",
    "OpenAI 호환": "http://127.0.0.1:8080/v1",
}


class LocalLLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalModelConfig:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    endpoint: str = DEFAULT_ENDPOINTS[DEFAULT_PROVIDER]

    def validated(self) -> "LocalModelConfig":
        provider = self.provider.strip()
        model = self.model.strip()
        endpoint = self.endpoint.strip().rstrip("/")
        if provider not in DEFAULT_ENDPOINTS:
            raise LocalLLMError("지원하지 않는 로컬 모델 공급자입니다.")
        if not model:
            raise LocalLLMError("모델 이름을 입력하세요.")
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise LocalLLMError("개인정보 보호를 위해 로컬 HTTP 주소만 사용할 수 있습니다.")
        if parsed.username or parsed.password:
            raise LocalLLMError("인증 정보가 포함된 주소는 사용할 수 없습니다.")
        return LocalModelConfig(provider, model, endpoint)


def list_models(config: LocalModelConfig, timeout: float = 3.0) -> list[str]:
    cfg = config.validated()
    url = f"{cfg.endpoint}/api/tags" if cfg.provider == "Ollama" else f"{cfg.endpoint}/models"
    payload = _get_json(url, timeout)
    if cfg.provider == "Ollama":
        return sorted({item.get("name", "") for item in payload.get("models", []) if item.get("name")})
    return sorted({item.get("id", "") for item in payload.get("data", []) if item.get("id")})


def generate_suggestion(pattern_summary: str, config: LocalModelConfig, timeout: float = 90.0) -> str:
    cfg = config.validated()
    system = (
        "당신은 로컬 파일 정리 조언자입니다. 삭제, 명령 실행, 외부 전송을 제안하지 마세요. "
        "파일 내용이나 개인정보를 추측하지 말고 사용자가 검토할 짧은 한국어 제안 3개만 작성하세요."
    )
    if cfg.provider == "Ollama":
        url = f"{cfg.endpoint}/api/generate"
        body = {
            "model": cfg.model,
            "prompt": f"{system}\n\n{pattern_summary}",
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 700},
        }
        payload = _post_json(url, body, timeout)
        answer = payload.get("response", "")
    else:
        url = f"{cfg.endpoint}/chat/completions"
        body = {"model": cfg.model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": pattern_summary},
        ], "temperature": 0.2, "max_tokens": 700, "stream": False}
        payload = _post_json(url, body, timeout)
        choices = payload.get("choices", [])
        answer = choices[0].get("message", {}).get("content", "") if choices else ""
    answer = answer.strip() if isinstance(answer, str) else ""
    if not answer:
        raise LocalLLMError("로컬 모델이 빈 응답을 반환했습니다.")
    return answer


def fallback_suggestion(pattern_summary: str) -> str:
    return (
        "로컬 AI를 사용할 수 없어 안전한 기본 제안을 표시합니다.\n"
        "1. 먼저 드라이런으로 이동 대상과 충돌 여부를 확인하세요.\n"
        "2. 자주 반복되는 파일 형식만 별도 하위 폴더로 정리하세요.\n"
        "3. 오래된 파일과 같은 이름의 파일은 자동 변경하지 말고 직접 검토하세요.\n\n"
        f"감지 요약: {pattern_summary or '특별한 반복 패턴 없음'}"
    )


def _get_json(url: str, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise LocalLLMError("로컬 모델 서버에 연결할 수 없습니다.") from exc


def _post_json(url: str, body: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, json.dumps(body, ensure_ascii=False).encode("utf-8"),
        {"Content-Type": "application/json"}, method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.5)
    raise LocalLLMError("로컬 모델 제안을 생성하지 못했습니다.") from last_error
