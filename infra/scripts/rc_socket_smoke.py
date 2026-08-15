"""Exercise the Local RC through running API and Web sockets only."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx

JsonObject = dict[str, object]
_MISSING = object()


class SmokeFailure(RuntimeError):
    """A labelled RC socket-smoke failure safe to print to the terminal."""


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
    client: httpx.Client,
    method: str,
    url: str,
    *,
    stage: str,
    expected_status: int,
    headers: dict[str, str] | None = None,
    json_payload: object = _MISSING,
    content: bytes | None = None,
) -> httpx.Response:
    request_kwargs: dict[str, object] = {"headers": headers or {}}
    if json_payload is not _MISSING:
        request_kwargs["json"] = json_payload
    if content is not None:
        request_kwargs["content"] = content
    try:
        response = client.request(method, url, **request_kwargs)
    except httpx.HTTPError as error:
        raise SmokeFailure(f"{stage}: transport error {type(error).__name__}") from error
    if response.status_code != expected_status:
        raise SmokeFailure(
            f"{stage}: expected HTTP {expected_status}, got {response.status_code} "
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


def _headers(
    actor: str, organization_id: str, workspace_id: str, correlation_id: str
) -> dict[str, str]:
    return {
        "X-Actor-Subject": actor,
        "X-Organization-Id": organization_id,
        "X-Workspace-Id": workspace_id,
        "X-Correlation-Id": correlation_id,
    }


def _with_key(base_headers: dict[str, str], key: str) -> dict[str, str]:
    return {**base_headers, "Idempotency-Key": key}


def _bootstrap(
    client: httpx.Client,
    api_base_url: str,
    token: str,
    label: str,
) -> tuple[str, str, str, str, str]:
    stage = f"bootstrap {label} tenant"
    actor = f"actor:rc-{label}-{token}"
    correlation_id = f"rc-{label}-{token}"
    organization_response = _request(
        client,
        "POST",
        _url(api_base_url, "/api/v1/organizations"),
        stage=stage,
        expected_status=201,
        headers={"X-Actor-Subject": actor, "X-Correlation-Id": correlation_id},
        json_payload={
            "slug": f"rc-{label}-{token}",
            "name": f"RC Socket {label} {token}",
        },
    )
    organization = _response_object(organization_response, stage)
    organization_id = _text_field(organization, "id", stage)
    organization_headers = {
        "X-Actor-Subject": actor,
        "X-Organization-Id": organization_id,
        "X-Correlation-Id": correlation_id,
    }
    workspace_response = _request(
        client,
        "POST",
        _url(api_base_url, f"/api/v1/organizations/{organization_id}/workspaces"),
        stage=f"{stage} workspace",
        expected_status=201,
        headers=organization_headers,
        json_payload={
            "slug": f"workspace-{label}-{token}",
            "name": f"Production Desk {label} {token}",
        },
    )
    workspace = _response_object(workspace_response, f"{stage} workspace")
    workspace_id = _text_field(workspace, "id", f"{stage} workspace")
    tenant_headers = _headers(actor, organization_id, workspace_id, correlation_id)
    project_response = _request(
        client,
        "POST",
        _url(
            api_base_url,
            f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects",
        ),
        stage=f"{stage} project",
        expected_status=201,
        headers=tenant_headers,
        json_payload={
            "name": f"Socket Smoke Project {label} {token}",
            "description": "Socket-level release-candidate verification",
        },
    )
    project = _response_object(project_response, f"{stage} project")
    project_id = _text_field(project, "id", f"{stage} project")
    return actor, organization_id, workspace_id, project_id, correlation_id


def _run_path(api_base_url: str, organization_id: str, workspace_id: str, project_id: str) -> str:
    return _url(
        api_base_url,
        f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}",
    )


def _run_smoke(api_base_url: str, web_base_url: str) -> None:
    token = uuid4().hex[:12]
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "packages/test-fixtures/brief/valid-structured-brief-v1.json"
    )
    source_bytes = fixture_path.read_bytes()
    source_checksum = hashlib.sha256(source_bytes).hexdigest()

    timeout = httpx.Timeout(30.0, connect=5.0)
    with httpx.Client(follow_redirects=True, timeout=timeout, trust_env=False) as client:
        health_response = _request(
            client,
            "GET",
            _url(api_base_url, "/api/v1/health"),
            stage="API socket health",
            expected_status=200,
        )
        health = _response_object(health_response, "API socket health")
        if health.get("status") != "ok" or health.get("service") != "foundation-api":
            raise SmokeFailure(
                "API socket health: health contract did not report foundation-api ok"
            )
        _request(
            client,
            "GET",
            _url(web_base_url, "/"),
            stage="Web socket health",
            expected_status=200,
        )

        actor, organization_id, workspace_id, project_id, correlation_id = _bootstrap(
            client, api_base_url, token, "primary"
        )
        root = _run_path(api_base_url, organization_id, workspace_id, project_id)
        tenant_headers = _headers(actor, organization_id, workspace_id, correlation_id)

        asset_payload: JsonObject = {
            "display_name": f"rc-brief-{token}.json",
            "original_filename": f"rc-brief-{token}.json",
            "media_type": "application/json",
            "byte_size": len(source_bytes),
            "checksum_algorithm": "sha256",
            "checksum_value": source_checksum,
            "source_type": "api_declared",
        }
        asset_key = f"rc-{token}-asset"
        asset_response = _request(
            client,
            "POST",
            f"{root}/source-assets",
            stage="source asset create",
            expected_status=201,
            headers=_with_key(tenant_headers, asset_key),
            json_payload=asset_payload,
        )
        asset_body = _response_object(asset_response, "source asset create")
        asset = _object_field(asset_body, "source_asset", "source asset create")
        current_version = _object_field(asset_body, "current_version", "source asset create")
        asset_id = _text_field(asset, "id", "source asset create")
        asset_version_id = _text_field(current_version, "id", "source asset create")

        replay_response = _request(
            client,
            "POST",
            f"{root}/source-assets",
            stage="source asset exact replay",
            expected_status=200,
            headers=_with_key(tenant_headers, asset_key),
            json_payload=asset_payload,
        )
        replay_body = _response_object(replay_response, "source asset exact replay")
        if replay_body.get("replayed") is not True:
            raise SmokeFailure("source asset exact replay: response was not marked replayed")

        changed_asset_payload = {**asset_payload, "display_name": f"changed-{token}.json"}
        _request(
            client,
            "POST",
            f"{root}/source-assets",
            stage="source asset changed-digest conflict",
            expected_status=409,
            headers=_with_key(tenant_headers, asset_key),
            json_payload=changed_asset_payload,
        )

        upload_response = _request(
            client,
            "POST",
            f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/uploads",
            stage="source asset upload",
            expected_status=201,
            headers={
                **_with_key(tenant_headers, f"rc-{token}-upload"),
                "Content-Type": "application/octet-stream",
            },
            content=source_bytes,
        )
        _response_object(upload_response, "source asset upload")

        extraction_response = _request(
            client,
            "POST",
            f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/extractions",
            stage="document extraction",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-document-extraction"),
        )
        extraction_body = _response_object(extraction_response, "document extraction")
        extraction = _object_field(extraction_body, "extraction", "document extraction")
        extraction_id = _text_field(extraction, "id", "document extraction")

        brief_run_url = (
            f"{root}/source-assets/{asset_id}/versions/{asset_version_id}/extractions/"
            f"{extraction_id}/brief-extraction-runs"
        )
        brief_run_key = f"rc-{token}-brief-run"
        brief_run_response = _request(
            client,
            "POST",
            brief_run_url,
            stage="brief extraction run",
            expected_status=201,
            headers=_with_key(tenant_headers, brief_run_key),
        )
        brief_run = _response_object(brief_run_response, "brief extraction run")
        brief_run_id = _text_field(brief_run, "run_id", "brief extraction run")
        brief_replay_response = _request(
            client,
            "POST",
            brief_run_url,
            stage="brief extraction idempotent replay",
            expected_status=200,
            headers=_with_key(tenant_headers, brief_run_key),
        )
        brief_replay = _response_object(brief_replay_response, "brief extraction idempotent replay")
        if (
            _text_field(brief_replay, "run_id", "brief extraction idempotent replay")
            != brief_run_id
        ):
            raise SmokeFailure("brief extraction idempotent replay: run identity changed")

        candidate_response = _request(
            client,
            "GET",
            f"{root}/brief-extraction-runs/{brief_run_id}/candidate",
            stage="brief candidate read",
            expected_status=200,
            headers=tenant_headers,
        )
        candidate_body = _response_object(candidate_response, "brief candidate read")
        candidate = _object_field(candidate_body, "candidate", "brief candidate read")
        accepted_response = _request(
            client,
            "POST",
            f"{root}/brief-extraction-runs/{brief_run_id}/accept",
            stage="explicit brief candidate accept",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-accept-brief"),
            json_payload={"accepted_content": candidate, "title": f"RC Brief {token}"},
        )
        accepted = _response_object(accepted_response, "explicit brief candidate accept")
        brief_id = _text_field(accepted, "brief_id", "explicit brief candidate accept")
        brief_version_id = _text_field(
            accepted, "brief_version_id", "explicit brief candidate accept"
        )

        concept_response = _request(
            client,
            "POST",
            f"{root}/briefs/{brief_id}/versions/{brief_version_id}/concept-runs",
            stage="three concept generation",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-concepts"),
            json_payload={},
        )
        concept_body = _response_object(concept_response, "three concept generation")
        candidates = _list_field(concept_body, "candidates", "three concept generation")
        if len(candidates) != 3:
            raise SmokeFailure(
                f"three concept generation: expected 3 candidates, got {len(candidates)}"
            )
        candidate_ids: list[str] = []
        for index, candidate_value in enumerate(candidates):
            if not isinstance(candidate_value, dict):
                raise SmokeFailure(f"three concept generation: candidate {index} was not an object")
            candidate_ids.append(
                _text_field(candidate_value, "id", f"three concept generation candidate {index}")
            )
        if len(set(candidate_ids)) != 3:
            raise SmokeFailure("three concept generation: candidate IDs were not unique")
        concept_run = _object_field(concept_body, "run", "three concept generation")
        concept_run_id = _text_field(concept_run, "id", "three concept generation")
        selected_response = _request(
            client,
            "POST",
            f"{root}/concept-runs/{concept_run_id}/candidates/{candidate_ids[1]}/select",
            stage="explicit concept selection",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-select-concept"),
            json_payload={},
        )
        _response_object(selected_response, "explicit concept selection")

        script_response = _request(
            client,
            "POST",
            f"{root}/concept-runs/{concept_run_id}/scripts",
            stage="script generation after selection",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-script"),
            json_payload={},
        )
        script_body = _response_object(script_response, "script generation after selection")
        script_id = _text_field(
            script_body, "script_version_id", "script generation after selection"
        )

        storyboard_response = _request(
            client,
            "POST",
            f"{root}/scripts/{script_id}/storyboards",
            stage="storyboard generation",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-storyboard"),
            json_payload={"provider_mode": "valid"},
        )
        storyboard_body = _response_object(storyboard_response, "storyboard generation")
        storyboard_version = _object_field(storyboard_body, "version", "storyboard generation")
        storyboard_id = _text_field(storyboard_version, "id", "storyboard generation")

        shot_plan_response = _request(
            client,
            "POST",
            f"{root}/storyboards/{storyboard_id}/shot-plans",
            stage="shot plan generation",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-shot-plan"),
            json_payload={"provider_mode": "valid"},
        )
        shot_plan_body = _response_object(shot_plan_response, "shot plan generation")
        shot_plan_version = _object_field(shot_plan_body, "version", "shot plan generation")
        shot_plan_id = _text_field(shot_plan_version, "id", "shot plan generation")

        approval_response = _request(
            client,
            "POST",
            f"{root}/planning-reviews",
            stage="explicit planning-bundle approval",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-approve-bundle"),
            json_payload={
                "artifact_type": "planning_bundle",
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "outcome": "approved",
                "summary": "Socket RC approval",
                "requested_changes": {},
            },
        )
        approval_body = _response_object(approval_response, "explicit planning-bundle approval")
        approval_review = _object_field(
            approval_body, "review", "explicit planning-bundle approval"
        )
        approval_review_id = _text_field(approval_review, "id", "explicit planning-bundle approval")

        package_response = _request(
            client,
            "POST",
            f"{root}/delivery-packages",
            stage="delivery package creation",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-delivery-package"),
            json_payload={
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "approval_review_id": approval_review_id,
            },
        )
        package_body = _response_object(package_response, "delivery package creation")
        package = _object_field(package_body, "package", "delivery package creation")
        package_id = _text_field(package, "id", "delivery package creation")
        package_manifest = _object_field(package, "manifest", "delivery package creation")
        if package_manifest.get("schema_version") != "delivery-package-v1":
            raise SmokeFailure("delivery package creation: manifest schema version was incorrect")

        export_response = _request(
            client,
            "POST",
            f"{root}/delivery-packages/{package_id}/exports",
            stage="delivery ZIP export",
            expected_status=201,
            headers=_with_key(tenant_headers, f"rc-{token}-delivery-zip"),
            json_payload={"format": "delivery-package.zip"},
        )
        export_body = _response_object(export_response, "delivery ZIP export")
        export = _object_field(export_body, "export", "delivery ZIP export")
        export_id = _text_field(export, "id", "delivery ZIP export")
        export_checksum = _text_field(export, "checksum", "delivery ZIP export")
        export_byte_size = export.get("byte_size")
        if not isinstance(export_byte_size, int) or export_byte_size <= 0:
            raise SmokeFailure("delivery ZIP export: invalid byte_size")

        download_response = _request(
            client,
            "GET",
            f"{root}/delivery-exports/{export_id}",
            stage="delivery ZIP download",
            expected_status=200,
            headers=tenant_headers,
        )
        downloaded = download_response.content
        if len(downloaded) != export_byte_size:
            raise SmokeFailure("delivery ZIP download: byte size did not match export metadata")
        if hashlib.sha256(downloaded).hexdigest() != export_checksum:
            raise SmokeFailure("delivery ZIP download: checksum did not match export metadata")
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
                    raise SmokeFailure("delivery ZIP download: archive contained a corrupt member")
                if set(archive.namelist()) != expected_members:
                    raise SmokeFailure(
                        "delivery ZIP download: ZIP membership was incomplete or unexpected"
                    )
                manifest = json.loads(archive.read("manifest.json"))
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            raise SmokeFailure("delivery ZIP download: invalid ZIP or manifest") from error
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != "delivery-package-v1"
        ):
            raise SmokeFailure("delivery ZIP download: manifest schema version was incorrect")
        lineage = manifest.get("lineage")
        if not isinstance(lineage, dict):
            raise SmokeFailure("delivery ZIP download: manifest lineage was missing")
        for name, expected in {
            "script_version_id": script_id,
            "storyboard_version_id": storyboard_id,
            "shot_plan_version_id": shot_plan_id,
        }.items():
            if lineage.get(name) != expected:
                raise SmokeFailure(f"delivery ZIP download: manifest lineage mismatch for {name}")

        viewer = f"actor:rc-viewer-{token}"
        _request(
            client,
            "POST",
            _url(
                api_base_url,
                f"/api/v1/organizations/{organization_id}/workspaces/{workspace_id}/memberships",
            ),
            stage="viewer membership bootstrap",
            expected_status=201,
            headers=tenant_headers,
            json_payload={"actor_subject": viewer, "role": "viewer"},
        )
        viewer_headers = _headers(viewer, organization_id, workspace_id, f"rc-viewer-{token}")
        _request(
            client,
            "POST",
            f"{root}/delivery-packages",
            stage="viewer mutation denial on replay key",
            expected_status=403,
            headers=_with_key(viewer_headers, f"rc-{token}-delivery-package"),
            json_payload={
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "approval_review_id": approval_review_id,
            },
        )
        _request(
            client,
            "POST",
            f"{root}/delivery-packages",
            stage="viewer mutation denial on fresh key",
            expected_status=403,
            headers=_with_key(viewer_headers, f"rc-{token}-viewer-fresh"),
            json_payload={
                "script_version_id": script_id,
                "storyboard_version_id": storyboard_id,
                "shot_plan_version_id": shot_plan_id,
                "approval_review_id": approval_review_id,
            },
        )

        other_actor, other_organization_id, other_workspace_id, _, other_correlation_id = (
            _bootstrap(client, api_base_url, token, "other")
        )
        cross_tenant_headers = _headers(
            other_actor,
            other_organization_id,
            other_workspace_id,
            other_correlation_id,
        )
        _request(
            client,
            "GET",
            _url(
                api_base_url,
                f"/api/v1/organizations/{other_organization_id}/workspaces/{other_workspace_id}"
                f"/projects/{project_id}/delivery-exports/{export_id}",
            ),
            stage="opaque cross-tenant export denial",
            expected_status=404,
            headers=cross_tenant_headers,
        )


def main() -> int:
    api_base_url = os.environ.get("RC_API_BASE_URL", "http://127.0.0.1:18000")
    web_base_url = os.environ.get("RC_WEB_BASE_URL", "http://127.0.0.1:13000")
    try:
        _run_smoke(api_base_url, web_base_url)
    except SmokeFailure as error:
        print(f"RC socket smoke failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("RC socket smoke interrupted", file=sys.stderr)
        return 130
    print("RC socket smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
