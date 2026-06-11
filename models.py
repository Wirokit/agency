from enum import Enum
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
    time_period: Optional[str] = ""
    description: Optional[str] = ""


class Education(BaseModel):
    degree: str
    school: Optional[str] = ""
    time_period: Optional[str] = ""
    description: Optional[str] = ""


class CV_data(BaseModel):
    id: Optional[UUID] = None
    name: str
    title: str
    profile_texts: List[str]
    skills: List[Skill]
    job_experience: List[JobExperience]
    education: List[Education]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"],
            name=data["name"],
            title=data["title"],
            profile_texts=data["profile_texts"],
            skills=[Skill(**s) for s in data["skills"]],
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


class CV_Handler(BaseModel):
    name: str
    email: str
    phone: str


class CV_Owner(BaseModel):
    id: UUID
    name: str
    title: str


class UserType(Enum):
    ADMIN = "admin"
    INTERNAL = "internal"
    EXTERNAL = "external"


def get_user_type_by_id(type_id: int):
    match type_id:
        case 1:
            return UserType.ADMIN
        case 2:
            return UserType.INTERNAL
        case 3:
            return UserType.EXTERNAL
