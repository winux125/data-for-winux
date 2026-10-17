"""Call the original RAG public API without changing decisions or its publication gate."""


def assess(runtime, bundle):
    return runtime.analyze(bundle).to_dict()


def publishable_assessments(result):
    return [assessment for assessment in result.get('assessments', [])
            if assessment.get('decision') == 'violation_supported'
            and assessment.get('publishable', {}).get('allowed') is True]
