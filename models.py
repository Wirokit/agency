from enum import Enum
import json
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class Skill(BaseModel):
    name: str
    proficiency: int
    is_highlight: bool


class JobExperience(BaseModel):
    title: str
    company_name: Optional[str] = ""
    description: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_is_year: bool = False
    end_is_year: bool = False


class Education(BaseModel):
    degree: str
    school: Optional[str] = ""
    description: Optional[str] = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_is_year: bool = False
    end_is_year: bool = False


class CV_data(BaseModel):
    id: Optional[UUID] = None
    name: str = ""
    title: str = ""
    show_skill_levels: bool = True
    times_opened_by_guests: int = 0
    profile_texts: List[str] = []
    skills: List[Skill] = []
    job_experience: List[JobExperience] = []
    education: List[Education] = []

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"],
            name=data["name"],
            title=data["title"],
            show_skill_levels=data["show_skill_levels"],
            times_opened_by_guests=data["times_opened_by_guests"],
            profile_texts=data["profile_texts"] or [],
            skills=[Skill(**s) for s in data["skills"]] if data["skills"] else [],
            job_experience=(
                ([JobExperience(**j) for j in data["job_experience"]])
                if data["job_experience"]
                else []
            ),
            education=(
                ([Education(**e) for e in data["education"]])
                if data["education"]
                else []
            ),
        )

    def toJSON(self):
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "title": self.title,
                "show_skill_levels": self.show_skill_levels,
                "profile_texts": self.profile_texts,
                "skills": [vars(skill) for skill in self.skills],
                "job_experience": [
                    vars(experience) for experience in self.job_experience
                ],
                "education": [vars(education) for education in self.education],
            }
        )


class CV_Handler(BaseModel):
    name: str
    email: str
    phone: str


class CV_Owner(BaseModel):
    id: UUID
    name: str
    title: str


class AuthType(Enum):
    ALL = "all"
    ADMIN = "admin"
    INTERNAL = "internal"
    EXTERNAL = "external"


def get_user_type_by_id(type_id: int):
    match type_id:
        case 1:
            return AuthType.ADMIN
        case 2:
            return AuthType.INTERNAL
        case 3:
            return AuthType.EXTERNAL
