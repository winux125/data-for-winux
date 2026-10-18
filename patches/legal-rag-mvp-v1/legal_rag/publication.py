"""Publication is separate from legal decisions and human-review metadata.

evidence_assisted is an opt-in MVP policy for decision support. It does not assert
that a human reviewed a card, or that generated visual observations are infallible.
"""
from dataclasses import asdict


def publication_status(result, card, config, *, real_backend):
    policy = config.publication
    allowed, reason = False, 'general_norm_reading_requires_review'
    if result.decision != 'violation_supported':
        reason = 'decision_' + result.decision
    elif card:
        if policy.mode == 'reviewed_only':
            allowed = card.review.human_reviewed and card.review.production_active
            reason = None if allowed else 'rule_not_production_active'
        elif card.rule_id not in policy.rule_ids:
            reason = 'rule_not_enabled_in_assisted_policy'
        elif result.norm.quote_sha256 not in card.pinned_text_sha256.values():
            reason = 'norm_hash_not_pinned'
        elif not result.context_completeness.get('complete'):
            reason = 'context_incomplete'
        elif not result.evidence or any(not e['evidence_refs'] for e in result.evidence if e['status'] != 'unknown'):
            reason = 'evidence_missing'
        elif result.generator == 'template_fallback' and not policy.allow_grounded_fallback:
            reason = 'validated_generation_required'
        else:
            allowed, reason = True, None
    if not real_backend:
        allowed, reason = False, 'test_or_template_backend'
    status = dict(allowed=bool(allowed), reason=reason, analysis_only=not allowed,
                  policy=policy.mode, human_review_required=True)
    if card:
        status['review'] = asdict(card.review)
    return status
