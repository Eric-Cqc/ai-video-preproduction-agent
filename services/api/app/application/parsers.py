import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Protocol

from services.api.app.application.errors import InvalidRequest

MAX_PARSER_INPUT_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 1024 * 1024
MAX_CSV_ROWS = 10_000
MAX_CSV_COLUMNS = 100
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 100_000
PARSER_VERSION = "1.0.0"
_DISALLOWED_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    parser_id: str
    parser_version: str
    document: dict[str, object]
    character_count: int
    warning_count: int = 0
    truncated: bool = False


class ParserPort(Protocol):
    parser_id: str
    parser_version: str

    def parse(self, content: bytes, media_type: str) -> ParsedDocument: ...


def _decode(content: bytes) -> str:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidRequest("source object is not valid UTF-8 text") from error
    if _DISALLOWED_CONTROL.search(text):
        raise InvalidRequest("source object contains disallowed binary control bytes")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _document(media_type: str, text: str) -> dict[str, object]:
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise InvalidRequest("normalized extraction exceeds the character limit")
    return {
        "schema_version": "1.0.0",
        "media_type": media_type,
        "text": text,
        "sections": [{"kind": "document", "start": 0, "end": len(text)}],
    }


class PlainTextParser:
    parser_id = "stdlib_plain_text"
    parser_version = PARSER_VERSION

    def parse(self, content: bytes, media_type: str) -> ParsedDocument:
        text = _decode(content)
        return ParsedDocument(
            self.parser_id, self.parser_version, _document(media_type, text), len(text)
        )


class CsvParser:
    parser_id = "stdlib_csv"
    parser_version = PARSER_VERSION

    def parse(self, content: bytes, media_type: str) -> ParsedDocument:
        text = _decode(content)
        try:
            rows: list[list[str]] = []
            for row in csv.reader(io.StringIO(text, newline=""), strict=True):
                if len(rows) >= MAX_CSV_ROWS:
                    raise InvalidRequest("CSV row limit exceeded")
                if len(row) > MAX_CSV_COLUMNS:
                    raise InvalidRequest("CSV column limit exceeded")
                rows.append(row)
        except csv.Error as error:
            raise InvalidRequest("source object is not valid CSV") from error
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(rows)
        normalized = output.getvalue()
        return ParsedDocument(
            self.parser_id,
            self.parser_version,
            _document(media_type, normalized),
            len(normalized),
        )


class JsonParser:
    parser_id = "stdlib_json"
    parser_version = PARSER_VERSION

    def parse(self, content: bytes, media_type: str) -> ParsedDocument:
        text = _decode(content)

        def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in values:
                if key in result:
                    raise InvalidRequest("JSON contains duplicate object keys")
                result[key] = value
            return result

        def invalid_constant(_: str) -> object:
            raise InvalidRequest("JSON non-finite numbers are not supported")

        try:
            value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
        except InvalidRequest:
            raise
        except (json.JSONDecodeError, RecursionError) as error:
            raise InvalidRequest("source object is not valid bounded JSON") from error
        self._validate_shape(value)
        normalized = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return ParsedDocument(
            self.parser_id,
            self.parser_version,
            _document(media_type, normalized),
            len(normalized),
        )

    @staticmethod
    def _validate_shape(root: object) -> None:
        stack: list[tuple[object, int]] = [(root, 1)]
        nodes = 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            if nodes > MAX_JSON_NODES:
                raise InvalidRequest("JSON node limit exceeded")
            if depth > MAX_JSON_DEPTH:
                raise InvalidRequest("JSON depth limit exceeded")
            if isinstance(value, dict):
                stack.extend((child, depth + 1) for child in value.values())
            elif isinstance(value, list):
                stack.extend((child, depth + 1) for child in value)


def parser_for_media_type(media_type: str) -> ParserPort:
    parsers: dict[str, ParserPort] = {
        "text/plain": PlainTextParser(),
        "text/csv": CsvParser(),
        "application/json": JsonParser(),
    }
    parser = parsers.get(media_type)
    if parser is None:
        raise InvalidRequest("source media type is not supported for deterministic parsing")
    return parser
