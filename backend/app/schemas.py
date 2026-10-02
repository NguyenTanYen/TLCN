"""Lược đồ dữ liệu vào (request body) – kiểm tra hợp lệ bằng Pydantic."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginIn(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class OptionIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    is_correct: bool = False


class CLOWeightIn(BaseModel):
    clo_id: int
    weight: float = Field(gt=0, le=1)


class QuestionIn(BaseModel):
    course_id: int
    outline_id: Optional[int] = None
    bloom_level_id: int = Field(ge=1, le=6)
    content: str = Field(min_length=3, max_length=20000)
    options: list[OptionIn]
    clos: list[CLOWeightIn]

    @model_validator(mode="after")
    def _check(self):
        if not 2 <= len(self.options) <= 10:
            raise ValueError("Câu hỏi phải có từ 2 đến 10 phương án")
        if sum(o.is_correct for o in self.options) != 1:
            raise ValueError("Câu hỏi trắc nghiệm phải có đúng 1 phương án đúng")
        if not self.clos:
            raise ValueError("Phải gán ít nhất 1 CĐR môn học (CLO)")
        if abs(sum(c.weight for c in self.clos) - 1.0) > 1e-6:
            raise ValueError("Tổng trọng số CLO của câu hỏi phải bằng 1.0")
        if len({c.clo_id for c in self.clos}) != len(self.clos):
            raise ValueError("Mỗi CLO chỉ được gán một lần")
        return self


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class ExamItemIn(BaseModel):
    question_id: int
    points: float = Field(gt=0, le=100)


class ExamIn(BaseModel):
    class_section_id: int
    exam_title: str = Field(min_length=3, max_length=255)
    assessment_type: Literal["process", "final"] = "final"
    exam_type: Literal["online", "paper"] = "online"
    exam_date: Optional[date] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0, le=600)
    max_score: float = Field(default=10, gt=0, le=999)
    items: list[ExamItemIn]

    @field_validator("items")
    @classmethod
    def _items(cls, v):
        if not v:
            raise ValueError("Vui lòng chọn ít nhất 1 câu hỏi")
        if len({i.question_id for i in v}) != len(v):
            raise ValueError("Câu hỏi bị trùng trong đề")
        return v


class LinkQuizIn(BaseModel):
    moodle_quiz_id: int = Field(gt=0)


class PublishIn(BaseModel):
    publish: bool


class CLOPlanIn(BaseModel):
    clo_id: int
    semester_id: int
    assessments_text: Optional[str] = Field(default=None, max_length=255)
    evidence_type: Literal["process", "final", "any"] = "final"
    method: str = Field(default="Bài KT trắc nghiệm", min_length=1, max_length=100)
    cycle: str = Field(default="1 lần/HK", min_length=1, max_length=30)
    pass_threshold_pct: float = Field(default=60, ge=0, le=100)
    target_pct: float = Field(default=70, ge=0, le=100)


class CLOIn(BaseModel):
    course_id: int
    clo_code: str = Field(min_length=1, max_length=10)
    description: str = Field(min_length=3)
    bloom_level_id: Optional[int] = Field(default=None, ge=1, le=6)
    plos: list[dict] = []  # [{plo_id, level}]


class PIPlanIn(BaseModel):
    pi_id: int
    course_id: int
    semester_id: int
    method: str = Field(min_length=1, max_length=150)
    cycle: str = Field(default="2 năm/lần", min_length=1, max_length=30)
    target_pct: float = Field(default=75, ge=0, le=100)
    lecturer_id: Optional[int] = None
    clo_ids: list[int] = []


class PLOIn(BaseModel):
    description: Optional[str] = None
    target_pct: Optional[float] = Field(default=None, ge=0, le=100)


class NarrativeIn(BaseModel):
    analysis: Optional[str] = None
    improvement: Optional[str] = None


class PLONarrativeIn(BaseModel):
    analysis: Optional[str] = None
    improvement_actions: Optional[str] = None
    improvement_results: Optional[str] = None
    evidence_tools: Optional[str] = None


class MatrixCellIn(BaseModel):
    outline_id: Optional[int] = None
    bloom_level_id: int = Field(ge=1, le=6)
    n: int = Field(ge=0, le=200)


class BlueprintIn(BaseModel):
    """Sinh đề theo ma trận: nhập số câu (tự lập ma trận) hoặc ma trận chi tiết chương × mức Bloom."""
    n_questions: Optional[int] = Field(default=None, ge=1, le=200)
    total_points: float = Field(default=10, gt=0, le=999)
    outline_ids: list[int] = []            # rỗng = mọi chương; có giá trị = kiểm tra theo chương
    clo_ids: list[int] = []                # rỗng = mọi CLO có câu trong phạm vi
    bloom_preset: Literal["balanced", "basic", "advanced", "custom"] = "balanced"
    bloom_mix: dict[int, float] = {}       # dùng khi bloom_preset = custom: {mức: %}
    matrix: list[MatrixCellIn] = []        # ma trận do GV nhập (nếu có thì bỏ qua n_questions)
    min_per_clo: Optional[int] = Field(default=None, ge=0, le=20)
    fixed_ids: list[int] = []              # câu GV đã chọn tay, luôn giữ
    prefer_unused: bool = True
    seed: Optional[int] = None

    @model_validator(mode="after")
    def _need(self):
        if not self.n_questions and not any(c.n for c in self.matrix):
            raise ValueError("Nhập số câu hoặc ma trận đề")
        if self.bloom_preset == "custom" and sum(self.bloom_mix.values()) <= 0:
            raise ValueError("Phân bố mức Bloom tùy chỉnh phải có tổng > 0")
        return self
