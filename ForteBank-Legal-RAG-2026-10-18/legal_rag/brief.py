"""Offline legal section context for discovery; exact source retrieval is separate."""
import hashlib
import json
from pathlib import Path
import re

from .paths import CORE_DIR

DEFAULT_BUNDLE = CORE_DIR / "section_briefs.json"
SECTION_FIELDS = {'section_id','source_id','official_heading','short_title','seek','limits',
    'source_lines_1based','section_text_sha256','clause_ids','summary_role','legal_verdict_enabled'}
SOURCE_FIELDS = {'source_id','number','scope','official_url','snapshot_path','snapshot_sha256',
    'text_path','text_sha256','retrieved_utc','revision_instant','official_is_actual',
    'official_in_force','main_body_lines_1based','appendices'}
ROOT_FIELDS = {'schema_version','bundle_id','date','status','legal_verdict_enabled',
               'section_coverage','sources','sections'}
POLICY = (
    'НОРМАТИВНАЯ КАРТА ДЛЯ ПОИСКА НАБЛЮДЕНИЙ. Это общая для всех видео сводка разделов, '
    'не доказательства и не готовые юридические вердикты. Используй её, чтобы замечать '
    'действия, этапы, нормальные объяснения и неопределённость во всём видео. '
    'Не выбирай для просмотра только ожидаемый тип события. Ищи и непокрытые действия. '
    'В candidate_section_ids укажи 0–4 идентификатора разделов из карты, которые стоит '
    'проверить по полному тексту; они не означают нарушение и не заменяют номер пункта. '
    'Пустой список допустим. Невидимое действие не равно отсутствовавшему; учитывай '
    'цифровые документы, перекрытия, начало/конец обслуживания и неизвестные полномочия. '
    'Одежда не доказывает должность; дата загрузки не является датой события. '
    'При неустановленной дате применимость редакции остаётся неизвестной. '
    'Каждый факт привяжи к реальным frame_ids/PTS; список кадров может быть непоследовательным, '
    'его крайние времена не доказывают непрерывность. Подлинность денег и содержание '
    'нечитаемых документов не угадывай. Для точного юридического решения нужны полный '
    'пункт, условия, исключения, применимая редакция и независимая проверка кадров.'
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Brief:
    def __init__(self, path=DEFAULT_BUNDLE):
        self.path = Path(path).resolve()
        self.raw = self.path.read_bytes()
        self.bundle = json.loads(self.raw)
        b = self.bundle
        if (set(b) != ROOT_FIELDS or b['schema_version'] != 1 or
                b['legal_verdict_enabled'] is not False or not b['sources'] or not b['sections']):
            raise ValueError('Invalid discovery brief; no annotation/example fields allowed.')
        self.sources, self.sections, self.texts = {}, {}, {}
        self.body_lines = {}
        for source in b['sources']:
            if set(source) != SOURCE_FIELDS:
                raise ValueError('Invalid source fields.')
            code = source['source_id']
            if code in self.sources or not (source['official_is_actual'] is True and source['official_in_force'] is True):
                raise ValueError('Duplicate or inactive official source.')
            if source['official_url'] != 'https://adilet.zan.kz/rus/docs/' + code:
                raise ValueError('Expected official source URL.')
            for name in ('snapshot','text'):
                file = (self.path.parent/source[name+'_path']).resolve()
                if self.path.parent not in file.parents:
                    raise ValueError('Source path escaped bundle.')
                data = file.read_bytes()
                if digest(data) != source[name+'_sha256']:
                    raise ValueError('Source hash mismatch: ' + code)
                if name == 'text':
                    self.body_lines[code] = data.decode('utf-8').splitlines()
            self.sources[code] = source
        for section in b['sections']:
            if (set(section) != SECTION_FIELDS or section['summary_role'] != 'discovery_hint_only'
                    or section['legal_verdict_enabled'] is not False):
                raise ValueError('Invalid section fields; no per-video examples or gold labels allowed.')
            sid, code = section['section_id'], section['source_id']
            if sid in self.sections or code not in self.sources:
                raise ValueError('Duplicate/unknown section.')
            if not re.fullmatch(r'\d+\.(?:general|g\d+(?:\.p\d+(?:-\d+)?)?)',sid):
                raise ValueError('Invalid section ID.')
            for key in ('short_title','seek','limits'):
                if not isinstance(section[key],str) or not section[key] or len(section[key]) > 300:
                    raise ValueError('Missing/oversized summary field.')
            a,z = section['source_lines_1based']
            lines = self.body_lines[code]
            if not 1 <= a <= z <= len(lines):
                raise ValueError('Invalid source line range.')
            text = '\n'.join(lines[a-1:z])+'\n'
            if digest(text.encode()) != section['section_text_sha256']:
                raise ValueError('Section text hash mismatch.')
            if not sid.endswith('.general') and lines[a-1] != section['official_heading']:
                raise ValueError('Section heading mismatch.')
            self.sections[sid], self.texts[sid] = section, text
        # Every main-body heading must occur once; appendix forms are explicitly excluded.
        for code, source in self.sources.items():
            a,z = source['main_body_lines_1based']
            expected = {(i+1,s) for i,s in enumerate(self.body_lines[code]) if a <= i+1 <= z and
                        re.match(r'^(?:Глава|Параграф)\s+\d',s)}
            actual = {(s['source_lines_1based'][0],s['official_heading']) for s in self.sections.values()
                      if s['source_id'] == code and not s['section_id'].endswith('.general')}
            if expected != actual:
                raise ValueError('Incomplete main-body section coverage: ' + code)

    def render(self, max_chars=22000):
        parts = [POLICY, '\n<legal_section_map>']
        for source in self.sources.values():
            parts.append('Акт '+source['number']+': '+source['scope'])
        for s in self.sections.values():
            parts.append(f"[{s['section_id']}] {s['short_title']}. {s['seek']} Ограничение: {s['limits']}")
        parts.append('</legal_section_map>')
        text = '\n'.join(parts)
        if len(text) > max_chars:
            raise ValueError('Complete section map exceeds budget; do not silently drop sections.')
        return text

    def full_sections(self, ids):
        """Exact source packets for later normative retrieval; never a legal verdict.

        Include source-wide applicability/time notes: a section alone can omit them.
        Linked acts and internal documents still require further retrieval when relevant.
        """
        if len(ids) != len(set(ids)) or any(sid not in self.sections for sid in ids):
            raise ValueError('Unknown/duplicate legal section IDs.')
        result = []
        for sid in ids:
            section = self.sections[sid]
            source = self.sources[section['source_id']]
            a,_ = source['main_body_lines_1based']
            preamble = '\n'.join(self.body_lines[section['source_id']][:a-1])
            general = next(s for s in self.sections.values() if s['source_id'] == source['source_id'])
            result.append(dict(section_id=sid, source_id=source['source_id'],
                official_url=source['official_url'], revision_instant=source['revision_instant'],
                source_sha256=source['text_sha256'], exact_section_text=self.texts[sid],
                document_preamble_and_temporal_notes=preamble,
                document_general_provisions=self.texts[general['section_id']],
                applicability_date_verified=False, active_verdict_rule=False))
        return result

    def metadata(self):
        rendered = self.render()
        return dict(mode='legal_brief', bundle_id=self.bundle['bundle_id'],
            bundle_sha256=digest(self.raw), rendered_sha256=digest(rendered.encode()),
            sources=len(self.sources), sections=len(self.sections), characters=len(rendered),
            source_text_sha256={k:v['text_sha256'] for k,v in self.sources.items()},
            legal_verdict_enabled=False)
