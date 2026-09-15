import json
from pathlib import Path

from nlp.llm_parser import (
    ClarificationResponse,
    fallback_parser,
)


DATASET_PATH = Path(__file__).parent.parent / "test_complaints.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def test_fallback_parser():
    test_cases = load_test_cases()

    for case in test_cases:
        result = fallback_parser(case["complaint"])

        if case.get("expected_clarification"):
            assert result is None

        else:
            # The fallback is intentionally simple.
            # It only needs to recognize obvious HVAC complaints.
            if result is not None:
                assert result.parameter in [
                    "temperature",
                    "humidity",
                    "airflow",
                ]

                assert result.direction in [
                    "increase",
                    "decrease",
                ]

                assert result.intensity in [
                    "slight",
                    "moderate",
                    "strong",
                ]

                assert 0.0 <= result.confidence <= 1.0


def test_fallback_temperature():
    result = fallback_parser("The room is freezing")

    assert result is not None
    assert result.parameter == "temperature"
    assert result.direction == "increase"


def test_fallback_humidity():
    result = fallback_parser("The room is humid")

    assert result is not None
    assert result.parameter == "humidity"
    assert result.direction == "decrease"


def test_fallback_airflow():
    result = fallback_parser("The room feels stuffy")

    assert result is not None
    assert result.parameter == "airflow"
    assert result.direction == "increase"


def test_unrelated_complaint():
    result = fallback_parser("My WiFi is extremely slow")

    assert result is None