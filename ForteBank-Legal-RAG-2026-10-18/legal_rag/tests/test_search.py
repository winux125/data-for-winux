"""Stemmer, BM25 behaviour, lexicon validation and a retrieval regression floor."""
import json
from pathlib import Path
import tempfile
import unittest

from legal_rag.__main__ import DEFAULT_QUERIES, evaluate
from legal_rag.api import LegalRAG
from legal_rag.bm25 import Lexicon
from legal_rag.text import stem, stem_tokens

A231 = 'V1900019680'


def setUpModule():
    global rag
    rag = LegalRAG()


class StemTests(unittest.TestCase):
    def test_paradigms_share_a_stem(self):
        for forms in (('кассовый', 'кассового', 'кассовым'), ('правила', 'правил', 'правилами'),
                      ('работник', 'работника', 'работником'), ('обслуживание', 'обслуживания')):
            self.assertEqual(len({stem(f) for f in forms}), 1, forms)
        self.assertEqual(stem_tokens('Пересчёт'), stem_tokens('пересчет'))
        self.assertEqual(stem_tokens('пункт 10-1 и 22'), ['пункт', '10-1', '22'])


class SearchTests(unittest.TestCase):
    def test_leaving_workplace_finds_clause_22(self):
        hits = rag.search('Кассир ушёл с рабочего места, клиент ещё у окна', k=3)
        self.assertEqual(hits[0].clause_id, f'{A231}:22')

    def test_repealed_clauses_are_not_indexed_and_filters_work(self):
        hits = rag.search('Исключен постановлением Правления', k=50)
        self.assertTrue(all(rag.corpus.clause(h.clause_id).status != 'repealed' for h in hits))
        only = rag.search('дверь касса замок', k=5, source_ids={'V2000020075'})
        self.assertTrue(only and all(h.clause_id.startswith('V2000020075') for h in only))

    def test_deterministic_order(self):
        query = 'пересчет наличных денег в присутствии клиента'
        self.assertEqual([h.clause_id for h in rag.search(query, k=10)], [h.clause_id for h in rag.search(query, k=10)])

    def test_lexicon_rejects_duplicates_and_single_word_phrases(self):
        good = {'id': 'x', 'predicates': [], 'phrases': ['покинул рабочее место'], 'terms': [], 'expansion': 'касса'}
        cases = [[good, good],                                              # duplicate id
                 [dict(good, phrases=['без пересчета'])],                    # one content word after stop words
                 [dict(good, phrases=[], terms=['рабочее место'])],          # a term must be one word
                 [dict(good, phrases=[], predicates=[])]]                    # cannot fire at all
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lexicon.json'
            for entries in cases:
                path.write_text(json.dumps({'schema_version': 2, 'entries': entries}, ensure_ascii=False),
                                encoding='utf-8')
                with self.assertRaises(ValueError):
                    Lexicon(path)

    def test_generic_words_do_not_expand_but_predicates_and_phrases_do(self):
        for neutral in ('Погода за окном солнечная', 'Один человек стоит у стены', 'На столе лежит ручка',
                        'Сотрудник взял свои вещи и ушёл домой после смены', 'Клиент открыл дверь и вошёл в зал',
                        'Посетитель держит телефон и читает новости', 'Ключ от машины на столе'):
            self.assertEqual(rag.index.query_weights(neutral)[1], [], neutral)
        self.assertIn('cashier_leaves', rag.index.query_weights('работник', predicates={'left_workplace'})[1])
        self.assertIn('cashier_leaves', rag.index.query_weights('кассир покинул рабочее место')[1])
        # A generic transfer does not establish that the recipient is a client.
        self.assertNotIn('cash_issue', rag.index.query_weights('передача', predicates={'cash_transfer'})[1])

    def test_dev_tuned_targets_stay_reachable(self):
        """231:15 / 231:19 were reached by phrases added while looking at these dev queries (not a test result)."""
        core = {h.clause_id for h in rag.search('кассир не проверил удостоверение личности клиента', k=5)}
        self.assertIn(f'{A231}:19', core)
        expanded = [h['unit_id'] for h in rag.search_sources('кассир передал деньги другому кассиру без записи', k=5)]
        self.assertIn(f'{A231}:rules1:p15', expanded)

    def test_shared_instance_is_reused_and_warm_is_idempotent(self):
        import legal_rag
        first = legal_rag.shared().warm()
        self.assertIs(first, legal_rag.shared())
        self.assertIs(first.warm(), first)
        self.assertEqual([h['chunk_id'] for h in first.search_sources('кассир ушёл с рабочего места', k=5)],
                         [h['chunk_id'] for h in first.search_sources('кассир ушёл с рабочего места', k=5)])

    def test_stem_cache_matches_uncached_algorithm(self):
        uncached = stem.__wrapped__
        for word in ('кассового', 'Пересчёт', 'правилами', 'обслуживания', 'контролирующего', '22'):
            self.assertEqual(stem(word), uncached(word))

    def test_development_retrieval_floor(self):
        """Regression guard on author-written development queries, not a quality claim."""
        report = evaluate(rag, DEFAULT_QUERIES)
        lexicon = report['variants']['bm25_lexicon']
        self.assertGreaterEqual(lexicon['recall@5'], .85)
        self.assertGreaterEqual(lexicon['recall@5'], report['variants']['bm25']['recall@5'])


if __name__ == '__main__':
    unittest.main()
