"""Call the original RAG public API without changing decisions or its publication gate."""


def assess(runtime, bundle):
    return runtime.analyze(bundle).to_dict()


def publishable_assessments(result):
    return [assessment for assessment in result.get('assessments', [])
            if assessment.get('decision') == 'violation_supported'
            and assessment.get('publishable', {}).get('allowed') is True]


def publishable_review_findings(result):
    """Explicit review contract; never upgrades an insufficient formal assessment."""
    if result.get('schema') != 'legal_rag.review.v1':
        return []
    return [row for row in result.get('review_findings', [])
            if row.get('schema') == 'legal_rag.review.v1'
            and row.get('finding_kind') == 'possible_indication'
            and row.get('human_review_required') is True
            and row.get('source_relation') in ('candidate_clause', 'context_only')
            and row.get('evidence')
            and row.get('publishable', {}).get('allowed') is True
            and row['publishable'].get('policy') == 'possible_indications']
