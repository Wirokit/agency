from dataclasses import dataclass
import json


@dataclass
class CV_experience:
    title: str
    company_name: str
    time_period: str
    description: str

    def fromJSON(json):
        return CV_experience(
            title=json["title"],
            company_name=json["company_name"],
            time_period=json["time_period"],
            description=json["description"],
        )


@dataclass
class CV_education:
    degree: str
    school: str
    time_period: str
    description: str

    def fromJSON(json):
        return CV_education(
            degree=json["degree"],
            school=json["school"],
            time_period=json["time_period"],
            description=json["description"],
        )


@dataclass
class CV_data:
    name: str
    title: str
    profile_texts: list[str]
    skills: list[str]
    highlight_skills: list[str]
    job_experience: list[CV_experience]
    education: list[CV_education]

    def toJSON(self):
        return json.dumps(
            {
                "name": self.name,
                "title": self.title,
                "profile_texts": self.profile_texts,
                "skills": self.skills,
                "highlight_skills": self.highlight_skills,
                "job_experience": [
                    vars(experience) for experience in self.job_experience
                ],
                "education": [vars(education) for education in self.education],
            },
            ensure_ascii=False,
        )

    def fromJSON(json):
        return CV_data(
            name=json["name"],
            title=json["title"],
            profile_texts=json["profile_texts"],
            skills=json["skills"],
            highlight_skills=json["highlight_skills"],
            job_experience=[
                CV_experience.fromJSON(experience)
                for experience in json["job_experience"]
            ],
            education=[
                CV_education.fromJSON(education) for education in json["education"]
            ],
        )
