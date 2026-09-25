"""Conditional rules engine: evaluates user-defined AnalysisRule rows against mails
and applies the configured action (archive/delete/flag/category), per plan section 8.1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from mailorganizer.config import constants
from mailorganizer.models.database import AnalysisRule, Mail
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import ValidationError
from mailorganizer.utils.logger import get_logger

logger = get_logger("rules_service")


@dataclass
class RuleCondition:
    """A single field/operator/value clause, optionally paired with a category to set."""

    field: str
    operator: str
    value: object
    set_category: str | None = None

    def to_json(self) -> str:
        data = {"field": self.field, "operator": self.operator, "value": self.value}
        if self.set_category:
            data["set_category"] = self.set_category
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str) -> "RuleCondition":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid rule condition JSON: {exc}") from exc
        if data.get("field") not in constants.RULE_FIELDS:
            raise ValidationError(f"Unknown rule field: {data.get('field')!r}")
        if data.get("operator") not in constants.RULE_OPERATORS:
            raise ValidationError(f"Unknown rule operator: {data.get('operator')!r}")
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data.get("value"),
            set_category=data.get("set_category"),
        )


def _mail_field_value(mail: Mail, field: str) -> object:
    if field == "sender":
        return mail.sender or ""
    if field == "subject":
        return mail.subject or ""
    if field == "category":
        return mail.analysis.category if mail.analysis else ""
    if field == "importance_score":
        return mail.analysis.importance_score if mail.analysis else None
    if field == "sentiment":
        return mail.analysis.sentiment if mail.analysis else ""
    if field == "keywords":
        if mail.analysis and mail.analysis.keywords:
            return json.loads(mail.analysis.keywords)
        return []
    raise ValidationError(f"Unknown rule field: {field!r}")


def evaluate_condition(condition: RuleCondition, mail: Mail) -> bool:
    """Return True if the mail (and its analysis, if any) matches the condition."""
    actual = _mail_field_value(mail, condition.field)
    if actual is None:
        return False

    op = condition.operator
    expected = condition.value

    if op == "contains":
        if isinstance(actual, list):
            return str(expected).lower() in [str(v).lower() for v in actual]
        return str(expected).lower() in str(actual).lower()
    if op == "equals":
        return str(actual).lower() == str(expected).lower()
    if op in ("gt", "lt", "gte", "lte"):
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False
        if op == "gt":
            return actual_num > expected_num
        if op == "lt":
            return actual_num < expected_num
        if op == "gte":
            return actual_num >= expected_num
        return actual_num <= expected_num
    raise ValidationError(f"Unknown rule operator: {op!r}")


class RulesEngine:
    """Applies a user's active analysis rules (in priority order) to their stored mails."""

    def __init__(self, storage: StorageService):
        self.storage = storage

    def apply_rule(self, rule: AnalysisRule, mail: Mail) -> bool:
        """Evaluate and, on match, apply `rule` to `mail`. Returns True if the rule matched."""
        try:
            condition = RuleCondition.from_json(rule.condition)
        except ValidationError as exc:
            logger.error("Rule %s has invalid condition: %s", rule.id, exc)
            return False

        if not evaluate_condition(condition, mail):
            return False

        self._apply_action(rule, condition, mail)
        return True

    def _apply_action(self, rule: AnalysisRule, condition: RuleCondition, mail: Mail) -> None:
        if rule.action == "archive":
            self.storage.set_mail_flags(mail.id, is_archived=True)
        elif rule.action == "delete":
            self.storage.set_mail_flags(mail.id, is_spam=True)
        elif rule.action == "flag":
            self.storage.set_mail_flags(mail.id, is_important=True)
        elif rule.action == "category" and condition.set_category:
            from mailorganizer.models.analysis import AnalysisResult

            existing = mail.analysis
            result = AnalysisResult(
                category=condition.set_category,
                importance_score=existing.importance_score if existing else 1,
                sentiment=existing.sentiment if existing else "neutral",
                summary=existing.summary if existing else "",
                recommended_action=existing.recommended_action if existing else "read_later",
                keywords=json.loads(existing.keywords) if existing and existing.keywords else [],
                ollama_model=existing.ollama_model if existing else "rule-engine",
            )
            self.storage.save_analysis(mail.id, result)
        else:
            logger.warning("Rule %s has unsupported action %r", rule.id, rule.action)

        logger.info("Rule %r matched mail %s -> action=%s", rule.name, mail.id, rule.action)

    def run_for_user(self, user_id: int) -> int:
        """Apply all active rules (priority order, first match wins per mail) to unarchived mails.

        Returns the number of mails affected by at least one rule.
        """
        rules = self.storage.list_rules(user_id, active_only=True)
        if not rules:
            return 0

        mails = self.storage.list_mails_for_cleanup(user_id)
        affected = 0
        for mail in mails:
            for rule in rules:
                if self.apply_rule(rule, mail):
                    affected += 1
                    break
        return affected
