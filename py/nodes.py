import io
import json
import os
from pathlib import Path

from comfy_api.latest import InputImpl

from .api import (
    API_PROVIDER_AZURE,
    API_PROVIDER_OPENAI,
    API_PROVIDER_OPTIONS,
    DEFAULT_API_PROVIDER,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SECONDS,
    DEFAULT_SIZE,
    IMAGE_TO_VIDEO_SIZE_OPTIONS,
    MODELS,
    NODE_CATEGORY,
    OPENAI_BASE_URL,
    SECONDS_OPTIONS,
    SIZE_OPTIONS,
    AsyncClient,
    Sora2APIError,
    build_create_request,
    validate_request,
)
from .api.client import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_JSON_PATH = ROOT_DIR / "config.local.json"
AZURE_OPENAI_V1_SUFFIX = "/openai/v1"


def _load_json_config():
    if not CONFIG_JSON_PATH.exists():
        return {}
    try:
        with CONFIG_JSON_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read {CONFIG_JSON_PATH.name}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError(f"{CONFIG_JSON_PATH.name} must contain a JSON object.")
    return config


def _env(*names):
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _present(config, key):
    value = config.get(key)
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _is_azure_url(value):
    value = str(value).lower()
    return ".openai.azure.com" in value or ".services.ai.azure.com" in value


def _normalize_azure_base_url(value):
    endpoint = str(value).strip().rstrip("/")
    for suffix in ("/videos", "/video/generations/jobs"):
        if endpoint.lower().endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
    if endpoint.lower().endswith(AZURE_OPENAI_V1_SUFFIX):
        return endpoint
    if endpoint.lower().endswith("/openai"):
        return endpoint + "/v1"
    return endpoint + AZURE_OPENAI_V1_SUFFIX


def _resolve_provider(config):
    if _present(config, "api_provider"):
        provider = str(config["api_provider"]).strip().lower()
    else:
        provider = _env("SORA2_API_PROVIDER").lower()
        if not provider:
            candidate_url = (
                str(config.get("base_url", "")).strip()
                or _env("SORA2_BASE_URL", "OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT")
            )
            if _is_azure_url(candidate_url) or _env("AZURE_OPENAI_API_KEY"):
                provider = API_PROVIDER_AZURE
            elif candidate_url.startswith(OPENAI_BASE_URL) or _env("OPENAI_API_KEY"):
                provider = API_PROVIDER_OPENAI
            else:
                provider = DEFAULT_API_PROVIDER
    if provider not in API_PROVIDER_OPTIONS:
        raise ValueError(f"api_provider must be one of: {', '.join(API_PROVIDER_OPTIONS)}.")
    return provider


def _resolve_api_key(config, provider):
    if _present(config, "api_key"):
        return str(config["api_key"]).strip()
    key = _env("SORA2_API_KEY")
    if not key and provider == API_PROVIDER_AZURE:
        key = _env("AZURE_OPENAI_API_KEY")
    if not key and provider == API_PROVIDER_OPENAI:
        key = _env("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "API key is required. Use config.local.json, SORA2_API_KEY, "
            "AZURE_OPENAI_API_KEY, or OPENAI_API_KEY."
        )
    return key


def _resolve_base_url(config, provider):
    if _present(config, "base_url"):
        value = str(config["base_url"]).strip()
    else:
        value = _env("SORA2_BASE_URL", "OPENAI_BASE_URL")
        if not value and provider == API_PROVIDER_AZURE:
            value = _env("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT")
        if not value:
            value = DEFAULT_BASE_URL
    return _normalize_azure_base_url(value) if provider == API_PROVIDER_AZURE else value.rstrip("/")


def _number(config, key, default, value_type, minimum):
    value = config.get(key, default)
    try:
        parsed = value_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a {value_type.__name__}.") from exc
    if parsed < minimum:
        raise ValueError(f"{key} must be greater than or equal to {minimum}.")
    return parsed


