"""Fixed installed Windows sealer entry; operator runs under sealer identity.

There is no RunAs password, impersonation shortcut, network service or worker
registration. Provisioned cross-identity invocation must be proven on Windows.
"""

import sys
from pathlib import Path

from backend.platform.diagrams.artifact_contracts import SealRequest
from backend.platform.diagrams.artifact_runtime.seal_generation import (
    DatabaseSealerMetadata,
    MetadataConfig,
)
from backend.platform.diagrams.windows_artifacts import WindowsPrincipalSealer
from backend.platform.diagrams.windows_native import NativeWindows

CONFIG = Path(r"C:\ProgramData\StackSense\DiagramSealer\db-sealer.json")


class WindowsMetadataConfig(MetadataConfig):
    sealer_sid: str
    worker_sid: str
    reader_sid: str


def configured_metadata(
    *, cleanup: bool = False
) -> tuple[DatabaseSealerMetadata, WindowsMetadataConfig]:
    native = NativeWindows()
    identity = native.token_sid()
    with native.file(CONFIG.parent, directory=True) as directory:
        native.require_acl(directory, "S-1-5-32-544", identity)
        path = CONFIG.with_name("db-cleanup.json") if cleanup else CONFIG
        with native.file(path) as handle:
            native.require_acl(handle, identity, identity)
            info = native.information(handle)
            size = (info.size_high << 32) | info.size_low
            if size > 8192:
                raise ValueError("diagram_store_unavailable")
            config = WindowsMetadataConfig.from_bytes(
                native.read(handle, size), max_bytes=8192
            )
    if config.sealer_sid != identity:
        raise ValueError("diagram_store_unavailable")
    metadata = DatabaseSealerMetadata.__new__(DatabaseSealerMetadata)
    metadata.initialize(config, cleanup=cleanup)
    return metadata, config


def main() -> None:
    if len(sys.argv) != 1:
        raise ValueError("diagram_input_invalid")
    metadata, config = configured_metadata()
    try:
        request = SealRequest.from_bytes(
            sys.stdin.buffer.read(262145), max_bytes=262144
        )
        result = WindowsPrincipalSealer(
            metadata,
            metadata.limits_for(request),
            sealer_sid=config.sealer_sid,
            worker_sid=config.worker_sid,
            reader_sid=config.reader_sid,
        ).seal(request)
        sys.stdout.buffer.write(result.to_bytes())
    finally:
        metadata.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("diagram_windows_sealing_rejected\n")
        raise SystemExit(78) from None
