"""Document and validate the jury contract while preserving rich source details."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Extensible(BaseModel):
    model_config = ConfigDict(extra='allow')


class Submission(BaseModel):
    job_id: str
    status: Literal['processing']


class EvidenceFrame(BaseModel):
    timestamp_sec: float = Field(ge=0, allow_inf_nan=False)
    image_base64: str = Field(min_length=1, description='JPEG bytes encoded as base64')


class Violation(Extensible):
    type: str = Field(min_length=1)
    timecode_sec: float = Field(ge=0, allow_inf_nan=False)
    description: str = Field(min_length=1, description='Visible action, conditional explanation and source citation')
    evidence_frames: list[EvidenceFrame] = Field(min_length=1, max_length=3)
    rule: dict | None = Field(default=None, description='Full quotation, hierarchy and related provisions; never cropped')


class DoneJob(Extensible):
    job_id: str
    status: Literal['done']
    verdict: Literal['violation', 'no_violation']
    violations: list[Violation]

    @model_validator(mode='after')
    def consistent_verdict(self):
        if bool(self.violations) != (self.verdict == 'violation'):
            raise ValueError('The verdict must match the published event list')
        return self


class ProcessingJob(Extensible):
    job_id: str
    status: Literal['processing']
    stage: str | None = None
    queue_position: int | None = Field(default=None, ge=0)


class FailedJob(Extensible):
    job_id: str
    status: Literal['failed']
    stage: str | None = None
    error: str | None = None

    @model_validator(mode='before')
    @classmethod
    def no_clean_error(cls, data):
        if isinstance(data, dict) and ('verdict' in data or 'violations' in data):
            raise ValueError('An error must not carry a verdict')
        return data


JobResponse = Annotated[DoneJob | ProcessingJob | FailedJob, Field(discriminator='status')]


def append_citation(description, rule):
    """Include a source in the required field even if a jury ignores extensions."""
    title = ('Правила осуществления кассовых операций и инкассации №231'
             if str(rule.get('unit_id', '')).startswith('V1900019680:') else rule['title'])
    relation = 'Источник (общий контекст)' if rule.get('source_relation') == 'context_only' else 'Источник'
    parts = [title, rule.get('section'), rule.get('url')]
    citation = relation + ': ' + '; '.join(p for p in parts if p)
    return description.rstrip() + '\n' + citation
