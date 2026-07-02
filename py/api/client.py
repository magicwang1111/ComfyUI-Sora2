import asyncio
import time

import httpx

from .capabilities import API_PROVIDER_AZURE, DEFAULT_BASE_URL
from .exceptions import Sora2APIError

DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY = 2.0
LOG_PREFIX = "[ComfyUI-Sora2]"


def _timeout_config(timeout):
    return httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout)


def _headers(api_key, api_provider):
    if api_provider == API_PROVIDER_AZURE:
        return {"api-key": api_key}
    return {"Authorization": f"Bearer {api_key}"}


def _retryable(exc):
    return isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError))


class AsyncClient:
    def __init__(
        self,
        api_key,
        api_provider,
        base_url=DEFAULT_BASE_URL,
        timeout=120,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_delay=DEFAULT_RETRY_DELAY,
        poll_interval=10,
        generation_timeout=1800,
    ):
        api_key = str(api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required.")

        self.base_url = str(base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        self.timeout = int(timeout)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))
        self.poll_interval = max(1.0, float(poll_interval))
        self.generation_timeout = max(1, int(generation_timeout))
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=_timeout_config(self.timeout),
            headers=_headers(api_key, api_provider),
            follow_redirects=True,
        )

    async def request(self, method, path, expected_statuses=(200,), **kwargs):
        attempts = self.max_retries + 1
        response = None
        for attempt in range(1, attempts + 1):
            print(f"{LOG_PREFIX} {method} {path} attempt {attempt}/{attempts}")
            try:
                response = await self._client.request(method, path, **kwargs)
                break
            except httpx.TimeoutException as exc:
                raise TimeoutError(
                    f"API request timed out after {self.timeout}s for {method} {path}."
                ) from exc
            except httpx.HTTPError as exc:
                if _retryable(exc) and attempt < attempts:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise ConnectionError(f"API request failed for {method} {path}: {exc}") from exc

        if response.status_code not in expected_statuses:
            raise Sora2APIError.from_response(response)
        return response

    async def create_video(self, data, files=None):
        response = await self.request(
            "POST",
            "/videos",
            expected_statuses=(200, 201, 202),
            data=data,
            files=files,
        )
        return response.json()

    async def retrieve_video(self, video_id):
        response = await self.request("GET", f"/videos/{video_id}")
        return response.json()

    async def poll_video(self, video):
        video_id = str(video.get("id", "")).strip()
        if not video_id:
            raise ValueError("Video create response did not include an id.")

        started_at = time.monotonic()
        current = video
        while True:
            status = str(current.get("status", "")).lower()
            progress = current.get("progress")
            print(f"{LOG_PREFIX} video={video_id} status={status} progress={progress}")

            if status == "completed":
                return current
            if status in {"failed", "cancelled", "canceled"}:
                error = current.get("error")
                if isinstance(error, dict):
                    detail = error.get("message") or error.get("code")
                else:
                    detail = error
                raise ValueError(f"Sora 2 video generation ended with status={status}: {detail or 'no detail'}")
            if time.monotonic() - started_at >= self.generation_timeout:
                raise TimeoutError(
                    f"Sora 2 video generation did not finish within {self.generation_timeout}s "
                    f"(video_id={video_id}, last_status={status or 'unknown'})."
                )

            await asyncio.sleep(self.poll_interval)
            current = await self.retrieve_video(video_id)

    async def download_video(self, video_id):
        response = await self.request(
            "GET",
            f"/videos/{video_id}/content",
            params={"variant": "video"},
        )
        if not response.content:
            raise ValueError("Video content response was empty.")
        return response.content

    async def close(self):
        await self._client.aclose()
