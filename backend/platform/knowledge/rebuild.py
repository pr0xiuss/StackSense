"""M2 uses only the independently reviewed public M1 reprojection port."""

from backend.platform.delivery.contracts import VersionScope
from backend.platform.delivery.reprojection import (
    AuthorizedReprojectionPrincipal,
    SearchReprojectionAccepted,
    SearchReprojectionRequest,
    SearchReprojectionService,
)
from backend.platform.knowledge.contracts import SearchNotReadyError
from backend.platform.knowledge.repository import (
    SearchPublicationPort,
    SqlAlchemySearchRepository,
)


class SearchRebuildService:
    def __init__(
        self,
        repository: SqlAlchemySearchRepository,
        orchestration: SearchReprojectionService,
    ) -> None:
        self._repository, self._orchestration = repository, orchestration

    def request(
        self, scope: VersionScope, key: str, principal: AuthorizedReprojectionPrincipal
    ) -> SearchReprojectionAccepted:
        prior = self._orchestration.lookup(scope, key, principal)
        if prior is not None:
            return prior  # Never resolve today's generation on durable replay.
        resource = self._repository.get_resource(
            scope.project_id, scope.architecture_version_id
        )
        if resource is None or resource.active_generation_id is None:
            raise SearchNotReadyError("No accepted search generation to rebuild")
        receipt = self._repository.get_publication_receipt(
            resource.active_generation_id
        )
        if receipt is None:
            raise SearchNotReadyError("Accepted search reference is unavailable")
        import json

        from backend.platform.delivery.contracts import ArtifactReference

        reference = ArtifactReference.model_validate_json(
            json.dumps(receipt.artifact_reference)
        )
        manifest = SearchPublicationPort(self._repository._session).require_accepted(
            reference
        )
        if manifest.attempt is None:
            raise SearchNotReadyError("Accepted attempt is unavailable")
        return self._orchestration.request_search_reprojection(
            scope,
            SearchReprojectionRequest(
                idempotency_key=key,
                expected_predecessor_work_id=manifest.attempt.work.work_id,
                expected_accepted_reference=reference,
                reason="manual_rebuild",
            ),
            principal,
        )
