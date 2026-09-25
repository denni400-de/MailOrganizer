"""Batch mail-cleanup operations, per Workflow 3 (Mail-Cleanup) in the implementation plan."""

from __future__ import annotations

from dataclasses import dataclass

from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.logger import get_logger

logger = get_logger("cleanup_service")


@dataclass
class CleanupSummary:
    """Counts of what a cleanup run did, for display in the summary dialog."""

    archived: int = 0
    spam_deleted: int = 0
    duplicates_deleted: int = 0

    @property
    def total_affected(self) -> int:
        return self.archived + self.spam_deleted + self.duplicates_deleted


class CleanupService:
    """Runs the batch cleanup operations offered by the Cleanup dialog."""

    def __init__(self, storage: StorageService):
        self.storage = storage

    def run(
        self,
        user_id: int,
        archive_older_than_days: int | None = None,
        delete_spam: bool = False,
        delete_duplicates: bool = False,
    ) -> CleanupSummary:
        """Execute the requested cleanup steps in a safe order (dedupe first, then spam, then archive)."""
        summary = CleanupSummary()

        if delete_duplicates:
            summary.duplicates_deleted = self.storage.delete_duplicate_mails(user_id)
            logger.info("Cleanup: removed %s duplicate mails", summary.duplicates_deleted)

        if delete_spam:
            summary.spam_deleted = self.storage.delete_spam_mails(user_id)
            logger.info("Cleanup: deleted %s spam mails", summary.spam_deleted)

        if archive_older_than_days is not None:
            summary.archived = self.storage.archive_mails_older_than(user_id, archive_older_than_days)
            logger.info("Cleanup: archived %s mails older than %s days", summary.archived, archive_older_than_days)

        return summary
