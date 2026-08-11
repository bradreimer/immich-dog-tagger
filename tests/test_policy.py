from immich_dog_tagger.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassifierPolicy,
)


def test_default_policy_version_and_threshold():
    assert DEFAULT_POLICY.version == "v1"
    assert DEFAULT_POLICY.confident_threshold == 0.80
    assert DEFAULT_POLICY.candidate_limit == 3


def test_decide_unknown_when_no_identity():
    decision = DEFAULT_POLICY.decide(identity=None, similarity=-1.0)

    assert decision is ClassificationDecision.UNKNOWN


def test_decide_confident_at_or_above_threshold():
    decision = DEFAULT_POLICY.decide(identity="Fibs", similarity=0.80)

    assert decision is ClassificationDecision.CONFIDENT


def test_decide_needs_review_below_threshold():
    decision = DEFAULT_POLICY.decide(identity="Fibs", similarity=0.79)

    assert decision is ClassificationDecision.NEEDS_REVIEW


def test_decide_confident_well_above_threshold():
    decision = DEFAULT_POLICY.decide(identity="Fibs", similarity=0.99)

    assert decision is ClassificationDecision.CONFIDENT


def test_custom_policy_threshold_moves_boundary():
    policy = ClassifierPolicy(version="v2-strict", confident_threshold=0.95)

    assert policy.decide(identity="Fibs", similarity=0.90) is (
        ClassificationDecision.NEEDS_REVIEW
    )
    assert policy.decide(identity="Fibs", similarity=0.95) is (
        ClassificationDecision.CONFIDENT
    )
