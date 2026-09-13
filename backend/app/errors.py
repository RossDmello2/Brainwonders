"""Only fixed, public messages cross the error boundary."""
from starlette.responses import JSONResponse

MESSAGES = {
    "REQUEST_INVALID": "The request is incomplete or not supported.",
    "REQUEST_FAILED": "The request could not be completed. Your work is still on this page.",
    "SERVICE_NOT_READY": "The service is temporarily unavailable. Please try later.",
    "SERVICE_BUSY": "The service is busy. Please try again shortly.",
    "SERVICE_RATE_LIMITED": "The service limit was reached. Please try later.",
    "INPUT_TOO_LARGE": "The file or request is too large. Choose a smaller file.",
    "REQUEST_TIMEOUT": "The upload took too long. Check your connection and try again.",
    "ORIGIN_NOT_ALLOWED": "This website is not configured to use the service.",
    "PROVIDER_KEY_REQUIRED": "Paste your own provider key before transcribing.",
    "PROVIDER_KEY_INVALID": "The key format is not valid. Paste your key again.",
    "PROVIDER_KEY_REJECTED": "The provider did not accept this key or its permissions.",
    "PROVIDER_PAYMENT_REQUIRED": "The provider requires an account payment or plan change. This is not an application charge.",
    "PROVIDER_RATE_LIMITED": "The provider's limit was reached. Check your account or try later.",
    "PROVIDER_RESPONSE_INVALID": "The provider returned an unreadable result. Try shorter audio or try later.",
    "PROVIDER_UNAVAILABLE": "The provider is unavailable. Please try later.",
    "PROVIDER_TIMEOUT": "The provider took too long. A retry may be billed as another request.",
    "MODEL_UNAVAILABLE": "The selected model is unavailable. No other model was used.",
    "AUDIO_FORMAT_UNSUPPORTED": "This audio format is not supported by the selected provider.",
    "AUDIO_EMPTY": "Choose a nonempty audio file or make a new recording.",
    "AUDIO_TOO_LONG": "Choose audio of 10 minutes or less.",
    "NO_SPEECH_RECOGNIZED": "No speech was recognized. Try a clearer recording.",
    "TEMPLATE_PAIR_REQUIRED": "Choose both the Word template and its matching JSON file.",
    "TEMPLATE_JSON_INVALID": "The template settings are not valid JSON. Ask the template author to check them.",
    "TEMPLATE_SCHEMA_UNSUPPORTED": "This template uses a settings version this application does not support.",
    "TEMPLATE_CONFIG_INVALID": "A template setting is missing or not allowed.",
    "TEMPLATE_ARCHIVE_INVALID": "This file is not a supported, intact Word template.",
    "TEMPLATE_TOO_COMPLEX": "This template is too large or complex for the free service.",
    "TEMPLATE_UNSAFE_CONTENT": "This template contains features that cannot be processed safely.",
    "TEMPLATE_PLACEHOLDER_SPLIT": "A placeholder is split by Word formatting. Retype it using one style.",
    "TEMPLATE_BINDING_MISMATCH": "The Word placeholders and JSON fields do not match.",
    "TEMPLATE_LOOP_INVALID": "A repeated section is not arranged correctly in the Word file.",
    "TEMPLATE_PREVIEW_MISMATCH": "The preview settings do not match this Word template.",
    "TEMPLATE_CHANGED": "The selected template changed. Validate the pair again.",
    "FIELD_INVALID": "Review the highlighted document fields.",
    "OUTPUT_NAME_INVALID": "The template produced an unsafe or overlong file name.",
    "DOCUMENT_TIMEOUT": "The template took too long to process. Try a simpler template.",
    "DOCUMENT_FAILED": "The document could not be created. Your text is still here.",
    "REVIEW_REQUIRED": "Preview the document and confirm that you have reviewed its details.",
    "CLEANUP_FAILED": "The service needs to restart before accepting more work.",
}


class AppError(Exception):
    def __init__(self, code, status=422, details=None, retryable=False, retry_after=None):
        self.code = code if code in MESSAGES else "REQUEST_FAILED"
        self.status = status
        self.details = (details or [])[:20]
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(self.code)


def error_response(error, request_id):
    return JSONResponse({"error": {"code": error.code, "message": MESSAGES[error.code],
        "retryable": error.retryable, "request_id": request_id, "details": error.details,
        "retry_after_seconds": error.retry_after}}, status_code=error.status,
        headers={"Retry-After": str(error.retry_after)} if error.retry_after else None)
