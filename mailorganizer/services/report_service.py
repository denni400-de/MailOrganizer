"""Generates weekly report data: top senders, category stats, importance distribution,
and suggested cleanup actions — per plan section 8.2 (Bericht-Generation).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from mailorganizer.services.storage_service import StorageService

DEFAULT_ARCHIVE_SUGGESTION_DAYS = 90


@dataclass
class ReportData:
    """Aggregated statistics for a reporting period, ready for display or PDF export."""

    period_start: datetime
    period_end: datetime
    total_mails: int
    top_senders: list[tuple[str, int]] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    importance_distribution: dict[int, int] = field(default_factory=dict)
    suggested_actions: list[str] = field(default_factory=list)


class ReportService:
    """Builds a ReportData snapshot from everything currently stored for a user."""

    def __init__(self, storage: StorageService):
        self.storage = storage

    def generate_weekly_report(self, user_id: int, top_n_senders: int = 5) -> ReportData:
        """Aggregate stats over the last 7 days of mail (plus overall cleanup suggestions)."""
        period_end = datetime.now()
        period_start = period_end - timedelta(days=7)

        all_mails = self.storage.list_mails_for_cleanup(user_id)
        recent_mails = [m for m in all_mails if m.received_at >= period_start]

        sender_counts = Counter(m.sender for m in recent_mails)
        top_senders = sender_counts.most_common(top_n_senders)

        category_counts: Counter[str] = Counter()
        importance_distribution: Counter[int] = Counter()
        for mail in recent_mails:
            if mail.analysis:
                if mail.analysis.category:
                    category_counts[mail.analysis.category] += 1
                if mail.analysis.importance_score:
                    importance_distribution[mail.analysis.importance_score] += 1

        suggestions = self._build_suggestions(all_mails)

        return ReportData(
            period_start=period_start,
            period_end=period_end,
            total_mails=len(recent_mails),
            top_senders=top_senders,
            category_counts=dict(category_counts),
            importance_distribution=dict(importance_distribution),
            suggested_actions=suggestions,
        )

    @staticmethod
    def _build_suggestions(all_mails) -> list[str]:
        suggestions: list[str] = []

        cutoff = datetime.now() - timedelta(days=DEFAULT_ARCHIVE_SUGGESTION_DAYS)
        old_count = sum(1 for m in all_mails if not m.is_archived and m.received_at < cutoff)
        if old_count:
            suggestions.append(
                f"{old_count} Mail(s) sind älter als {DEFAULT_ARCHIVE_SUGGESTION_DAYS} Tage und könnten archiviert werden."
            )

        spam_count = sum(1 for m in all_mails if m.is_spam)
        if spam_count:
            suggestions.append(f"{spam_count} Mail(s) sind als Spam markiert und könnten gelöscht werden.")

        seen: set[tuple] = set()
        duplicate_count = 0
        for mail in sorted(all_mails, key=lambda m: m.id):
            key = (mail.sender, mail.subject, mail.received_at)
            if key in seen:
                duplicate_count += 1
            else:
                seen.add(key)
        if duplicate_count:
            suggestions.append(f"{duplicate_count} doppelte Mail(s) gefunden und könnten entfernt werden.")

        unanalyzed = sum(1 for m in all_mails if m.analysis is None)
        if unanalyzed:
            suggestions.append(f"{unanalyzed} Mail(s) wurden noch nicht analysiert.")

        if not suggestions:
            suggestions.append("Keine Aufräum-Vorschläge — alles sieht aufgeräumt aus.")

        return suggestions
