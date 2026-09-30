"""Public GitHub repository acquisition handler."""

import shutil
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from backend.platform.config import get_settings
from backend.platform.errors import (
    GitHubAcquisitionError,
    GitHubNetworkError,
    GitHubRateLimitExceededError,
    GitHubRepositoryNotFoundError,
    GitHubTimeoutError,
    SourceValidationError,
)
from backend.platform.ingestion.application.acquisition import (
    AcquisitionHandler,
    AcquisitionResult,
)
from backend.platform.ingestion.domain.constants import (
    MAX_REPOSITORY_SIZE_BYTES,
    SourceType,
)
from backend.platform.ingestion.domain.source import (
    parse_github_url,
    validate_github_ref,
)
from backend.platform.ingestion.infra.acquisition.archive_extractor import (
    ArchiveExtractor,
)


class GitHubAcquisitionHandler(AcquisitionHandler):
    """Safely acquires a public GitHub repository archive into sandbox."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        timeout_seconds: int | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    def can_handle(self, source_type: str) -> bool:
        return source_type.lower() in ("github", SourceType.GITHUB.value)

    def acquire(
        self,
        source_reference: str,
        revision_identifier: str | None,
        temp_root: Path,
    ) -> AcquisitionResult:
        if "@" in source_reference:
            raw_url, ref_part = source_reference.split("@", 1)
        else:
            raw_url, ref_part = source_reference, None

        normalized_url, owner, repo = parse_github_url(raw_url)
        validated_ref = validate_github_ref(ref_part)

        target_ref = validated_ref if validated_ref else "HEAD"
        encoded_ref = quote(target_ref, safe="")

        codeload_url = (
            f"https://codeload.github.com/{owner}/{repo}/tar.gz/{encoded_ref}"
        )
        temp_root.mkdir(parents=True, exist_ok=True)
        download_path = temp_root / f"github_{owner}_{repo}.tar.gz"
        user_agent = self._user_agent or get_settings().github_acquisition_user_agent
        headers = {"User-Agent": user_agent}

        timeout = (
            self._timeout_seconds
            if self._timeout_seconds is not None
            else get_settings().github_acquisition_timeout_seconds
        )
        client = self._http_client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
        )
        should_close_client = self._http_client is None

        try:
            try:
                with client.stream("GET", codeload_url, headers=headers) as response:
                    # Unify 401, 403, and 404 to avoid leaking private repository
                    # existence
                    if response.status_code in (401, 403, 404):
                        raise GitHubRepositoryNotFoundError(
                            "Repository not found or access denied."
                        )
                    if response.status_code == 429:
                        raise GitHubRateLimitExceededError(
                            "Repository not found or access denied."
                        )
                    if response.status_code >= 400:
                        raise GitHubAcquisitionError(
                            f"GitHub acquisition failed with HTTP status "
                            f"{response.status_code}."
                        )

                    total_downloaded = 0
                    stream_start = time.monotonic()
                    with open(download_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            if (time.monotonic() - stream_start) > timeout:
                                raise GitHubTimeoutError(
                                    "GitHub repository download timed out after "
                                    f"{timeout} seconds."
                                )
                            total_downloaded += len(chunk)
                            if total_downloaded > MAX_REPOSITORY_SIZE_BYTES:
                                raise SourceValidationError(
                                    f"Downloaded repository archive exceeds limit of "
                                    f"{MAX_REPOSITORY_SIZE_BYTES} bytes."
                                )
                            f.write(chunk)
            except httpx.TimeoutException as exc:
                raise GitHubTimeoutError(
                    "GitHub repository download timed out."
                ) from exc
            except httpx.RequestError as exc:
                raise GitHubNetworkError(
                    f"GitHub acquisition network failure: {exc}"
                ) from exc
        finally:
            if should_close_client:
                client.close()

        extracted = ArchiveExtractor.extract(
            archive_path=download_path,
            destination_dir=temp_root / "extracted",
            unwrap_single_root=True,
        )

        resolved_rev = (
            revision_identifier or validated_ref or extracted.source_hash[:12]
        )

        return AcquisitionResult(
            root_path=extracted.root_path,
            revision_identifier=resolved_rev,
            source_hash=extracted.source_hash,
            total_source_bytes=extracted.archive_size,
            cleanup_fn=lambda: shutil.rmtree(temp_root, ignore_errors=True),
        )
