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
    CODEX_TIMEOUT_SECONDS,
    CODEX_TOOL_NAME,
    DEFAULT_PROVIDER_EDGE,
    JSON_INDENT_LEVEL,
    MAXIMUM_CODEX_ARTIFACT_COUNT,
    MAXIMUM_CODEX_OUTPUT_BYTES,
    MAXIMUM_IMAGE_EDGE,
    MAXIMUM_PIXEL_COUNT,
    MAXIMUM_PROVIDER_BYTES,
    MINIMUM_DIMENSION,
    MINIMUM_PIXEL_COUNT,
    OPENAI_API_KEY_NAME,
    OPENAI_API_URL,
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
class ProviderArtifact:
    """Provider bytes, requested dimensions, and observed source dimensions."""

    image_bytes: bytes
    source_size: ImageSize
    provider_requested_size: ImageSize | None
    model_or_tool: str
    credential_source: str


Transport = Callable[[str, bytes, Mapping[str, str]], bytes]
Runner = Callable[[Sequence[str], Path, Mapping[str, str]], None]


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
        raise ImagegenError("size exceeds GPT Image 2 limits")


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
    Raises:
        ImagegenError: If the aspect ratio cannot be represented by provider dimensions.
    """
    if is_native_openai_size(final_size):
        return final_size
    return ImageSize(DEFAULT_PROVIDER_EDGE, DEFAULT_PROVIDER_EDGE)


def decode_image(image_bytes: bytes) -> ImageSize:
    """Decode image bytes with Pillow and return observed dimensions.

    Args:
        image_bytes: Encoded image bytes from a provider or transformation.
    Returns:
        Decoded image dimensions.
    Raises:
        ImagegenError: If bytes are oversized, malformed, or exceed pixel limits.
    """
    if len(image_bytes) > MAXIMUM_PROVIDER_BYTES:
        raise ImagegenError("provider image exceeds the byte limit")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.format != PNG_FORMAT:
                raise ImagegenError("provider image must be PNG")
            if image.width * image.height > MAXIMUM_PIXEL_COUNT:
                raise ImagegenError("provider image exceeds the pixel limit")
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            return ImageSize(*image.size)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ImagegenError("provider returned an invalid image") from error


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


def request_openai_image(prompt: str, requested_size: ImageSize, transport: Transport) -> ProviderArtifact:
    """Request a GPT Image 2 artifact using the environment API key.

    Args:
        prompt: Image-generation prompt.
        requested_size: Native provider dimensions.
        transport: Injected HTTPS transport.
    Returns:
        Provider artifact with observed source dimensions.
    Raises:
        ImagegenError: If credentials, transport, or provider bytes are invalid.
    """
    api_key = os.environ.get(OPENAI_API_KEY_NAME)
    if not api_key:
        raise ImagegenError("OPENAI_API_KEY is required for openai-api")
    request_body = json.dumps({"model": OPENAI_MODEL, "prompt": prompt, "size": requested_size.as_text(), "output_format": OPENAI_OUTPUT_FORMAT}).encode()
    all_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        api_payload = json.loads(transport(OPENAI_API_URL, request_body, all_headers))
        image_records = api_payload.get("data", [])
        image_record = image_records[0] if image_records else {}
        if image_record.get("b64_json"):
            image_bytes = base64.b64decode(image_record["b64_json"], validate=True)
        elif image_record.get("url"):
            with urllib.request.urlopen(image_record["url"], timeout=OPENAI_TIMEOUT_SECONDS) as image_download:
                image_bytes = image_download.read(MAXIMUM_PROVIDER_BYTES + 1)
        else:
            raise ImagegenError("OpenAI returned no image artifact")
    except ImagegenError:
        raise
    except (AttributeError, binascii.Error, IndexError, KeyError, OSError, TypeError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ImagegenError("OpenAI returned an invalid image response") from error
    return ProviderArtifact(image_bytes, decode_image(image_bytes), requested_size, OPENAI_MODEL, OPENAI_API_KEY_NAME)


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


def request_oauth_image(prompt: str, runner: Runner) -> ProviderArtifact:
    """Run Codex in an isolated directory and measure its PNG artifact.

    Args:
        prompt: Image-generation prompt.
        runner: Injected Codex process runner.
    Returns:
        Provider artifact with runtime-observed dimensions.
    Raises:
        ImagegenError: If Codex or its artifact contract fails.
    """
    with tempfile.TemporaryDirectory(prefix=TEMPORARY_DIRECTORY_PREFIX) as temporary_directory:
        work_directory = Path(temporary_directory)
        artifact_path = work_directory / f"generated{PNG_SUFFIX}"
        contract = f"Generate exactly one PNG image for this prompt: {prompt}. Save it at {artifact_path}."
        codex_command = shutil.which("codex") or "codex"
        runner((codex_command, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(work_directory), contract), work_directory, build_oauth_environment())
        image_bytes = discover_oauth_artifact(work_directory, artifact_path)
    return ProviderArtifact(image_bytes, decode_image(image_bytes), None, CODEX_TOOL_NAME, "codex OAuth")


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
    try:
        source_size = decode_image(image_bytes)
        if source_size.width != source_size.height:
            raise ImagegenError("provider image must be square")
        with Image.open(BytesIO(image_bytes)) as source_image:
            source_image.load()
            resized_image = source_image.resize((target_size.width, target_size.height), Image.Resampling.LANCZOS)
            destination = BytesIO()
            resized_image.save(destination, format="PNG")
            return destination.getvalue()
    except ImagegenError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ImagegenError("image resize failed") from error


def build_receipt(prompt: str, backend: str, artifact: ProviderArtifact, requested_size: ImageSize, final_bytes: bytes) -> dict[str, object]:
    """Build receipt fields from observed provider and final bytes.

    Args:
        prompt: Image-generation prompt.
        backend: Selected provider backend.
        artifact: Verified provider artifact.
        requested_size: Requested final dimensions.
        final_bytes: Verified final PNG bytes.
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
    return {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "backend": backend, "model_or_tool": artifact.model_or_tool, "requested_size": requested_size.as_text(), "provider_size": provider_size, "source_size": artifact.source_size.as_text(), "final_size": final_size.as_text(), "transformation": transformation, "transformations": transformations, "source_sha256": source_digest, "final_sha256": final_digest, "credential_source": artifact.credential_source}


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
    if destination_path.suffix.casefold() != PNG_SUFFIX:
        raise ImagegenError("destination must use a .png suffix")
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


