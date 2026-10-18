"""Reference extraction on real phrasing, closure, and the frozen pilot's regex gap."""
import re
from pathlib import Path
import unittest

from legal_rag.corpus import Corpus
from legal_rag.refs import ReferenceIndex

A231, A14, A230, A49 = 'V1900019680', 'V2000020075', 'V1700016120', 'V1900018545'
ROOT = Path(__file__).resolve().parents[2]


def setUpModule():
    global corpus, refs
    corpus = Corpus()
    refs = ReferenceIndex(corpus)


def targets(clause_id, resolution=None):
    return {t for r in refs.references(clause_id) if resolution in (None, r.resolution) for t in r.target_clause_ids}


class ReferenceTests(unittest.TestCase):
    def test_same_act_numeric_lists(self):
        self.assertEqual(targets(f'{A231}:19', 'same_act'), {f'{A231}:57', f'{A231}:58'})
        self.assertEqual(targets(f'{A231}:24', 'same_act'), {f'{A231}:106'})
        self.assertEqual(targets(f'{A231}:49', 'same_act'), {f'{A231}:46'})
        self.assertTrue({f'{A14}:{n}' for n in (12, 13, 14, 15, 21)} <= targets(f'{A14}:20', 'same_act'))
        self.assertIn('self_clause', {r.resolution for r in refs.references(f'{A14}:20')})

    def test_external_documents_are_not_resolved_into_the_corpus(self):
        reasons = {r.unresolved_reason for r in refs.references(f'{A231}:109-5')}
        self.assertIn('other_rules_not_in_corpus', reasons)
        self.assertTrue(all(r.resolution == 'external' for r in refs.references(f'{A49}:6')))
        self.assertTrue(all(not r.target_clause_ids for r in refs.references(f'{A49}:6')))

    def test_cross_act_document_links_to_corpus_acts(self):
        self.assertEqual(targets(f'{A231}:57', 'cross_act_document'), {f'{A230}:1'})
        self.assertEqual(targets(f'{A231}:5', 'cross_act_document'), {f'{A14}:1'})

    def test_footnotes_are_not_references(self):
        # 231:1 has 'Сноска. Пункт 1 - в редакции …' but its only reference is the legal basis.
        self.assertTrue(all(r.resolution == 'external' for r in refs.references(f'{A231}:1')))

    def test_closure_depth(self):
        deep = {cid for cid, _, _ in refs.closure([f'{A231}:19'], depth=2)[0]}
        shallow = {cid for cid, _, _ in refs.closure([f'{A231}:19'], depth=1)[0]}
        self.assertEqual(shallow, {f'{A231}:57', f'{A231}:58'})
        self.assertIn(f'{A230}:1', deep)

    def test_frozen_pilot_internal_reference_pattern_misses_real_phrasing(self):
        """Documents why rag_verdict_cv closure never fired; the pilot itself stays frozen."""
        # Frozen regression fixture copied from the pilot, not an import of its
        # entire historical experiment (which is not needed in the handoff).
        pilot_pattern = re.compile(
            r'\bпункт(?:а|е|ом|у)?\s+(\d+(?:-\d+)?)\s+настоящ(?:их|его)\s+(?:Правил|Положения|Требований)', re.I)
        text = '\n'.join(corpus.brief.body_lines[A231])
        self.assertEqual(len(pilot_pattern.findall(text)), 0)
        resolved = [r for cid in corpus.clauses if cid.startswith(A231) for r in refs.references(cid)
                    if r.resolution == 'same_act']
        self.assertGreaterEqual(len(resolved), 15)


if __name__ == '__main__':
    unittest.main()