def _resolve_runtime_client_kwargs():
    config = _load_json_config()
    provider = _resolve_provider(config)
    return {
        "api_key": _resolve_api_key(config, provider),
        "api_provider": provider,
        "base_url": _resolve_base_url(config, provider),
        "timeout": _number(config, "request_timeout", 120, int, 5),
        "max_retries": _number(
            config, "request_retries", DEFAULT_MAX_RETRIES, int, 0
        ),
        "retry_delay": _number(
            config, "retry_delay", DEFAULT_RETRY_DELAY, float, 0
        ),
        "poll_interval": _number(config, "poll_interval", 10, float, 1),
        "generation_timeout": _number(
            config, "generation_timeout", 1800, int, 1
        ),
    }


def _create_runtime_client():
    return AsyncClient(**_resolve_runtime_client_kwargs())


def _model_name(selected, override):
    return str(override).strip() or selected


def _json_response(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _api_error(exc):
    if exc.status_code in {401, 403}:
        raise ValueError(
            f"API request was rejected with {exc.status_code}. Check the API key, "
            "base_url, Azure resource permissions, and Sora deployment access."
        ) from exc
    if exc.status_code == 404:
        raise ValueError(
            "API returned 404. Check that base_url ends with /openai/v1 and that "
            "the resource supports the Sora 2 Videos API."
        ) from exc
    if exc.status_code == 429:
        raise ValueError("API rate limit exceeded (429). Wait and retry.") from exc
    raise ValueError(str(exc)) from exc


async def _generate(prompt, model, seconds, size, model_override, input_image=None):
    validate_request(model, prompt, seconds, size, input_image=input_image)
    request_model = _model_name(model, model_override)
    data, files = build_create_request(
        request_model, prompt, seconds, size, input_image=input_image
    )

    client = _create_runtime_client()
    try:
        try:
            initial = await client.create_video(data, files)
            final = await client.poll_video(initial)
            content = await client.download_video(final["id"])
        except Sora2APIError as exc:
            _api_error(exc)
    finally:
        await client.close()

    print(f"[ComfyUI-Sora2] video={final['id']} completed")
    return InputImpl.VideoFromFile(io.BytesIO(content)), _json_response(final)


class Sora2TextToVideoNode:
    CATEGORY = NODE_CATEGORY
    FUNCTION = "generate"
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "response_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (MODELS, {"default": DEFAULT_MODEL}),
                "seconds": (SECONDS_OPTIONS, {"default": DEFAULT_SECONDS}),
                "size": (SIZE_OPTIONS, {"default": DEFAULT_SIZE}),
            },
            "optional": {
                "model_override": ("STRING", {"default": ""}),
            },
        }

    async def generate(
        self,
        prompt,
        model=DEFAULT_MODEL,
        seconds=DEFAULT_SECONDS,
        size=DEFAULT_SIZE,
        model_override="",
    ):
        return await _generate(prompt, model, seconds, size, model_override)


class Sora2ImageToVideoNode:
    CATEGORY = NODE_CATEGORY
    FUNCTION = "generate"
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "response_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "input_image": ("IMAGE",),
                "model": (MODELS, {"default": DEFAULT_MODEL}),
                "seconds": (SECONDS_OPTIONS, {"default": DEFAULT_SECONDS}),
                "size": (
                    IMAGE_TO_VIDEO_SIZE_OPTIONS,
                    {"default": IMAGE_TO_VIDEO_SIZE_OPTIONS[0]},
                ),
            },
            "optional": {
                "model_override": ("STRING", {"default": ""}),
            },
        }

    async def generate(
        self,
        prompt,
        input_image,
        model=DEFAULT_MODEL,
        seconds=DEFAULT_SECONDS,
        size=IMAGE_TO_VIDEO_SIZE_OPTIONS[0],
        model_override="",
    ):
        return await _generate(
            prompt,
            model,
            seconds,
            size,
            model_override,
            input_image=input_image,
        )
