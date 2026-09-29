"""Ánh xạ ORM cho 39 bảng của assessment_db (xem database/01_schema.sql).

Ràng buộc CHECK/UNIQUE được khai báo trong DDL; ORM chỉ khai báo cột, khóa và quan hệ cần dùng.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ---------------------------------------------------------------- A. Người dùng & tổ chức


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    lecturer: Mapped[Optional["Lecturer"]] = relationship(back_populates="user", uselist=False)
    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False)


class Lecturer(Base):
    __tablename__ = "lecturers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    lecturer_code: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(100))
    department: Mapped[Optional[str]] = mapped_column(String(150))
    user: Mapped[Optional[User]] = relationship(back_populates="lecturer")


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    student_code: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(100))
    class_name: Mapped[Optional[str]] = mapped_column(String(50))
    moodle_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    user: Mapped[Optional[User]] = relationship(back_populates="student")


class Semester(Base):
    __tablename__ = "semesters"
    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year: Mapped[str] = mapped_column(String(9))
    term: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

# ---------------------------------------------------------------- B. CTĐT & CĐR CTĐT


class Program(Base):
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(20), default="Đại học")
    department: Mapped[Optional[str]] = mapped_column(String(150))
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=75)
    plos: Mapped[list["PLO"]] = relationship(back_populates="program", order_by="PLO.plo_code")


class PLO(Base):
    __tablename__ = "plos"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    group_no: Mapped[int] = mapped_column(SmallInteger)
    plo_code: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=75)
    program: Mapped[Program] = relationship(back_populates="plos")
    pis: Mapped[list["PerformanceIndicator"]] = relationship(back_populates="plo", order_by="PerformanceIndicator.pi_code")
    measurement_plans: Mapped[list["PLOMeasurementPlan"]] = relationship(order_by="PLOMeasurementPlan.round_no")


class PLOMeasurementPlan(Base):
    __tablename__ = "plo_measurement_plans"
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id"), primary_key=True)
    round_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    academic_year: Mapped[str] = mapped_column(String(9))
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class PerformanceIndicator(Base):
    __tablename__ = "performance_indicators"
    id: Mapped[int] = mapped_column(primary_key=True)
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id"))
    pi_code: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    plo: Mapped[PLO] = relationship(back_populates="pis")


class ProgramCourse(Base):
    __tablename__ = "program_courses"
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), primary_key=True)


class PICourse(Base):
    __tablename__ = "pi_courses"
    pi_id: Mapped[int] = mapped_column(ForeignKey("performance_indicators.id"), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), primary_key=True)

# ---------------------------------------------------------------- C. Học phần & CLO


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(String(20))
    course_name: Mapped[str] = mapped_column(String(255))
    credits: Mapped[int] = mapped_column(SmallInteger)
    clo_target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=75)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    clos: Mapped[list["CLO"]] = relationship(back_populates="course", order_by="CLO.clo_code")
    outlines: Mapped[list["CourseOutline"]] = relationship(order_by="CourseOutline.chapter_number")


class CourseOutline(Base):
    __tablename__ = "course_outlines"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    chapter_number: Mapped[int] = mapped_column(SmallInteger)
    chapter_name: Mapped[str] = mapped_column(String(255))


class BloomLevel(Base):
    __tablename__ = "bloom_levels"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name_vi: Mapped[str] = mapped_column(String(50))


class CLO(Base):
    __tablename__ = "clos"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    clo_code: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    bloom_level_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bloom_levels.id"))
    course: Mapped[Course] = relationship(back_populates="clos")


class CLOPLOMapping(Base):
    __tablename__ = "clo_plo_mapping"
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), primary_key=True)
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id"), primary_key=True)
    level: Mapped[str] = mapped_column(String(1))

# ---------------------------------------------------------------- D. Kế hoạch đo lường


class CLOAssessmentPlan(Base):
    __tablename__ = "clo_assessment_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    assessments_text: Mapped[Optional[str]] = mapped_column(String(255))
    evidence_type: Mapped[str] = mapped_column(String(10), default="final")
    method: Mapped[str] = mapped_column(String(100), default="Bài KT trắc nghiệm")
    cycle: Mapped[str] = mapped_column(String(30), default="1 lần/HK")
    pass_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=60)
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=70)
    clo: Mapped[CLO] = relationship()


class PIAssessmentPlan(Base):
    __tablename__ = "pi_assessment_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    pi_id: Mapped[int] = mapped_column(ForeignKey("performance_indicators.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    method: Mapped[str] = mapped_column(String(150))
    cycle: Mapped[str] = mapped_column(String(30), default="2 năm/lần")
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=75)
    lecturer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lecturers.id"))
    pi: Mapped[PerformanceIndicator] = relationship()
    course: Mapped[Course] = relationship()
    semester: Mapped[Semester] = relationship()
    lecturer: Mapped[Optional[Lecturer]] = relationship()


class PIPlanCLO(Base):
    __tablename__ = "pi_plan_clos"
    plan_id: Mapped[int] = mapped_column(ForeignKey("pi_assessment_plans.id"), primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), primary_key=True)


class AssessmentAssignment(Base):
    __tablename__ = "assessment_assignments"
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), primary_key=True)
    note: Mapped[Optional[str]] = mapped_column(String(255))

# ---------------------------------------------------------------- E. Lớp HP & ngân hàng câu hỏi


class ClassSection(Base):
    __tablename__ = "class_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"))
    section_code: Mapped[str] = mapped_column(String(30))
    moodle_course_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    course: Mapped[Course] = relationship()
    semester: Mapped[Semester] = relationship()
    lecturer: Mapped[Lecturer] = relationship()


class Enrollment(Base):
    __tablename__ = "enrollments"
    class_section_id: Mapped[int] = mapped_column(ForeignKey("class_sections.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), default="active")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    student: Mapped[Student] = relationship()


class Question(Base):
    __tablename__ = "question_bank"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    outline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("course_outlines.id"))
    bloom_level_id: Mapped[int] = mapped_column(ForeignKey("bloom_levels.id"))
    question_type: Mapped[str] = mapped_column(String(30), default="multichoice")
    content: Mapped[str] = mapped_column(Text)
    moodle_question_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    options: Mapped[list["QuestionOption"]] = relationship(order_by="QuestionOption.position", cascade="all, delete-orphan")
    clo_links: Mapped[list["QuestionCLO"]] = relationship(cascade="all, delete-orphan")
    outline: Mapped[Optional[CourseOutline]] = relationship()
    bloom: Mapped[BloomLevel] = relationship()


class QuestionOption(Base):
    __tablename__ = "question_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question_bank.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    opt_label: Mapped[str] = mapped_column(String(1))
    content: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    moodle_answer_id: Mapped[Optional[int]] = mapped_column(BigInteger)


class QuestionCLO(Base):
    __tablename__ = "question_clo_mapping"
    question_id: Mapped[int] = mapped_column(ForeignKey("question_bank.id"), primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=1)
    clo: Mapped[CLO] = relationship()

# ---------------------------------------------------------------- F. Đề thi


class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_section_id: Mapped[int] = mapped_column(ForeignKey("class_sections.id"))
    exam_title: Mapped[str] = mapped_column(String(255))
    assessment_type: Mapped[str] = mapped_column(String(10), default="final")
    exam_type: Mapped[str] = mapped_column(String(10), default="online")
    exam_date: Mapped[Optional[date]] = mapped_column(Date)
    duration_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=10)
    moodle_quiz_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    publish_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    class_section: Mapped[ClassSection] = relationship()
    questions: Mapped[list["ExamQuestion"]] = relationship(order_by="ExamQuestion.order_index", cascade="all, delete-orphan")
    versions: Mapped[list["ExamVersion"]] = relationship(order_by="ExamVersion.version_code", cascade="all, delete-orphan")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question_bank.id"), primary_key=True)
    order_index: Mapped[int] = mapped_column(SmallInteger)
    points: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=1)
    question: Mapped[Question] = relationship()


class ExamVersion(Base):
    __tablename__ = "exam_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    version_code: Mapped[str] = mapped_column(String(10))
    items: Mapped[list["ExamVersionQuestion"]] = relationship(order_by="ExamVersionQuestion.position", cascade="all, delete-orphan")


class ExamVersionQuestion(Base):
    __tablename__ = "exam_version_questions"
    version_id: Mapped[int] = mapped_column(ForeignKey("exam_versions.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question_bank.id"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    options: Mapped[list["ExamVersionOption"]] = relationship(
        order_by="ExamVersionOption.displayed_label", cascade="all, delete-orphan",
        primaryjoin="and_(ExamVersionQuestion.version_id == foreign(ExamVersionOption.version_id), "
                    "ExamVersionQuestion.question_id == foreign(ExamVersionOption.question_id))")


class ExamVersionOption(Base):
    __tablename__ = "exam_version_options"
    version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    displayed_label: Mapped[str] = mapped_column(String(1), primary_key=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("question_options.id"))

# ---------------------------------------------------------------- G. Kết quả & báo cáo


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exam_versions.id"))
    moodle_attempt_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(10), default="moodle")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    student: Mapped[Student] = relationship()


class ItemResult(Base):
    __tablename__ = "item_level_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("question_bank.id"))
    selected_option_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question_options.id"))
    response_status: Mapped[str] = mapped_column(String(20))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    score_earned: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class ItemStatistic(Base):
    __tablename__ = "item_statistics"
    exam_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    n_students: Mapped[int] = mapped_column(Integer)
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    di_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AttemptCLOResult(Base):
    __tablename__ = "attempt_clo_results"
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"), primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), primary_key=True)
    score_earned: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    score_max: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    score_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_achieved: Mapped[bool] = mapped_column(Boolean)


class CLOResult(Base):
    __tablename__ = "clo_results"
    class_section_id: Mapped[int] = mapped_column(ForeignKey("class_sections.id"), primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), primary_key=True)
    n_evaluated: Mapped[int] = mapped_column(Integer)
    n_achieved: Mapped[int] = mapped_column(Integer)
    achieved_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_achieved: Mapped[bool] = mapped_column(Boolean)
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    improvement: Mapped[Optional[str]] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PIResult(Base):
    __tablename__ = "pi_results"
    plan_id: Mapped[int] = mapped_column(ForeignKey("pi_assessment_plans.id"), primary_key=True)
    n_evaluated: Mapped[int] = mapped_column(Integer)
    n_achieved: Mapped[int] = mapped_column(Integer)
    achieved_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_achieved: Mapped[bool] = mapped_column(Boolean)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PLOResult(Base):
    __tablename__ = "plo_results"
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id"), primary_key=True)
    academic_year: Mapped[str] = mapped_column(String(9), primary_key=True)
    n_evaluated: Mapped[int] = mapped_column(Integer)
    n_achieved: Mapped[int] = mapped_column(Integer)
    achieved_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_achieved: Mapped[bool] = mapped_column(Boolean)
    data_summary: Mapped[Optional[str]] = mapped_column(Text)
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    improvement_actions: Mapped[Optional[str]] = mapped_column(Text)
    improvement_results: Mapped[Optional[str]] = mapped_column(Text)
    evidence_tools: Mapped[Optional[str]] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LearningPath(Base):
    __tablename__ = "personalized_learning_paths"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"))
    generated_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    diagnostic_summary: Mapped[Optional[str]] = mapped_column(Text)
    recommended_study_plan: Mapped[Optional[str]] = mapped_column(Text)
    items: Mapped[list["LearningPathItem"]] = relationship(order_by="LearningPathItem.priority", cascade="all, delete-orphan")


class LearningPathItem(Base):
    __tablename__ = "learning_path_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("personalized_learning_paths.id"))
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"))
    outline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("course_outlines.id"))
    priority: Mapped[int] = mapped_column(SmallInteger)
    gap_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    clo: Mapped[CLO] = relationship()
    outline: Mapped[Optional[CourseOutline]] = relationship()


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    kind: Mapped[str] = mapped_column(String(10), default="moodle")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="running")
    n_attempts: Mapped[Optional[int]] = mapped_column(Integer)
    n_absent: Mapped[Optional[int]] = mapped_column(Integer)
    message: Mapped[Optional[str]] = mapped_column(Text)
