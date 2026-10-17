"""Clause exactness and structure on the real verified bundle (CPU, offline)."""
import unittest

from legal_rag.corpus import Corpus, sha256

A231, A14, A230, A253, A49 = 'V1900019680', 'V2000020075', 'V1700016120', 'V1200007926', 'V1900018545'


def setUpModule():
    global corpus
    corpus = Corpus()


class CorpusTests(unittest.TestCase):
    def test_clause_counts_per_act(self):
        counts = {}
        for clause in corpus.clauses.values():
            counts[clause.source_id] = counts.get(clause.source_id, 0) + 1
        self.assertEqual(counts, {A231: 154, A14: 24, A230: 39, A253: 9, A49: 94})

    def test_every_clause_is_exact_source_lines(self):
        for clause in corpus.clauses.values():
            lines = corpus.brief.body_lines[clause.source_id]
            a, z = clause.lines
            first, last = corpus.brief.sources[clause.source_id]['main_body_lines_1based']
            self.assertTrue(first <= a <= z <= last, clause.clause_id)
            self.assertEqual(clause.text, '\n'.join(lines[a - 1:z]) + '\n')
            self.assertEqual(clause.text_sha256, sha256(clause.text))
        self.assertEqual({k: v for k, v in corpus.orphans.items() if v}, {})

    def test_repealed_and_suspended_status(self):
        by_status = {}
        for clause in corpus.clauses.values():
            by_status.setdefault(clause.status, set()).add(clause.clause_id)
        self.assertEqual(by_status['repealed'], {f'{A231}:95', f'{A231}:97', f'{A14}:17', f'{A49}:18', f'{A49}:20',
                                                 f'{A49}:21'})
        self.assertEqual(by_status['suspended_wording_uncertain'], {f'{A14}:11', f'{A14}:14', f'{A14}:16'})
        self.assertEqual(by_status['partially_suspended_wording_uncertain'], {f'{A14}:13'})
        suspension = next(a for a in corpus.clause(f'{A14}:11').amendments if a.kind == 'suspended')
        self.assertEqual((suspension.suspended_until, suspension.act_number), ('2027-01-01', '88'))

    def test_official_note_belongs_to_following_clause(self):
        self.assertNotIn('Примечание ИЗПИ', corpus.clause(f'{A14}:10').text)
        notes = [text for _, text in corpus.clause(f'{A14}:11').notes]
        self.assertTrue(any(text.startswith('Действие пункта 11') for text in notes))

    def test_definitions_and_amendments(self):
        terms = {d.item: d.term for d in corpus.definitions_in(f'{A231}:2')}
        self.assertEqual(len(terms), 22)
        self.assertEqual(terms['2'], 'контролирующий работник')
        self.assertTrue(corpus.definitions_in(f'{A253}:3'))
        last = corpus.clause(f'{A231}:2').amendments[-1]
        self.assertEqual((last.kind, last.act_date, last.act_number), ('redaction', '2026-03-16', '25'))
        self.assertIn('2026-07-12', {a.effective_from for a in corpus.clause(f'{A231}:74').amendments})

    def test_aliases_and_act_metadata(self):
        targets = {a.name: a.target_source_id for a in corpus.aliases[A231]}
        self.assertEqual(targets['Правила организации охраны и устройства помещений'], A14)
        self.assertEqual(targets['Правила № 230'], A230)
        self.assertEqual(corpus.acts[A231].adopted, '2019-11-29')
        # The official text of No. 14 prints 'от "24" февраля года № 14' without a year: never invent it.
        self.assertIsNone(corpus.acts[A14].adopted)


if __name__ == '__main__':
    unittest.main()
