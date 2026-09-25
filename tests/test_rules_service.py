from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mailorganizer.models.analysis import AnalysisResult
from mailorganizer.models.mail import MailData
from mailorganizer.services.rules_service import RuleCondition, RulesEngine, evaluate_condition
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import ValidationError


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield StorageService(Path(tmp) / "test.db")


@pytest.fixture
def user_id(storage):
    user = storage.get_or_create_user("a@b.com", "imap.x.com", "smtp.x.com", "encpass")
    return user.id


def make_mail(**overrides) -> MailData:
    defaults = dict(
        message_id="<1@x>",
        sender="promo@amazon.com",
        recipients=["a@b.com"],
        subject="Dein Angebot",
        received_at=datetime.now(),
        body="Kaufe jetzt mit Rabatt",
    )
    defaults.update(overrides)
    return MailData(**defaults)


def test_rule_condition_round_trip():
    condition = RuleCondition(field="sender", operator="contains", value="amazon", set_category="shopping")
    restored = RuleCondition.from_json(condition.to_json())
    assert restored.field == "sender"
    assert restored.operator == "contains"
    assert restored.value == "amazon"
    assert restored.set_category == "shopping"


def test_rule_condition_rejects_unknown_field():
    with pytest.raises(ValidationError):
        RuleCondition.from_json('{"field": "bogus", "operator": "contains", "value": "x"}')


def test_evaluate_condition_contains_on_sender(storage, user_id):
    mail_row = storage.save_mail(user_id, make_mail())
    condition = RuleCondition(field="sender", operator="contains", value="amazon")
    assert evaluate_condition(condition, mail_row) is True

    condition_no_match = RuleCondition(field="sender", operator="contains", value="ebay")
    assert evaluate_condition(condition_no_match, mail_row) is False


def test_evaluate_condition_importance_gte_without_analysis_is_false(storage, user_id):
    mail_row = storage.save_mail(user_id, make_mail())
    condition = RuleCondition(field="importance_score", operator="gte", value=3)
    assert evaluate_condition(condition, mail_row) is False


def test_evaluate_condition_importance_gte_with_analysis(storage, user_id):
    mail_row = storage.save_mail(user_id, make_mail())
    storage.save_analysis(
        mail_row.id,
        AnalysisResult(
            category="shopping",
            importance_score=4,
            sentiment="neutral",
            summary="s",
            recommended_action="archive",
            ollama_model="mistral",
        ),
    )
    mails = storage.list_mails(user_id)
    condition = RuleCondition(field="importance_score", operator="gte", value=3)
    assert evaluate_condition(condition, mails[0]) is True


def test_rules_engine_archives_matching_mail(storage, user_id):
    mail_row = storage.save_mail(user_id, make_mail())
    condition = RuleCondition(field="sender", operator="contains", value="amazon")
    storage.create_rule(user_id, name="Archive Amazon", condition=condition.to_json(), action="archive", priority=1)

    engine = RulesEngine(storage)
    affected = engine.run_for_user(user_id)

    assert affected == 1
    active_mails = storage.list_mails(user_id)
    assert active_mails == []


def test_rules_engine_sets_category(storage, user_id):
    mail_row = storage.save_mail(user_id, make_mail())
    condition = RuleCondition(field="sender", operator="contains", value="amazon", set_category="shopping")
    storage.create_rule(user_id, name="Categorize Amazon", condition=condition.to_json(), action="category", priority=1)

    engine = RulesEngine(storage)
    engine.run_for_user(user_id)

    mails = storage.list_mails(user_id)
    assert mails[0].analysis is not None
    assert mails[0].analysis.category == "shopping"


def test_rules_engine_inactive_rule_not_applied(storage, user_id):
    storage.save_mail(user_id, make_mail())
    condition = RuleCondition(field="sender", operator="contains", value="amazon")
    storage.create_rule(
        user_id, name="Archive Amazon", condition=condition.to_json(), action="archive", priority=1, is_active=False
    )

    engine = RulesEngine(storage)
    affected = engine.run_for_user(user_id)

    assert affected == 0
    assert len(storage.list_mails(user_id)) == 1


def test_rules_engine_first_matching_rule_wins(storage, user_id):
    storage.save_mail(user_id, make_mail())
    flag_condition = RuleCondition(field="sender", operator="contains", value="amazon")
    archive_condition = RuleCondition(field="sender", operator="contains", value="amazon")
    storage.create_rule(user_id, name="Flag first", condition=flag_condition.to_json(), action="flag", priority=1)
    storage.create_rule(user_id, name="Archive second", condition=archive_condition.to_json(), action="archive", priority=2)

    engine = RulesEngine(storage)
    engine.run_for_user(user_id)

    mails = storage.list_mails(user_id)
    assert len(mails) == 1
    assert mails[0].is_important is True
    assert mails[0].is_archived is False
