from nlp.conversation import ConversationManager
from nlp.llm_parser import HVACConstraint


def test_store_constraint():

    manager = ConversationManager()

    constraint = HVACConstraint(
        zone_id="Room 3",
        parameter="temperature",
        direction="decrease",
        intensity="strong",
        confidence=0.95,
        raw_text="Room 3 is too hot",
    )

    manager.store_constraint(constraint)

    assert manager.state.zone_id == "Room 3"
    assert manager.state.parameter == "temperature"
    assert manager.state.direction == "decrease"
    assert manager.state.intensity == "strong"

    assert manager.state.issue_active is True
    assert manager.state.awaiting_resolution is True


def test_yes_resets_conversation():

    manager = ConversationManager()

    manager.state.zone_id = "Room 3"
    manager.state.issue_active = True
    manager.state.awaiting_resolution = True

    result = manager.handle_resolution("yes")

    assert result["type"] == "resolved"

    assert manager.state.zone_id is None
    assert manager.state.parameter is None
    assert manager.state.issue_active is False
    assert manager.state.awaiting_resolution is False


def test_no_continues_conversation():

    manager = ConversationManager()

    manager.state.zone_id = "Room 3"
    manager.state.parameter = "temperature"
    manager.state.issue_active = True
    manager.state.awaiting_resolution = True

    result = manager.handle_resolution("no")

    assert result["type"] == "continue"

    assert manager.state.zone_id == "Room 3"
    assert manager.state.issue_active is True
    assert manager.state.awaiting_resolution is False


def test_ambiguous_resolution():

    manager = ConversationManager()

    manager.state.zone_id = "Room 3"
    manager.state.awaiting_resolution = True

    result = manager.handle_resolution("maybe")

    assert result["type"] == "clarification"
    assert "yes or no" in result["reply"]