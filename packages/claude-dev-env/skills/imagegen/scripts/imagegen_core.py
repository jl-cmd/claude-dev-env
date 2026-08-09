"""Exact-resolution image generation with secret-safe provider boundaries."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from config.constants import (
    ALL_SUPPORTED_BACKENDS,
    ALL_SUPPORTED_RESIZE_POLICIES,
    CODEX_DEFAULT_REASONING_EFFORT,
    CODEX_REASONING_EFFORT_CONFIG_KEY,
    CODEX_TOOL_NAME,
    DEFAULT_CODEX_TIMEOUT_SECONDS,
    DEFAULT_PROVIDER_EDGE,
    JSON_INDENT_LEVEL,
    MAXIMUM_CODEX_ARTIFACT_COUNT,
    MAXIMUM_CODEX_OUTPUT_BYTES,
    MAXIMUM_IMAGE_EDGE,
    MAXIMUM_PIXEL_COUNT,
    MAXIMUM_PROVIDER_BYTES,
    MAXIMUM_REFERENCE_IMAGE_COUNT,
    MINIMUM_DIMENSION,
    MINIMUM_PIXEL_COUNT,
    MULTIPART_BOUNDARY_TOKEN_BYTES,
    MULTIPART_IMAGE_FIELD_NAME,
    MULTIPART_MODEL_FIELD_NAME,
    MULTIPART_PROMPT_FIELD_NAME,
    MULTIPART_SIZE_FIELD_NAME,
    OPENAI_API_KEY_NAME,
    OPENAI_API_URL,
    OPENAI_EDIT_API_URL,
    OPENAI_MODEL,
    OPENAI_OUTPUT_FORMAT,
    OPENAI_TIMEOUT_SECONDS,
    PNG_FORMAT,
    PNG_SUFFIX,
    RECEIPT_SUFFIX,
    SIZE_COMPONENT_COUNT,
    SIZE_MULTIPLE,
    SIZE_SEPARATOR,
    TEMPORARY_DIRECTORY_PREFIX,
    TEMPORARY_FILE_TOKEN_BYTES,
)


class ImagegenError(RuntimeError):
    """Raised when generation cannot produce a truthful receipt."""


@dataclass(frozen=True)
class ImageSize:
    """A validated square image size."""

    width: int
    height: int

    def as_text(self) -> str:
        return f"{self.width}{SIZE_SEPARATOR}{self.height}"


@dataclass(frozen=True)
class ReferenceImage:
    """One entry from ``--reference-image``, validated and read into bytes."""

    source_path: Path
    image_bytes: bytes
    image_format: str


@dataclass(frozen=True)
class ProviderArtifact:
    """Provider bytes, requested dimensions, and observed source dimensions."""

    image_bytes: bytes
    source_size: ImageSize
    provider_requested_size: ImageSize | None
    model_or_tool: str
    credential_source: str


Transport = Callable[[str, bytes, Mapping[str, str]], bytes]
Runner = Callable[[Sequence[str], Path, Mapping[str, str], int], None]


def parse_size(size_text: str) -> ImageSize:
    """Parse a square final artifact size within the output safety limits.

    Args:
        size_text: Width and height separated by ``x``.
    Returns:
        The parsed final artifact size.
    Raises:
        ImagegenError: If the size is malformed or exceeds the safety limits.
    """
    pieces = size_text.lower().split(SIZE_SEPARATOR)
    if len(pieces) != SIZE_COMPONENT_COUNT or not all(piece.isdigit() for piece in pieces):
        raise ImagegenError("size must use WIDTHxHEIGHT notation")
    image_size = ImageSize(int(pieces[0]), int(pieces[1]))
    validate_final_size(image_size)
    return image_size


def validate_final_size(image_size: ImageSize) -> None:
    """Validate square final dimensions for both CLI and library callers.

    Args:
        image_size: Candidate final dimensions.
    Raises:
        ImagegenError: If dimensions are non-square or exceed output limits.
    """
    if (
        image_size.width < MINIMUM_DIMENSION
        or image_size.height < MINIMUM_DIMENSION
        or image_size.width != image_size.height
        or image_size.width > MAXIMUM_IMAGE_EDGE
        or image_size.width * image_size.height > MAXIMUM_PIXEL_COUNT
    ):
        raise ImagegenError("size exceeds output limits")


def is_native_openai_size(image_size: ImageSize) -> bool:
    """Return whether GPT Image 2 accepts the requested provider size.

    Args:
        image_size: Candidate provider dimensions.
    Returns:
        True when the dimensions satisfy the GPT Image 2 contract.
    """
    return (
        image_size.width == image_size.height
        and image_size.width % SIZE_MULTIPLE == 0
        and image_size.height % SIZE_MULTIPLE == 0
        and image_size.width <= MAXIMUM_IMAGE_EDGE
        and image_size.width * image_size.height >= MINIMUM_PIXEL_COUNT
        and image_size.width * image_size.height <= MAXIMUM_PIXEL_COUNT
    )


def select_provider_size(final_size: ImageSize) -> ImageSize:
    """Select a valid GPT Image 2 size with the final aspect ratio.

    Args:
        final_size: Requested final artifact dimensions.
    Returns:
        A valid native provider size with the same aspect ratio.
    """
    if is_native_openai_size(final_size):
        return final_size
    return ImageSize(DEFAULT_PROVIDER_EDGE, DEFAULT_PROVIDER_EDGE)


def require_png_within_limits(image: Image.Image) -> None:
    """Require a PNG whose pixel count stays within the safety limit.

    Args:
        image: Open Pillow image.
    Raises:
        ImagegenError: If the format is not PNG or the pixel count is too high.
    """
    if image.format != PNG_FORMAT:
        raise ImagegenError("provider image must be PNG")
    if image.width * image.height > MAXIMUM_PIXEL_COUNT:
        raise ImagegenError("provider image exceeds the pixel limit")


def require_provider_byte_limit(image_bytes: bytes) -> None:
    """Require encoded image bytes stay within the provider byte limit.

    Args:
        image_bytes: Encoded image payload.
    Raises:
        ImagegenError: If the payload is larger than the allowed byte limit.
    """
    if len(image_bytes) > MAXIMUM_PROVIDER_BYTES:
        raise ImagegenError("provider image exceeds the byte limit")


def decode_image(image_bytes: bytes) -> ImageSize:
    """Decode image bytes with Pillow and return observed dimensions.

    Args:
        image_bytes: Encoded image bytes from a provider or transformation.
    Returns:
        Decoded image dimensions.
    Raises:
        ImagegenError: If bytes are oversized, malformed, or exceed pixel limits.
    """
    require_provider_byte_limit(image_bytes)
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            require_png_within_limits(image)
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            return ImageSize(*image.size)
    except ImagegenError:
        raise
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ImagegenError("provider returned an invalid image") from error


def require_readable_reference_image(source_path: Path) -> ReferenceImage:
    """Require a reference image that exists and decodes with Pillow.

    Args:
        source_path: Candidate reference image path.
    Returns:
        The validated reference image.
    Raises:
        ImagegenError: If the path is missing or the bytes do not decode as an image.
    """
    if not source_path.is_file():
        raise ImagegenError(f"reference_image_not_found: {source_path}")
    image_bytes = source_path.read_bytes()
    require_provider_byte_limit(image_bytes)
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            image_format = (image.format or PNG_FORMAT).lower()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ImagegenError(f"reference_image_undecodable: {source_path}") from error
    return ReferenceImage(source_path, image_bytes, image_format)


def validate_reference_images(all_reference_image_paths: Sequence[Path]) -> list[ReferenceImage]:
    """Validate every reference image before any backend is spawned.

    Args:
        all_reference_image_paths: Candidate reference image paths, in CLI order.
    Returns:
        The validated reference images, in the same order.
    Raises:
        ImagegenError: If the count exceeds the provider limit, or any path is
            missing or undecodable.
    """
    if len(all_reference_image_paths) > MAXIMUM_REFERENCE_IMAGE_COUNT:
        raise ImagegenError(f"too_many_reference_images: at most {MAXIMUM_REFERENCE_IMAGE_COUNT} are supported")
    return [require_readable_reference_image(each_reference_image_path) for each_reference_image_path in all_reference_image_paths]


def build_openai_transport() -> Transport:
    """Build the standard-library HTTPS transport.

    Returns:
        A transport callable for the OpenAI image-generation endpoint.
    """
    def send_request(url: str, body: bytes, all_headers: Mapping[str, str]) -> bytes:
        """Send one authenticated request.

        Args:
            url: HTTPS endpoint.
            body: JSON request bytes.
            all_headers: Request headers, including authentication.
        Returns:
            Raw endpoint bytes.
        Raises:
            ImagegenError: If the HTTPS request fails.
        """
        request = urllib.request.Request(url, data=body, headers=dict(all_headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=OPENAI_TIMEOUT_SECONDS) as http_reply:
                return http_reply.read()
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise ImagegenError("OpenAI image request failed") from error

    return send_request


def extract_openai_image_bytes(all_api_payload: Mapping[str, Sequence[Mapping[str, str]]]) -> bytes:
    """Extract the first image artifact from an OpenAI images response.

    Args:
        all_api_payload: Decoded JSON response body.
    Returns:
        Raw image bytes, downloaded when the payload carries a URL.
    Raises:
        ImagegenError: If the payload carries no usable image artifact.
    """
    image_records = all_api_payload.get("data", [])
    image_record = image_records[0] if image_records else {}
    if image_record.get("b64_json"):
        return base64.b64decode(image_record["b64_json"], validate=True)
    if image_record.get("url"):
        return download_https_image(image_record["url"])
    raise ImagegenError("OpenAI returned no image artifact")


def request_openai_image(prompt: str, requested_size: ImageSize, transport: Transport, model: str = OPENAI_MODEL) -> ProviderArtifact:
    """Request a GPT Image 2 artifact using the environment API key.

    Args:
        prompt: Image-generation prompt.
        requested_size: Native provider dimensions.
        transport: Injected HTTPS transport.
        model: Requested model name.
    Returns:
        Provider artifact with observed source dimensions.
    Raises:
        ImagegenError: If credentials, transport, or provider bytes are invalid.
    """
    api_key = os.environ.get(OPENAI_API_KEY_NAME)
    if not api_key:
        raise ImagegenError("OPENAI_API_KEY is required for openai-api")
    request_body = json.dumps({"model": model, "prompt": prompt, "size": requested_size.as_text(), "output_format": OPENAI_OUTPUT_FORMAT}).encode()
    all_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        image_bytes = extract_openai_image_bytes(json.loads(transport(OPENAI_API_URL, request_body, all_headers)))
    except ImagegenError:
        raise
    except (AttributeError, binascii.Error, IndexError, KeyError, OSError, TypeError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ImagegenError("OpenAI returned an invalid image response") from error
    return ProviderArtifact(image_bytes, decode_image(image_bytes), requested_size, model, OPENAI_API_KEY_NAME)


def build_openai_edit_request_body(boundary: str, prompt: str, model: str, requested_size: ImageSize, all_reference_images: Sequence[ReferenceImage]) -> bytes:
    """Build a multipart body for the OpenAI image-edit endpoint.

    Args:
        boundary: Multipart boundary token.
        prompt: Image-generation prompt.
        model: Requested model name.
        requested_size: Native provider dimensions.
        all_reference_images: Validated reference images to attach.
    Returns:
        The encoded multipart request body.
    """
    body_parts: list[bytes] = []
    all_text_fields = ((MULTIPART_MODEL_FIELD_NAME, model), (MULTIPART_PROMPT_FIELD_NAME, prompt), (MULTIPART_SIZE_FIELD_NAME, requested_size.as_text()))
    for each_field_name, each_field_content in all_text_fields:
        body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{each_field_name}"\r\n\r\n{each_field_content}\r\n'.encode())
    for each_reference_image in all_reference_images:
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{MULTIPART_IMAGE_FIELD_NAME}"; filename="{each_reference_image.source_path.name}"\r\n'
            f"Content-Type: image/{each_reference_image.image_format}\r\n\r\n"
        ).encode()
        body_parts.append(header + each_reference_image.image_bytes + b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(body_parts)


def request_openai_image_with_references(prompt: str, requested_size: ImageSize, model: str, all_reference_images: Sequence[ReferenceImage], transport: Transport) -> ProviderArtifact:
    """Request an edited GPT Image 2 artifact grounded in reference images.

    Args:
        prompt: Image-generation prompt.
        requested_size: Native provider dimensions.
        model: Requested model name.
        all_reference_images: Validated reference images to attach.
        transport: Injected HTTPS transport.
    Returns:
        Provider artifact with observed source dimensions.
    Raises:
        ImagegenError: If credentials, transport, or provider bytes are invalid.
    """
    api_key = os.environ.get(OPENAI_API_KEY_NAME)
    if not api_key:
        raise ImagegenError("OPENAI_API_KEY is required for openai-api")
    boundary = secrets.token_hex(MULTIPART_BOUNDARY_TOKEN_BYTES)
    request_body = build_openai_edit_request_body(boundary, prompt, model, requested_size, all_reference_images)
    all_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    try:
        image_bytes = extract_openai_image_bytes(json.loads(transport(OPENAI_EDIT_API_URL, request_body, all_headers)))
    except ImagegenError:
        raise
    except (AttributeError, binascii.Error, IndexError, KeyError, OSError, TypeError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ImagegenError("OpenAI returned an invalid image response") from error
    return ProviderArtifact(image_bytes, decode_image(image_bytes), requested_size, model, OPENAI_API_KEY_NAME)


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse HTTP redirects so an HTTPS URL cannot land on a weaker scheme."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: object,
        status_code: int,
        message: str,
        all_headers: Mapping[str, str],
        new_url: str,
    ) -> None:
        del request, file_pointer, status_code, message, all_headers, new_url
        raise ImagegenError("OpenAI image URL redirects are not allowed")


def download_https_image(image_url: str) -> bytes:
    """Download provider image bytes from an HTTPS URL only.

    Args:
        image_url: Provider-returned image location.
    Returns:
        Raw image bytes capped by the provider byte limit.
    Raises:
        ImagegenError: If the URL is not HTTPS, redirects, download fails, or bytes exceed the limit.
    """
    if not image_url.casefold().startswith("https://"):
        raise ImagegenError("OpenAI image URL must use HTTPS")
    request = urllib.request.Request(image_url, method="GET")
    opener = urllib.request.build_opener(_RejectRedirectHandler)
    try:
        with opener.open(request, timeout=OPENAI_TIMEOUT_SECONDS) as image_download:
            if not image_download.geturl().casefold().startswith("https://"):
                raise ImagegenError("OpenAI image URL must use HTTPS")
            image_bytes = image_download.read(MAXIMUM_PROVIDER_BYTES + 1)
    except ImagegenError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError) as error:
        raise ImagegenError("OpenAI image download failed") from error
    require_provider_byte_limit(image_bytes)
    return image_bytes


def build_oauth_environment() -> dict[str, str]:
    """Copy the child environment while removing the API credential."""
    child_environment = dict(os.environ)
    child_environment.pop(OPENAI_API_KEY_NAME, None)
    return child_environment


def discover_oauth_artifact(work_directory: Path, expected_path: Path) -> bytes:
    """Find exactly one PNG emitted by the Codex image tool.

    Args:
        work_directory: Isolated directory scanned for provider artifacts.
        expected_path: Exact PNG path declared in the Codex prompt.
    Returns:
        The single PNG artifact bytes.
    Raises:
        ImagegenError: If the provider emits zero, multiple, or unreadable PNGs.
    """
    all_images = sorted(work_directory.rglob(f"*{PNG_SUFFIX}"))
    if len(all_images) != MAXIMUM_CODEX_ARTIFACT_COUNT:
        raise ImagegenError("Codex must produce exactly one PNG artifact")
    if all_images[0] != expected_path:
        raise ImagegenError("Codex artifact path does not match the declared path")
    try:
        return all_images[0].read_bytes()
    except OSError as error:
        raise ImagegenError("Codex artifact could not be read") from error


def build_codex_arguments(codex_command: str, work_directory: Path, contract: str, all_reference_images: Sequence[ReferenceImage], model: str | None, reasoning_effort: str | None) -> tuple[str, ...]:
    """Build the Codex CLI argument vector for one image-generation run.

    Args:
        codex_command: Resolved Codex executable path or name.
        work_directory: Isolated Codex working directory.
        contract: The generation instruction passed as the trailing prompt.
        all_reference_images: Validated reference images to attach with ``-i``.
        model: Requested Codex model name, or ``None`` to use the Codex default.
        reasoning_effort: Requested Codex reasoning effort, or ``None`` to use the Codex default.
    Returns:
        The full argument vector, contract last.
    """
    all_arguments = [codex_command, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(work_directory)]
    if all_reference_images:
        all_arguments.append("-i")
        all_arguments.extend(str(each_reference_image.source_path) for each_reference_image in all_reference_images)
    if model:
        all_arguments.extend(("-m", model))
    if reasoning_effort:
        all_arguments.extend(("-c", f"{CODEX_REASONING_EFFORT_CONFIG_KEY}={reasoning_effort}"))
    all_arguments.append(contract)
    return tuple(all_arguments)


def request_oauth_image(
    prompt: str,
    runner: Runner,
    requested_size: ImageSize,
    all_reference_images: Sequence[ReferenceImage] = (),
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS,
) -> ProviderArtifact:
    """Run Codex in an isolated directory and measure its PNG artifact.

    Args:
        prompt: Image-generation prompt.
        runner: Injected Codex process runner.
        requested_size: Exact dimensions stated in the Codex contract.
        all_reference_images: Validated reference images attached with ``-i``.
        model: Requested Codex model name, passed through with ``-m``.
        reasoning_effort: Requested Codex reasoning effort, or ``None`` to omit
            the override. ``generate_image`` resolves an absent value to
            ``CODEX_DEFAULT_REASONING_EFFORT`` before calling this function.
        timeout_seconds: Bound passed through to the runner's process timeout.
    Returns:
        Provider artifact with runtime-observed dimensions.
    Raises:
        ImagegenError: If Codex or its artifact contract fails.
    """
    with tempfile.TemporaryDirectory(prefix=TEMPORARY_DIRECTORY_PREFIX) as temporary_directory:
        work_directory = Path(temporary_directory)
        artifact_path = work_directory / f"generated{PNG_SUFFIX}"
        size_clause = f" The image must be exactly {requested_size.as_text()} pixels — generate at exactly that size."
        reference_clause = " Use the attached reference image(s) as visual guidance." if all_reference_images else ""
        contract = f"Generate exactly one PNG image for this prompt: {prompt}.{size_clause}{reference_clause} Save it at {artifact_path}."
        codex_command = shutil.which("codex") or "codex"
        all_arguments = build_codex_arguments(codex_command, work_directory, contract, all_reference_images, model, reasoning_effort)
        runner(all_arguments, work_directory, build_oauth_environment(), timeout_seconds)
        image_bytes = discover_oauth_artifact(work_directory, artifact_path)
    return ProviderArtifact(image_bytes, decode_image(image_bytes), requested_size, CODEX_TOOL_NAME, "codex OAuth")


def resize_image(image_bytes: bytes, target_size: ImageSize) -> bytes:
    """Resize decoded image bytes to the requested dimensions as PNG.

    Args:
        image_bytes: Valid source image bytes.
        target_size: Final dimensions with the same aspect ratio.
    Returns:
        Resampled PNG bytes.
    Raises:
        ImagegenError: If the source is invalid or has a mismatched aspect ratio.
    """
    require_provider_byte_limit(image_bytes)
    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            require_png_within_limits(source_image)
            source_image.load()
            if source_image.width != source_image.height:
                raise ImagegenError("provider image must be square")
            resized_image = source_image.resize((target_size.width, target_size.height), Image.Resampling.LANCZOS)
            destination = BytesIO()
            resized_image.save(destination, format=PNG_FORMAT)
            return destination.getvalue()
    except ImagegenError:
        raise
    except (OSError, TypeError, ValueError, Image.DecompressionBombError) as error:
        raise ImagegenError("image resize failed") from error


def build_receipt(prompt: str, backend: str, artifact: ProviderArtifact, requested_size: ImageSize, final_bytes: bytes, all_reference_images: Sequence[ReferenceImage], model: str | None, reasoning_effort: str | None) -> dict[str, object]:
    """Build receipt fields from observed provider and final bytes.

    Args:
        prompt: Image-generation prompt.
        backend: Selected provider backend.
        artifact: Verified provider artifact.
        requested_size: Requested final dimensions.
        final_bytes: Verified final PNG bytes.
        all_reference_images: Validated reference images attached to the request.
        model: Requested model name, or ``None`` when not supplied.
        reasoning_effort: Requested reasoning effort, or ``None`` when not supplied.
    Returns:
        JSON-compatible receipt fields.
    Raises:
        ImagegenError: If final bytes do not match the requested dimensions.
    """
    final_size = decode_image(final_bytes)
    if final_size != requested_size:
        raise ImagegenError("final image dimensions do not match requested size")
    transformation = "native" if artifact.source_size == requested_size else "resized"
    transformations = [] if transformation == "native" else ["resize:lanczos"]
    provider_size = artifact.provider_requested_size.as_text() if artifact.provider_requested_size else None
    source_digest = hashlib.sha256(artifact.image_bytes).hexdigest()
    final_digest = source_digest if transformation == "native" else hashlib.sha256(final_bytes).hexdigest()
    reference_image_paths = [str(each_reference_image.source_path) for each_reference_image in all_reference_images]
    reference_image_sha256 = [hashlib.sha256(each_reference_image.image_bytes).hexdigest() for each_reference_image in all_reference_images]
    return {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "backend": backend, "model_or_tool": artifact.model_or_tool, "requested_size": requested_size.as_text(), "provider_size": provider_size, "source_size": artifact.source_size.as_text(), "final_size": final_size.as_text(), "transformation": transformation, "transformations": transformations, "source_sha256": source_digest, "final_sha256": final_digest, "credential_source": artifact.credential_source, "reference_image_paths": reference_image_paths, "reference_image_sha256": reference_image_sha256, "model": model, "reasoning_effort": reasoning_effort}


def require_png_destination(destination_path: Path) -> None:
    """Require a destination path that ends with ``.png``.

    Args:
        destination_path: Candidate final image path.
    Raises:
        ImagegenError: If the path does not use a ``.png`` suffix.
    """
    if destination_path.suffix.casefold() != PNG_SUFFIX:
        raise ImagegenError("destination must use a .png suffix")


def publish_artifact(destination_path: Path, image_bytes: bytes, all_receipt: dict[str, object], should_overwrite: bool) -> None:
    """Publish image and receipt atomically after overwrite checks.

    Args:
        destination_path: Final PNG path.
        image_bytes: Verified final PNG bytes.
        all_receipt: Receipt fields describing the published bytes.
        should_overwrite: Whether existing destinations may be replaced.
    Raises:
        ImagegenError: If publication cannot proceed safely.
    """
    require_png_destination(destination_path)
    receipt_path = destination_path.with_suffix(RECEIPT_SUFFIX)
    if receipt_path == destination_path:
        raise ImagegenError("destination and receipt paths must differ")
    if not should_overwrite and (destination_path.exists() or receipt_path.exists()):
        raise ImagegenError("output or receipt already exists; use --overwrite")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    previous_image = destination_path.read_bytes() if destination_path.exists() else None
    previous_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    temporary_paths: list[Path] = []
    was_image_replaced = False
    was_receipt_replaced = False
    try:
        for each_destination, each_content in ((destination_path, image_bytes), (receipt_path, json.dumps(all_receipt, indent=JSON_INDENT_LEVEL).encode())):
            temporary_path = each_destination.with_name(f".{each_destination.name}.{secrets.token_hex(TEMPORARY_FILE_TOKEN_BYTES)}.tmp")
            temporary_paths.append(temporary_path)
            temporary_path.write_bytes(each_content)
        os.replace(temporary_paths[0], destination_path)
        was_image_replaced = True
        os.replace(temporary_paths[1], receipt_path)
        was_receipt_replaced = True
    except (OSError, TypeError, ValueError) as error:
        if was_receipt_replaced:
            _restore_path(receipt_path, previous_receipt)
        if was_image_replaced:
            _restore_path(destination_path, previous_image)
        raise ImagegenError("artifact publication failed") from error
    finally:
        for each_temporary_path in temporary_paths:
            try:
                each_temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _restore_path(path: Path, previous_bytes: bytes | None) -> None:
    """Restore one path during publication rollback."""
    try:
        if previous_bytes is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous_bytes)
    except OSError:
        pass


def generate_image(
    prompt: str,
    backend: str,
    requested_size: ImageSize,
    destination_path: Path,
    resize_policy: str,
    should_overwrite: bool,
    transport: Transport | None = None,
    runner: Runner | None = None,
    all_reference_images: Sequence[Path] = (),
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Generate, verify, optionally resize, and publish one image.

    Args:
        prompt: Image-generation prompt.
        backend: ``openai-api`` or ``codex-oauth``.
        requested_size: Final artifact dimensions.
        destination_path: Final PNG path.
        resize_policy: ``forbid`` or ``allow``.
        should_overwrite: Whether existing destinations may be replaced.
        transport: Optional injected OpenAI transport.
        runner: Optional injected Codex runner.
        all_reference_images: Reference image paths, validated before any backend spawn.
        model: Requested model name, passed through to the selected backend.
        reasoning_effort: Requested reasoning effort, passed through to ``codex-oauth``
            only. ``codex-oauth`` defaults an absent value to ``CODEX_DEFAULT_REASONING_EFFORT``.
        timeout_seconds: Process timeout bound passed to ``codex-oauth`` only.
            ``openai-api`` keeps its own separate ``OPENAI_TIMEOUT_SECONDS`` bound.
    Returns:
        Published receipt fields.
    Raises:
        ImagegenError: If provider, validation, transformation, or publication fails.
    """
    validate_final_size(requested_size)
    require_png_destination(destination_path)
    if backend not in ALL_SUPPORTED_BACKENDS or resize_policy not in ALL_SUPPORTED_RESIZE_POLICIES:
        raise ImagegenError("unsupported backend or resize policy")
    all_verified_reference_images = validate_reference_images(all_reference_images)
    if backend == "openai-api":
        if reasoning_effort:
            raise ImagegenError("reasoning_effort_unsupported_by_backend: openai-api has no reasoning-effort control")
        provider_size = select_provider_size(requested_size)
        if provider_size != requested_size and resize_policy == "forbid":
            raise ImagegenError("requested size is not supported natively; use --resize-policy allow")
        request_model = model or OPENAI_MODEL
        active_transport = transport or build_openai_transport()
        if all_verified_reference_images:
            artifact = request_openai_image_with_references(prompt, provider_size, request_model, all_verified_reference_images, active_transport)
        else:
            artifact = request_openai_image(prompt, provider_size, active_transport, request_model)
    else:
        reasoning_effort = reasoning_effort or CODEX_DEFAULT_REASONING_EFFORT
        artifact = request_oauth_image(
            prompt,
            runner or run_codex,
            requested_size,
            all_reference_images=all_verified_reference_images,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        )
    if artifact.source_size != requested_size and resize_policy == "forbid":
        raise ImagegenError("provider dimensions differ from requested size")
    final_bytes = artifact.image_bytes if artifact.source_size == requested_size else resize_image(artifact.image_bytes, requested_size)
    receipt = build_receipt(prompt, backend, artifact, requested_size, final_bytes, all_verified_reference_images, model, reasoning_effort)
    publish_artifact(destination_path, final_bytes, receipt, should_overwrite)
    return receipt


