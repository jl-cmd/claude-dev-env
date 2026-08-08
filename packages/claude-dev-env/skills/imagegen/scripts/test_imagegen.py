"""Focused tests for exact-resolution image generation."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

import imagegen_core
from imagegen_core import (
    ImagegenError,
    ImageSize,
    build_oauth_environment,
    decode_image,
    download_https_image,
    generate_image,
    parse_size,
    publish_artifact,
    resize_image,
)


def make_png(image_size: tuple[int, int]) -> bytes:
    """Create real PNG bytes for provider-boundary tests."""
    destination = BytesIO()
    Image.new("RGB", image_size, "purple").save(destination, format="PNG")
    return destination.getvalue()


def test_native_output_preserves_source_bytes_and_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_bytes = make_png((2880, 2880))
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    provider_payload = b'{"data":[{"b64_json":"' + base64.b64encode(source_bytes) + b'"}]}'
    receipt = generate_image("native", "openai-api", ImageSize(2880, 2880), tmp_path / "native.png", "forbid", False, transport=lambda _url, _body, _headers: provider_payload)
    assert (tmp_path / "native.png").read_bytes() == source_bytes
    assert receipt["transformation"] == "native"
    assert receipt["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()


def test_oauth_output_resizes_and_strips_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    captured_environment: dict[str, str] = {}

    def runner(_arguments: Sequence[str], work_directory: Path, environment: Mapping[str, str]) -> None:
        captured_environment.update(environment)
        (work_directory / "generated.png").write_bytes(make_png((1254, 1254)))

    receipt = generate_image("resize", "codex-oauth", ImageSize(2880, 2880), tmp_path / "resized.png", "allow", False, runner=runner)
    assert decode_image((tmp_path / "resized.png").read_bytes()) == ImageSize(2880, 2880)
    assert receipt["transformation"] == "resized"
    assert "OPENAI_API_KEY" not in captured_environment


@pytest.mark.parametrize("invalid_size", ("2880", "2880x1440", "2881x2881", "3841x3841", "3840x3840"))
def test_invalid_sizes_fail(invalid_size: str) -> None:
    with pytest.raises(ImagegenError):
        parse_size(invalid_size)


@pytest.mark.parametrize("valid_size", ("256x256", "512x512", "1028x1028", "2880x2880"))
def test_final_sizes_are_independent_from_native_api_sizes(valid_size: str) -> None:
    assert parse_size(valid_size).as_text() == valid_size


def test_openai_unsupported_size_fails_before_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ImagegenError, match="resize-policy"):
        generate_image("prompt", "openai-api", ImageSize(1028, 1028), tmp_path / "artifact.png", "forbid", False)


def test_openai_native_size_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ImagegenError, match="OPENAI_API_KEY"):
        generate_image("prompt", "openai-api", ImageSize(2880, 2880), tmp_path / "artifact.png", "forbid", False)


def test_openai_unsupported_size_requests_valid_provider_size_before_resize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    request_sizes: list[str] = []
    request_formats: list[str] = []
    source_bytes = make_png((2048, 2048))
    provider_payload = b'{"data":[{"b64_json":"' + base64.b64encode(source_bytes) + b'"}]}'

    def transport(_url: str, body: bytes, _headers: Mapping[str, str]) -> bytes:
        request_payload = json.loads(body)
        request_sizes.append(request_payload["size"])
        request_formats.append(request_payload["output_format"])
        return provider_payload

    receipt = generate_image("prompt", "openai-api", ImageSize(1028, 1028), tmp_path / "artifact.png", "allow", False, transport=transport)

    assert request_sizes == ["2048x2048"]
    assert request_formats == ["png"]
    assert receipt["source_size"] == "2048x2048"
    assert receipt["final_size"] == "1028x1028"
    assert receipt["transformation"] == "resized"


def test_oauth_environment_strips_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    assert "OPENAI_API_KEY" not in build_oauth_environment()


def test_library_validates_square_size_and_png_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ImagegenError, match="size exceeds"):
        generate_image("prompt", "openai-api", ImageSize(1028, 1024), tmp_path / "artifact.png", "forbid", False)
    with pytest.raises(ImagegenError, match=".png"):
        generate_image("prompt", "openai-api", ImageSize(2880, 2880), tmp_path / "artifact.jpg", "forbid", False)


def test_http_provider_image_url_is_rejected() -> None:
    with pytest.raises(ImagegenError, match="HTTPS"):
        download_https_image("http://example.invalid/image.png")


def test_non_png_provider_bytes_are_rejected() -> None:
    destination = BytesIO()
    Image.new("RGB", (16, 16), "purple").save(destination, format="JPEG")

    with pytest.raises(ImagegenError, match="PNG"):
        decode_image(destination.getvalue())


@pytest.mark.parametrize("artifact_names", ((), ("one.png", "two.png")))
def test_missing_or_multiple_artifacts_fail(tmp_path: Path, artifact_names: tuple[str, ...]) -> None:
    def runner(_arguments: Sequence[str], work_directory: Path, _environment: Mapping[str, str]) -> None:
        for each_artifact_name in artifact_names:
            (work_directory / each_artifact_name).write_bytes(make_png((1254, 1254)))

    with pytest.raises(ImagegenError, match="exactly one"):
        generate_image("prompt", "codex-oauth", ImageSize(2880, 2880), tmp_path / "artifact.png", "allow", False, runner=runner)


def test_mismatched_aspect_ratio_is_rejected(tmp_path: Path) -> None:
    def runner(_arguments: Sequence[str], work_directory: Path, _environment: Mapping[str, str]) -> None:
        (work_directory / "generated.png").write_bytes(make_png((1254, 1000)))

    with pytest.raises(ImagegenError, match="square"):
        generate_image("prompt", "codex-oauth", ImageSize(2880, 2880), tmp_path / "artifact.png", "allow", False, runner=runner)


def test_transparency_survives_native_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = BytesIO()
    Image.new("RGBA", (16, 16), (10, 20, 30, 0)).save(destination, format="PNG")
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    provider_payload = b'{"data":[{"b64_json":"' + base64.b64encode(destination.getvalue()) + b'"}]}'
    generate_image("transparent", "openai-api", ImageSize(16, 16), tmp_path / "transparent.png", "allow", False, transport=lambda _url, _body, _headers: provider_payload)
    with Image.open(tmp_path / "transparent.png") as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (10, 20, 30, 0)


def test_overwrite_refusal_and_cleanup(tmp_path: Path) -> None:
    output_path = tmp_path / "existing.png"
    output_path.write_bytes(make_png((16, 16)))
    with pytest.raises(ImagegenError, match="already exists"):
        publish_artifact(output_path, output_path.read_bytes(), {"transformation": "native"}, False)
    assert not list(tmp_path.glob("*.tmp"))


def test_publication_rolls_back_when_receipt_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination_path = tmp_path / "artifact.png"
    original_replace = imagegen_core.os.replace
    replacement_count = 0

    def replace_with_failure(source: Path, target: Path) -> None:
        nonlocal replacement_count
        replacement_count += 1
        if replacement_count == 2:
            raise OSError("receipt replacement failed")
        original_replace(source, target)

    monkeypatch.setattr(imagegen_core.os, "replace", replace_with_failure)
    with pytest.raises(ImagegenError, match="publication failed"):
        publish_artifact(destination_path, make_png((16, 16)), {"transformation": "native"}, False)
    assert not destination_path.exists()
    assert not destination_path.with_suffix(".json").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_resize_and_decode_have_expected_hashes() -> None:
    source_bytes = make_png((1254, 1254))
    final_bytes = resize_image(source_bytes, ImageSize(2880, 2880))
    assert decode_image(final_bytes) == ImageSize(2880, 2880)
    assert hashlib.sha256(source_bytes).hexdigest() != hashlib.sha256(final_bytes).hexdigest()
