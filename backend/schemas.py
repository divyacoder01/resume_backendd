from pydantic import BaseModel, Field


class Experience(BaseModel):
    title: str
    company: str
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str
    institution: str
    year: str = ""
    details: str = ""


class Project(BaseModel):
    name: str
    description: str = ""
    bullets: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    """Tailored resume. Also used as part of the Gemini response schema."""

    name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class CustomizeResult(BaseModel):
    """What Gemini must return, and what POST /customize responds with."""

    resume: Resume
    changes: list[str] = Field(
        description="Short notes on what was tailored and why."
    )
    match_keywords: list[str] = Field(
        description="Job-description keywords the tailored resume covers."
    )