def run_codex(all_arguments: Sequence[str], work_directory: Path, all_environment: Mapping[str, str], timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS) -> None:
    """Invoke Codex without exposing credentials in arguments.

    Args:
        all_arguments: Executable and arguments for the Codex process.
        work_directory: Isolated temporary working directory.
        all_environment: Sanitized child environment.
        timeout_seconds: Bound passed to the Codex subprocess timeout.
    Raises:
        ImagegenError: If Codex times out, exits non-zero, or cannot run at all.
    """
    try:
        completed_process = subprocess.run(all_arguments, cwd=work_directory, env=all_environment, shell=False, check=True, capture_output=True, text=False, timeout=timeout_seconds)
        if len(completed_process.stdout) > MAXIMUM_CODEX_OUTPUT_BYTES or len(completed_process.stderr) > MAXIMUM_CODEX_OUTPUT_BYTES:
            raise ImagegenError("Codex output exceeds the limit")
    except subprocess.TimeoutExpired as error:
        raise ImagegenError(f"codex_timed_out: exceeded the {timeout_seconds}s cap") from error
    except subprocess.CalledProcessError as error:
        raise ImagegenError("codex_exited_nonzero: Codex image generation failed") from error
    except OSError as error:
        raise ImagegenError("codex_spawn_failed: Codex could not be run") from error
