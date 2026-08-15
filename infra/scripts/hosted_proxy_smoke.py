"""Exercise the hosted API through the Caddy proxy with a deterministic workflow."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import os
import socket
import ssl
import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

JsonObject = dict[str, object]
_MISSING = object()
PILOT_COOKIE_NAME = "pilot_access"
DEFAULT_PROXY_ORIGIN = "http://caddy:80"


class SmokeFailure(RuntimeError):
    """A labelled hosted-smoke failure safe to print to the terminal."""


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_response_detail(response: httpx.Response) -> str:
    """Return bounded, non-body diagnostics for a failed HTTP assertion."""

    try:
        payload = response.json()
    except ValueError:
        return (
            f"content_type={response.headers.get('content-type', 'unknown')};"
            f" bytes={len(response.content)}"
        )
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return f"error_code={error['code']}"
    return "unexpected_json_response"


def _request(
    client: object,
    method: str,
    url: str,
    *,
    stage: str,
    expected_status: int | frozenset[int],
    headers: Mapping[str, str] | None = None,
    json_payload: object = _MISSING,
    content: bytes | None = None,
) -> httpx.Response:
    request_kwargs: dict[str, object] = {"headers": dict(headers or {})}
    if json_payload is not _MISSING:
        request_kwargs["json"] = json_payload
    if content is not None:
        request_kwargs["content"] = content
    try:
        response = client.request(method, url, **request_kwargs)  # type: ignore[attr-defined]
    except (httpx.HTTPError, OSError) as error:
        raise SmokeFailure(f"{stage}: transport error {type(error).__name__}") from error
    expected = frozenset({expected_status}) if isinstance(expected_status, int) else expected_status
    if response.status_code not in expected:
        raise SmokeFailure(
            f"{stage}: expected HTTP {sorted(expected)}, got {response.status_code} "
            f"({_safe_response_detail(response)})"
        )
    return response


def _response_object(response: httpx.Response, stage: str) -> JsonObject:
    try:
        payload = response.json()
    except ValueError as error:
        raise SmokeFailure(f"{stage}: response was not JSON") from error
    if not isinstance(payload, dict):
        raise SmokeFailure(f"{stage}: response JSON was not an object")
    return payload


def _text_field(payload: JsonObject, name: str, stage: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise SmokeFailure(f"{stage}: missing text field {name}")
    return value


def _object_field(payload: JsonObject, name: str, stage: str) -> JsonObject:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise SmokeFailure(f"{stage}: missing object field {name}")
    return value


def _list_field(payload: JsonObject, name: str, stage: str) -> list[object]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise SmokeFailure(f"{stage}: missing list field {name}")
    return value


def _with_key(base_headers: Mapping[str, str], key: str) -> dict[str, str]:
    return {**base_headers, "Idempotency-Key": key}


def _cookie_present(client: HostedProxyClient) -> bool:
    return any(
        cookie.name == PILOT_COOKIE_NAME and bool(cookie.value) for cookie in client.cookies.jar
    )


def _assert_session_cookie(response: httpx.Response, client: HostedProxyClient) -> None:
    set_cookie = response.headers.get("set-cookie", "")
    lowered = set_cookie.casefold()
    if not set_cookie or not _cookie_present(client):
        raise SmokeFailure("correct pilot login: session cookie was not stored")
    if "secure" not in {part.strip().casefold() for part in set_cookie.split(";")}:
        raise SmokeFailure("correct pilot login: session cookie was not Secure")
    if "httponly" not in {part.strip().casefold() for part in set_cookie.split(";")}:
        raise SmokeFailure("correct pilot login: session cookie was not HttpOnly")
    if "samesite=strict" not in lowered:
        raise SmokeFailure("correct pilot login: session cookie SameSite was not Strict")


class _CaddyHTTPSConnection(http.client.HTTPSConnection):
    """Connect to Caddy while presenting the configured pilot domain as TLS SNI."""

    def __init__(
        self,
        caddy_host: str,
        *,
        server_hostname: str,
        context: ssl.SSLContext,
        timeout: float,
    ) -> None:
        super().__init__(caddy_host, port=443, timeout=timeout, context=context)
        self._caddy_host = caddy_host
        self._server_hostname = server_hostname

    def connect(self) -> None:
        sock = socket.create_connection((self._caddy_host, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self._server_hostname)


class _CaddyProxyTransport(httpx.BaseTransport):
    """Route logical HTTPX URLs to the Caddy service without resolving the public domain."""

    def __init__(
        self,
        *,
        caddy_host: str,
        pilot_domain: str,
        tls_context: ssl.SSLContext,
        timeout: float,
    ) -> None:
        self._caddy_host = caddy_host
        self._pilot_domain = pilot_domain
        self._tls_context = tls_context
        self._timeout = timeout

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.scheme == "http":
            connection: http.client.HTTPConnection = http.client.HTTPConnection(
                self._caddy_host, port=80, timeout=self._timeout
            )
        elif request.url.scheme == "https":
            connection = _CaddyHTTPSConnection(
                self._caddy_host,
                server_hostname=self._pilot_domain,
                context=self._tls_context,
                timeout=self._timeout,
            )
        else:
            raise httpx.UnsupportedProtocol(f"unsupported proxy scheme {request.url.scheme}")

        headers = {
            name: value
            for name, value in request.headers.multi_items()
            if name.casefold() not in {"host", "accept-encoding"}
        }
        headers["Host"] = self._pilot_domain
        # The small stdlib bridge returns buffered bytes; avoid Caddy compression so HTTPX does
        # not need a streaming decoder outside its normal transport implementation.
        headers["Accept-Encoding"] = "identity"
        try:
            connection.request(
                request.method,
                request.url.raw_path.decode("ascii"),
                body=request.read(),
                headers=headers,
            )
            upstream = connection.getresponse()
            body = upstream.read()
            return httpx.Response(
                status_code=upstream.status,
                headers=upstream.getheaders(),
                content=body,
                request=request,
                extensions={
                    "http_version": b"HTTP/1.1",
                    "reason_phrase": upstream.reason.encode("ascii", "replace"),
                },
            )
        except (http.client.HTTPException, OSError) as error:
            raise httpx.NetworkError("Caddy proxy transport failed") from error
        finally:
            connection.close()


class HostedProxyClient:
    """HTTPX client with a logical origin that can switch from Caddy HTTP to HTTPS."""

    def __init__(
        self,
        *,
        base_url: str,
        pilot_domain: str,
        tls_context: ssl.SSLContext,
        timeout: httpx.Timeout,
    ) -> None:
        parsed = urlsplit(base_url)
        self._pilot_domain = pilot_domain
        self._origin = base_url.rstrip("/")
        self._proxy_mode = parsed.hostname == "caddy"
        transport: httpx.BaseTransport | None = None
        if self._proxy_mode:
            transport = _CaddyProxyTransport(
                caddy_host=parsed.hostname or "caddy",
                pilot_domain=pilot_domain,
                tls_context=tls_context,
                timeout=timeout.connect or 5.0,
            )
        self._client = httpx.Client(
            follow_redirects=True,
            headers={"Host": pilot_domain},
            timeout=timeout,
            trust_env=False,
            transport=transport,
        )

    @property
    def cookies(self) -> httpx.Cookies:
        return self._client.cookies

    def endpoint(self, path: str) -> str:
        return _url(self._origin, path)

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        if self._proxy_mode and self._origin.startswith("http://"):
            self._origin = f"https://{self._pilot_domain}"
        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HostedProxyClient:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _tls_context(pilot_domain: str) -> ssl.SSLContext:
    ca_bundle = os.environ.get("HOSTED_SMOKE_CA_BUNDLE", "").strip()
    insecure = os.environ.get("HOSTED_SMOKE_INSECURE") == "1"
    local_domain = pilot_domain in {"localhost", "127.0.0.1"}
    if insecure and not local_domain:
        raise SmokeFailure(
            "configuration: HOSTED_SMOKE_INSECURE=1 is allowed only for localhost/127.0.0.1"
        )
    if insecure:
        print(
            "WARNING: hosted proxy smoke is using unverified TLS for the local internal hop",
            file=sys.stderr,
        )
        return ssl._create_unverified_context()
    if ca_bundle:
        bundle_path = Path(ca_bundle)
        if not bundle_path.is_file():
            raise SmokeFailure("configuration: HOSTED_SMOKE_CA_BUNDLE does not exist")
        try:
            return ssl.create_default_context(cafile=str(bundle_path))
        except OSError as error:
            raise SmokeFailure("configuration: HOSTED_SMOKE_CA_BUNDLE is not usable") from error
    return ssl.create_default_context()


def _pilot_domain() -> str:
    value = os.environ.get("PILOT_DOMAIN", "").strip()
    if not value or any(character.isspace() for character in value) or "/" in value:
        raise SmokeFailure("configuration: PILOT_DOMAIN must be a host name")
    if urlsplit(f"//{value}").hostname is None:
        raise SmokeFailure("configuration: PILOT_DOMAIN must be a host name")
    return value


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SmokeFailure(f"configuration: {name} is required")
    return value


def _uuid_env(name: str) -> str:
    value = _required_env(name)
    try:
        UUID(value)
    except ValueError as error:
        raise SmokeFailure(f"configuration: {name} must be a UUID") from error
    return value


def _health_check(client: object, url: str, stage: str) -> None:
    response = _request(client, "GET", url, stage=stage, expected_status=200)
    payload = _response_object(response, stage)
    if payload.get("status") != "ok" or payload.get("service") != "foundation-api":
        raise SmokeFailure(f"{stage}: health contract did not report foundation-api ok")


def _assert_bootstrap(client: HostedProxyClient, organization_id: str, workspace_id: str) -> None:
    organization_stage = "bootstrap assertion organization"
    organization = _response_object(
        _request(
            client,
            "GET",
            client.endpoint(f"/api/v1/organizations/{organization_id}"),
            stage=organization_stage,
            expected_status=200,
        ),
        organization_stage,
    )
    if _text_field(organization, "id", organization_stage) != organization_id:
        raise SmokeFailure(f"{organization_stage}: configured ID did not match response")
    if organization.get("status") != "active":
        raise SmokeFailure(f"{organization_stage}: organization was not active")

    workspace_stage = "bootstrap assertion workspace"
    workspace = _response_object(
        _request(
            client,
            "GET",
            client.endpoint(f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"),
            stage=workspace_stage,
            expected_status=200,
        ),
        workspace_stage,
    )
    if _text_field(workspace, "id", workspace_stage) != workspace_id:
        raise SmokeFailure(f"{workspace_stage}: configured ID did not match response")
    if _text_field(workspace, "organization_id", workspace_stage) != organization_id:
        raise SmokeFailure(f"{workspace_stage}: organization ID did not match response")
    if workspace.get("status") != "active":
        raise SmokeFailure(f"{workspace_stage}: workspace was not active")


def _run_workflow(
    client: HostedProxyClient,
    *,
    organization_id: str,
    workspace_id: str,
    actor_subject: str,
    token: str,
) -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
    )
    try:
        source_bytes = fixture_path.read_bytes()
    except OSError as error:
        raise SmokeFailure("source fixture: could not be read") from error
    source_checksum = hashlib.sha256(source_bytes).hexdigest()
    correlation_id = f"hosted-{token}"
    common_headers = {"X-Correlation-Id": correlation_id}

    project_stage = "project create"
    project = _response_object(
        _request(
            client,
            "POST",
            client.endpoint(
                f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects"
            ),
            stage=project_stage,
            expected_status=201,
            headers=common_headers,
            json_payload={
                "name": f"Hosted Proxy Smoke Project {token}",
                "description": "Hosted deterministic proxy validation",
            },
        ),
        project_stage,
    )
    project_id = _text_field(project, "id", project_stage)
    if _text_field(project, "created_by_actor_subject", project_stage) != actor_subject:
        raise SmokeFailure(f"{project_stage}: fixed pilot actor was not used")
    root = client.endpoint(
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}"
    )

    asset_payload: JsonObject = {
        "display_name": f"hosted-brief-{token}.json",
        "original_filename": f"hosted-brief-{token}.json",
        "media_type": "application/json",
        "byte_size": len(source_bytes),
        "checksum_algorithm": "sha256",
        "checksum_value": source_checksum,
        "source_type": "api_declared",
    }
    asset_key = f"hosted-{token}-asset"
    asset_stage = "source asset create"
    asset_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/source-assets",
            stage=asset_stage,
            expected_status=201,
            headers=_with_key(common_headers, asset_key),
            json_payload=asset_payload,
        ),
        asset_stage,
    )
    asset = _object_field(asset_body, "source_asset", asset_stage)
    current_version = _object_field(asset_body, "current_version", asset_stage)
    asset_id = _text_field(asset, "id", asset_stage)
    asset_version_id = _text_field(current_version, "id", asset_stage)

    replay_stage = "source asset exact replay"
    replay_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/source-assets",
            stage=replay_stage,
            expected_status=200,
            headers=_with_key(common_headers, asset_key),
            json_payload=asset_payload,
        ),
        replay_stage,
    )
    if replay_body.get("replayed") is not True:
        raise SmokeFailure(f"{replay_stage}: response was not marked replayed")

    conflict_stage = "source asset changed-digest conflict"
    changed_asset_payload = {**asset_payload, "display_name": f"changed-{token}.json"}
    _request(
        client,
        "POST",
        f"{root}/source-assets",
        stage=conflict_stage,
        expected_status=409,
        headers=_with_key(common_headers, asset_key),
        json_payload=changed_asset_payload,
    )

    upload_stage = "source asset upload"
    _request(
        client,
        "POST",
        f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/uploads",
        stage=upload_stage,
        expected_status=201,
        headers={
            **_with_key(common_headers, f"hosted-{token}-upload"),
            "Content-Type": "application/octet-stream",
        },
        content=source_bytes,
    )

    extraction_stage = "document extraction"
    extraction_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/extractions",
            stage=extraction_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-parse"),
        ),
        extraction_stage,
    )
    extraction = _object_field(extraction_body, "extraction", extraction_stage)
    extraction_id = _text_field(extraction, "id", extraction_stage)

    brief_run_url = (
        f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/extractions/"
        f"{extraction_id}/brief-extraction-runs"
    )
    brief_run_key = f"hosted-{token}-brief-run"
    brief_run_stage = "brief extraction run"
    brief_run = _response_object(
        _request(
            client,
            "POST",
            brief_run_url,
            stage=brief_run_stage,
            expected_status=201,
            headers=_with_key(common_headers, brief_run_key),
            json_payload={},
        ),
        brief_run_stage,
    )
    brief_run_id = _text_field(brief_run, "run_id", brief_run_stage)
    brief_replay_stage = "brief extraction idempotent replay"
    brief_replay = _response_object(
        _request(
            client,
            "POST",
            brief_run_url,
            stage=brief_replay_stage,
            expected_status=200,
            headers=_with_key(common_headers, brief_run_key),
            json_payload={},
        ),
        brief_replay_stage,
    )
    if _text_field(brief_replay, "run_id", brief_replay_stage) != brief_run_id:
        raise SmokeFailure(f"{brief_replay_stage}: run identity changed")

    candidate_stage = "brief candidate read"
    candidate_body = _response_object(
        _request(
            client,
            "GET",
            f"{root}/brief-extraction-runs/{brief_run_id}/candidate",
            stage=candidate_stage,
            expected_status=200,
            headers=common_headers,
        ),
        candidate_stage,
    )
    candidate = _object_field(candidate_body, "candidate", candidate_stage)

    accept_stage = "explicit brief candidate accept"
    accepted = _response_object(
        _request(
            client,
            "POST",
            f"{root}/brief-extraction-runs/{brief_run_id}/accept",
            stage=accept_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-accept-brief"),
            json_payload={"accepted_content": candidate, "title": f"Hosted Brief {token}"},
        ),
        accept_stage,
    )
    brief_id = _text_field(accepted, "brief_id", accept_stage)
    brief_version_id = _text_field(accepted, "brief_version_id", accept_stage)

    concepts_stage = "three concept generation"
    concept_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/briefs/{brief_id}/versions/{brief_version_id}/concept-runs",
            stage=concepts_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-concepts"),
            json_payload={},
        ),
        concepts_stage,
    )
    candidates = _list_field(concept_body, "candidates", concepts_stage)
    if len(candidates) != 3:
        raise SmokeFailure(f"{concepts_stage}: expected 3 candidates, got {len(candidates)}")
    candidate_ids: list[str] = []
    for index, candidate_value in enumerate(candidates):
        if not isinstance(candidate_value, dict):
            raise SmokeFailure(f"{concepts_stage}: candidate {index} was not an object")
        candidate_ids.append(
            _text_field(candidate_value, "id", f"{concepts_stage} candidate {index}")
        )
    if len(set(candidate_ids)) != 3:
        raise SmokeFailure(f"{concepts_stage}: candidate IDs were not unique")
    concept_run = _object_field(concept_body, "run", concepts_stage)
    concept_run_id = _text_field(concept_run, "id", concepts_stage)

    select_stage = "explicit concept selection"
    _request(
        client,
        "POST",
        f"{root}/concept-runs/{concept_run_id}/candidates/{candidate_ids[1]}/select",
        stage=select_stage,
        expected_status=201,
        headers=_with_key(common_headers, f"hosted-{token}-select-concept"),
        json_payload={},
    )

    script_stage = "script generation after selection"
    script_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/concept-runs/{concept_run_id}/scripts",
            stage=script_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-script"),
            json_payload={},
        ),
        script_stage,
    )
    script_id = _text_field(script_body, "script_version_id", script_stage)

    storyboard_stage = "storyboard generation"
    storyboard_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/scripts/{script_id}/storyboards",
            stage=storyboard_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-storyboard"),
            json_payload={"provider_mode": "valid"},
        ),
        storyboard_stage,
    )
    storyboard_version = _object_field(storyboard_body, "version", storyboard_stage)
    storyboard_id = _text_field(storyboard_version, "id", storyboard_stage)

    shot_plan_stage = "shot plan generation"
    shot_plan_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/storyboards/{storyboard_id}/shot-plans",
            stage=shot_plan_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-shot-plan"),
            json_payload={"provider_mode": "valid"},
        ),
        shot_plan_stage,
    )
    shot_plan_version = _object_field(shot_plan_body, "version", shot_plan_stage)
    shot_plan_id = _text_field(shot_plan_version, "id", shot_plan_stage)

    approval_stage = "explicit planning-bundle approval"
    approval_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/planning-reviews",
            stage=approval_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-approve-bundle"),
            json_payload={
                "artifact_type": "planning_bundle",
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "outcome": "approved",
                "summary": "Hosted proxy smoke approval",
                "requested_changes": {},
            },
        ),
        approval_stage,
    )
    approval_review = _object_field(approval_body, "review", approval_stage)
    approval_review_id = _text_field(approval_review, "id", approval_stage)

    package_stage = "delivery package creation"
    package_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/delivery-packages",
            stage=package_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-delivery-package"),
            json_payload={
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "approval_review_id": approval_review_id,
            },
        ),
        package_stage,
    )
    package = _object_field(package_body, "package", package_stage)
    package_id = _text_field(package, "id", package_stage)
    package_manifest = _object_field(package, "manifest", package_stage)
    if package_manifest.get("schema_version") != "delivery-package-v1":
        raise SmokeFailure(f"{package_stage}: manifest schema version was incorrect")

    export_stage = "delivery ZIP export"
    export_body = _response_object(
        _request(
            client,
            "POST",
            f"{root}/delivery-packages/{package_id}/exports",
            stage=export_stage,
            expected_status=201,
            headers=_with_key(common_headers, f"hosted-{token}-delivery-zip"),
            json_payload={"format": "delivery-package.zip"},
        ),
        export_stage,
    )
    export = _object_field(export_body, "export", export_stage)
    export_id = _text_field(export, "id", export_stage)
    export_checksum = _text_field(export, "checksum", export_stage)
    export_byte_size = export.get("byte_size")
    if not isinstance(export_byte_size, int) or export_byte_size <= 0:
        raise SmokeFailure(f"{export_stage}: invalid byte_size")

    download_stage = "delivery ZIP download"
    download_response = _request(
        client,
        "GET",
        f"{root}/delivery-exports/{export_id}",
        stage=download_stage,
        expected_status=200,
        headers=common_headers,
    )
    downloaded = download_response.content
    if len(downloaded) != export_byte_size:
        raise SmokeFailure(f"{download_stage}: byte size did not match export metadata")
    if hashlib.sha256(downloaded).hexdigest() != export_checksum:
        raise SmokeFailure(f"{download_stage}: checksum did not match export metadata")
    expected_members = {
        "manifest.json",
        "script.json",
        "storyboard.json",
        "shot-plan.json",
        "shot-plan.csv",
        "README.txt",
    }
    try:
        with zipfile.ZipFile(io.BytesIO(downloaded)) as archive:
            if archive.testzip() is not None:
                raise SmokeFailure(f"{download_stage}: archive contained a corrupt member")
            if set(archive.namelist()) != expected_members:
                raise SmokeFailure(f"{download_stage}: ZIP membership was incomplete")
            manifest = json.loads(archive.read("manifest.json"))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise SmokeFailure(f"{download_stage}: invalid ZIP or manifest") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "delivery-package-v1":
        raise SmokeFailure(f"{download_stage}: manifest schema version was incorrect")
    lineage = manifest.get("lineage")
    if not isinstance(lineage, dict):
        raise SmokeFailure(f"{download_stage}: manifest lineage was missing")
    for name, expected in {
        "script_version_id": script_id,
        "storyboard_version_id": storyboard_id,
        "shot_plan_version_id": shot_plan_id,
    }.items():
        if lineage.get(name) != expected:
            raise SmokeFailure(f"{download_stage}: manifest lineage mismatch for {name}")

    membership_stage = "membership creation assertion"
    viewer = f"pilot:hosted-smoke-viewer-{token}"
    membership = _response_object(
        _request(
            client,
            "POST",
            client.endpoint(
                f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships"
            ),
            stage=membership_stage,
            expected_status=201,
            headers=common_headers,
            json_payload={"actor_subject": viewer, "role": "viewer"},
        ),
        membership_stage,
    )
    if _text_field(membership, "actor_subject", membership_stage) != viewer:
        raise SmokeFailure(f"{membership_stage}: actor subject did not round-trip")
    if _text_field(membership, "organization_id", membership_stage) != organization_id:
        raise SmokeFailure(f"{membership_stage}: organization ID did not round-trip")
    if _text_field(membership, "workspace_id", membership_stage) != workspace_id:
        raise SmokeFailure(f"{membership_stage}: workspace ID did not round-trip")
    if _text_field(membership, "role", membership_stage) != "viewer":
        raise SmokeFailure(f"{membership_stage}: role did not round-trip")

    cross_tenant_stage = "opaque cross-tenant project denial"
    other_organization_id = str(uuid4())
    _request(
        client,
        "GET",
        client.endpoint(
            f"/api/v1/organizations/{other_organization_id}/workspaces/{workspace_id}"
            f"/projects/{project_id}"
        ),
        stage=cross_tenant_stage,
        expected_status=404,
        headers=common_headers,
    )

    viewer_refusal_stage = "viewer identity mutation refusal"
    # This deliberately supplies temporary identity headers to prove hosted impersonation is
    # refused.
    _request(
        client,
        "POST",
        f"{root}/delivery-packages",
        stage=viewer_refusal_stage,
        expected_status=403,
        headers={
            **common_headers,
            "X-Actor-Subject": viewer,
            "X-Organization-Id": organization_id,
            "X-Workspace-Id": workspace_id,
            "Idempotency-Key": f"hosted-{token}-viewer-refusal",
        },
        json_payload={
            "script_version_id": script_id,
            "storyboard_version_id": storyboard_id,
            "shot_plan_version_id": shot_plan_id,
            "approval_review_id": approval_review_id,
        },
    )


def _run_smoke(assert_bootstrap: bool) -> None:
    pilot_domain = _pilot_domain()
    pilot_password = _required_env("PILOT_ACCESS_PASSWORD")
    organization_id = _uuid_env("PILOT_ORGANIZATION_ID")
    workspace_id = _uuid_env("PILOT_WORKSPACE_ID")
    actor_subject = _required_env("PILOT_ACTOR_SUBJECT")
    base_url = os.environ.get("PILOT_BASE_URL", DEFAULT_PROXY_ORIGIN).strip().rstrip("/")
    parsed_base = urlsplit(base_url)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise SmokeFailure("configuration: PILOT_BASE_URL must be an absolute HTTP(S) URL")
    if parsed_base.query or parsed_base.fragment:
        raise SmokeFailure("configuration: PILOT_BASE_URL must not contain query or fragment")

    timeout = httpx.Timeout(30.0, connect=5.0)
    internal_base_url = os.environ.get("HOSTED_API_URL", "http://api:8000").rstrip("/")
    with httpx.Client(follow_redirects=False, timeout=timeout, trust_env=False) as preflight:
        _health_check(
            preflight,
            _url(internal_base_url, "/api/v1/health"),
            "API internal health preflight",
        )

    tls_context = _tls_context(pilot_domain)
    token = uuid4().hex[:12]
    with HostedProxyClient(
        base_url=base_url,
        pilot_domain=pilot_domain,
        tls_context=tls_context,
        timeout=timeout,
    ) as client:
        _health_check(client, client.endpoint("/api/v1/health"), "hosted proxy API health")

        unauthenticated_stage = "unauthenticated API call"
        _request(
            client,
            "GET",
            client.endpoint("/api/v1/pilot-context"),
            stage=unauthenticated_stage,
            expected_status=401,
        )

        wrong_password_stage = "wrong password login"
        _request(
            client,
            "POST",
            client.endpoint("/api/v1/pilot-access"),
            stage=wrong_password_stage,
            expected_status=frozenset({401, 403}),
            json_payload={"password": f"wrong-{token}"},
        )

        correct_password_stage = "correct password login"
        login_response = _request(
            client,
            "POST",
            client.endpoint("/api/v1/pilot-access"),
            stage=correct_password_stage,
            expected_status=204,
            json_payload={"password": pilot_password},
        )
        _assert_session_cookie(login_response, client)

        if assert_bootstrap:
            _assert_bootstrap(client, organization_id, workspace_id)
        _run_workflow(
            client,
            organization_id=organization_id,
            workspace_id=workspace_id,
            actor_subject=actor_subject,
            token=token,
        )

        logout_stage = "logout"
        _request(
            client,
            "POST",
            client.endpoint("/api/v1/pilot-access/logout"),
            stage=logout_stage,
            expected_status=204,
        )
        _request(
            client,
            "GET",
            client.endpoint("/api/v1/pilot-context"),
            stage="post-logout API call",
            expected_status=401,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assert-bootstrap",
        action="store_true",
        help="GET the configured pilot organization/workspace and assert their UUIDs",
    )
    args = parser.parse_args()
    try:
        _run_smoke(args.assert_bootstrap)
    except SmokeFailure as error:
        print(f"Hosted proxy smoke failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Hosted proxy smoke interrupted", file=sys.stderr)
        return 130
    print("Hosted proxy smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
