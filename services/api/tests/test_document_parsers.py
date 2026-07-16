import json

import pytest

from services.api.app.application.errors import InvalidRequest
from services.api.app.application.parsers import (
    CsvParser,
    JsonParser,
    PlainTextParser,
    parser_for_media_type,
)


def test_plain_text_utf8_bom_and_newline_normalization() -> None:
    parsed = PlainTextParser().parse(b"\xef\xbb\xbfalpha\r\nbeta\rgamma", "text/plain")
    assert parsed.document["text"] == "alpha\nbeta\ngamma"
    assert parsed.character_count == len("alpha\nbeta\ngamma")
    assert parsed.document["sections"] == [
        {"kind": "document", "start": 0, "end": len("alpha\nbeta\ngamma")}
    ]


@pytest.mark.parametrize("content", [b"\xff\xfe", b"hello\x00world", b"hello\x07world"])
def test_plain_text_rejects_invalid_encoding_and_binary_controls(content: bytes) -> None:
    with pytest.raises(InvalidRequest):
        PlainTextParser().parse(content, "text/plain")


def test_csv_is_deterministic_and_bounded() -> None:
    parser = CsvParser()
    first = parser.parse(b'b,a\r\n"x,y",z\r\n', "text/csv")
    second = parser.parse(b'b,a\n"x,y",z\n', "text/csv")
    assert first.document == second.document
    assert first.document["text"] == 'b,a\n"x,y",z\n'

    with pytest.raises(InvalidRequest, match="row limit"):
        parser.parse(("x\n" * 10_001).encode(), "text/csv")
    with pytest.raises(InvalidRequest, match="column limit"):
        parser.parse((",".join("x" for _ in range(101))).encode(), "text/csv")


def test_json_canonicalization_depth_nodes_and_duplicate_keys() -> None:
    parser = JsonParser()
    left = parser.parse(b'{"b":2,"a":[1,true]}', "application/json")
    right = parser.parse(b'{ "a" : [1,true], "b": 2 }', "application/json")
    assert left.document == right.document
    assert left.document["text"] == '{"a":[1,true],"b":2}'

    with pytest.raises(InvalidRequest, match="duplicate"):
        parser.parse(b'{"a":1,"a":2}', "application/json")
    with pytest.raises(InvalidRequest, match="non-finite"):
        parser.parse(b'{"value":NaN}', "application/json")
    deep: object = 0
    for _ in range(33):
        deep = [deep]
    with pytest.raises(InvalidRequest, match="depth"):
        parser.parse(json.dumps(deep).encode(), "application/json")
    with pytest.raises(InvalidRequest, match="node"):
        parser.parse(json.dumps([0] * 100_001).encode(), "application/json")


def test_output_limit_and_unsupported_formats_are_explicit() -> None:
    with pytest.raises(InvalidRequest, match="character limit"):
        PlainTextParser().parse(b"x" * (1024 * 1024 + 1), "text/plain")
    for media_type in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        with pytest.raises(InvalidRequest, match="not supported"):
            parser_for_media_type(media_type)
