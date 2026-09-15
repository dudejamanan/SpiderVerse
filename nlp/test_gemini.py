from nlp.llm_parser import (
    parse_complaint,
    HVACConstraint,
    ClarificationResponse,
)


def run_complaint_test(complaint: str):
    print("\n" + "=" * 60)
    print(f"Complaint: {complaint}")
    print("=" * 60)

    result = parse_complaint(complaint)

    if isinstance(result, HVACConstraint):
        print("RESULT: HVAC CONSTRAINT")
        print(f"Room/Zone : {result.zone_id}")
        print(f"Parameter : {result.parameter}")
        print(f"Direction : {result.direction}")
        print(f"Intensity : {result.intensity}")
        print(f"Confidence: {result.confidence}")
        print(f"Raw text  : {result.raw_text}")

    elif isinstance(result, ClarificationResponse):
        print("RESULT: CLARIFICATION REQUIRED")
        print(f"Question: {result.message}")


if __name__ == "__main__":

    # Test ONE complaint at a time.
    complaint = input("\nEnter occupant complaint: ")

    run_complaint_test(complaint)