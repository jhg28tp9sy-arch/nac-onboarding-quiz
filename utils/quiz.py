from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import Random

from utils.roster import Staff, photo_path
from utils.scoring import normalize

FIELDS = {"role_recall": "role", "name_recall": "name"}


@dataclass(frozen=True)
class Question:
    staff: Staff
    options: tuple[str, ...] = ()
    review_only: bool = False


@dataclass
class Attempt:
    questions: list[Question]
    index: int = 0
    answers: dict[int, tuple[str, ...]] = field(default_factory=dict)
    retry: bool | None = None
    ended_early: bool = False
    review_questions: list[Question] = field(default_factory=list)

    @property
    def finished(self):
        return self.index == len(self.questions)

    def submit(self, index, *values):
        if self.finished or index != self.index or index in self.answers:
            return False
        self.answers[index] = values
        return True

    def advance(self, index):
        if self.finished or index != self.index or index not in self.answers:
            return False
        self.index += 1
        return True

    def end(self):
        if not self.finished:
            self.ended_early = len(self.answers) < len(self.questions)
            self.index = len(self.questions)


@dataclass(frozen=True)
class QuizResult:
    attempt: Attempt
    rows: list[dict[str, str]]
    missed: set[str]
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def make_questions(mode, staff, root, *, ids=None, rng=None):
    rng = rng or Random()
    active = [record for record in staff if record.active]
    if mode == "name_recall":
        active = [record for record in active if photo_path(record, root) is not None]
    eligible = [record for record in active if getattr(record, mode)
                and (ids is None or record.id in ids)]
    rng.shuffle(eligible)
    field_name = FIELDS.get(mode)
    questions = []
    for record in eligible:
        if field_name is None:
            questions.append(Question(record, review_only=photo_path(record, root) is None))
            continue
        correct = getattr(record, field_name)
        seen = {normalize(correct)}
        candidates = []
        # Prefer distractors from the same department, with randomized ties.
        others = rng.sample(active, len(active))
        others.sort(key=lambda person: person.department != record.department)
        for person in others:
            value = getattr(person, field_name)
            key = normalize(value)
            if key and key not in seen:
                candidates.append(value)
                seen.add(key)
            if len(candidates) == 3:
                break
        if len(candidates) == 3:
            options = [correct, *candidates]
            rng.shuffle(options)
            questions.append(Question(record, tuple(options)))
        else:
            questions.append(Question(record))
    return questions
