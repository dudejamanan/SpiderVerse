
from nlp.llm_parser import (
    HVACConstraint,
    ClarificationResponse,
    fallback_parser,
    parse_complaint,
    parse_complaint_with_context,
)


# ============================================================
# Basic complaint parsing
# ============================================================

def test_parse_hot_room():

    result = parse_complaint(
        "Room 3 is too hot"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 3"
    assert result.parameter == "temperature"
    assert result.direction == "decrease"


def test_parse_cold_room():

    result = parse_complaint(
        "Room 2 is freezing"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 2"
    assert result.parameter == "temperature"
    assert result.direction == "increase"


# ============================================================
# Humidity
# ============================================================

def test_parse_humid_room():

    result = parse_complaint(
        "Conference Room is too humid"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Conference Room"
    assert result.parameter == "humidity"
    assert result.direction == "decrease"


def test_parse_dry_room():

    result = parse_complaint(
        "Lab 3 is too dry"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Lab 3"
    assert result.parameter == "humidity"
    assert result.direction == "increase"


# ============================================================
# Airflow
# ============================================================

def test_parse_stuffy_room():

    result = parse_complaint(
        "Lab 3 feels stuffy"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Lab 3"
    assert result.parameter == "airflow"
    assert result.direction == "increase"


def test_parse_strong_airflow():

    result = parse_complaint(
        "There is too much air blowing in Room 4"
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 4"
    assert result.parameter == "airflow"
    assert result.direction == "decrease"


# ============================================================
# Missing room
# ============================================================

def test_missing_room():

    result = parse_complaint(
        "It is too cold"
    )

    assert isinstance(
        result,
        ClarificationResponse
    )

    assert result.clarification_needed is True

    assert (
        "room" in result.message.lower()
        or "zone" in result.message.lower()
    )


# ============================================================
# Missing HVAC issue
# ============================================================

def test_room_without_hvac_issue():

    result = parse_complaint(
        "Room 3"
    )

    assert isinstance(
        result,
        ClarificationResponse
    )

    assert result.clarification_needed is True


# ============================================================
# Local fallback parser
# ============================================================

def test_fallback_parser_extracts_constraint():

    result = fallback_parser(
        "Room 2 is too hot"
    )

    assert result is not None

    assert result.zone_id == "Room 2"
    assert result.parameter == "temperature"
    assert result.direction == "decrease"


# ============================================================
# Context-aware parsing
# ============================================================

def test_context_supplies_existing_room():

    result = parse_complaint_with_context(
        "It is too cold now",
        existing_zone="Room 3",
        existing_parameter="temperature",
        existing_direction="decrease",
        existing_intensity="strong",
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 3"
    assert result.parameter == "temperature"
    assert result.direction == "increase"


def test_context_supplies_room_for_cooler_request():

    result = parse_complaint_with_context(
        "make it cooler",
        existing_zone="Room 3",
        existing_parameter="temperature",
        existing_direction="increase",
        existing_intensity="strong",
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 3"
    assert result.parameter == "temperature"
    assert result.direction == "decrease"


def test_context_supplies_room_for_airflow():

    result = parse_complaint_with_context(
        "I need more fresh air",
        existing_zone="Room 5",
        existing_parameter="airflow",
        existing_direction="increase",
        existing_intensity="moderate",
    )

    assert isinstance(
        result,
        HVACConstraint
    )

    assert result.zone_id == "Room 5"
    assert result.parameter == "airflow"
    assert result.direction == "increase"


# ============================================================
# Input validation
# ============================================================

def test_empty_complaint():

    try:
        parse_complaint("")

        assert False, (
            "Expected ValueError for empty complaint"
        )

    except ValueError:
        pass


def test_non_string_complaint():

    try:
        parse_complaint(None)

        assert False, (
            "Expected TypeError for non-string complaint"
        )

    except TypeError:
        pass
    
