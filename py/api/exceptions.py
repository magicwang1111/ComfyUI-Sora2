class Sora2APIError(Exception):
    def __init__(self, status_code, message, error_type=None, code=None, response_body=None):
        self.status_code = status_code
        self.message = message or "Unknown API error"
        self.error_type = error_type
        self.code = code
        self.response_body = response_body
        type_label = f" {error_type}" if error_type else ""
        super().__init__(f"API request failed ({status_code}{type_label}): {self.message}")

    @classmethod
    def from_response(cls, response):
        try:
            payload = response.json()
        except Exception:
            payload = {}

        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            error = {}
        return cls(
            response.status_code,
            error.get("message") or response.text,
            error_type=error.get("type"),
            code=error.get("code"),
            response_body=payload,
        )
