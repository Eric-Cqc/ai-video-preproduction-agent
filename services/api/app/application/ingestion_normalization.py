import hashlib
import json

from foundation_contracts import validate_structured_brief
from jsonschema import ValidationError

from services.api.app.application.errors import InvalidRequest

MAX_STRUCTURED_CONTENT_BYTES = 128 * 1024


def canonicalize_structured_brief(content: dict[str, object]) -> tuple[dict[str, object], str]:
    try:
        validate_structured_brief(content)
    except ValidationError as error:
        raise InvalidRequest(
            "structured Brief content does not match the canonical schema"
        ) from error
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) > MAX_STRUCTURED_CONTENT_BYTES:
        raise InvalidRequest("structured Brief content exceeds the size limit")
    return content, hashlib.sha256(encoded).hexdigest()