def generate_image(prompt: str, backend: str, requested_size: ImageSize, destination_path: Path, resize_policy: str, should_overwrite: bool, transport: Transport | None = None, runner: Runner | None = None) -> dict[str, object]:
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
    Returns:
        Published receipt fields.
    Raises:
        ImagegenError: If provider, validation, transformation, or publication fails.
    """
    validate_final_size(requested_size)
    if destination_path.suffix.casefold() != PNG_SUFFIX:
        raise ImagegenError("destination must use a .png suffix")
    if backend not in ALL_SUPPORTED_BACKENDS or resize_policy not in ALL_SUPPORTED_RESIZE_POLICIES:
        raise ImagegenError("unsupported backend or resize policy")
    provider_size = select_provider_size(requested_size)
    if backend == "openai-api" and provider_size != requested_size and resize_policy == "forbid":
        raise ImagegenError("requested size is not supported natively; use --resize-policy allow")
    artifact = request_openai_image(prompt, provider_size, transport or build_openai_transport()) if backend == "openai-api" else request_oauth_image(prompt, runner or run_codex)
    if artifact.source_size != requested_size and resize_policy == "forbid":
        raise ImagegenError("provider dimensions differ from requested size")
    final_bytes = artifact.image_bytes if artifact.source_size == requested_size else resize_image(artifact.image_bytes, requested_size)
    receipt = build_receipt(prompt, backend, artifact, requested_size, final_bytes)
    publish_artifact(destination_path, final_bytes, receipt, should_overwrite)
    return receipt


def run_codex(all_arguments: Sequence[str], work_directory: Path, all_environment: Mapping[str, str]) -> None:
    """Invoke Codex without exposing credentials in arguments.

    Args:
        all_arguments: Executable and arguments for the Codex process.
        work_directory: Isolated temporary working directory.
        all_environment: Sanitized child environment.
    Raises:
        ImagegenError: If Codex cannot complete within the bounded process contract.
    """
    try:
        completed_process = subprocess.run(all_arguments, cwd=work_directory, env=all_environment, shell=False, check=True, capture_output=True, text=False, timeout=CODEX_TIMEOUT_SECONDS)
        if len(completed_process.stdout) > MAXIMUM_CODEX_OUTPUT_BYTES or len(completed_process.stderr) > MAXIMUM_CODEX_OUTPUT_BYTES:
            raise ImagegenError("Codex output exceeds the limit")
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ImagegenError("Codex image generation failed") from error
