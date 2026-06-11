import os
from uuid import UUID
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from app.db import get_db
from models import CV_Handler, CV_Owner, CV_data

from .bedrock import extract_cv
from .utils import parse_pdf


def extract_data_from_cv(
    file: FileStorage,
):
    """
    Reads a PDF file, processes it into a CV object and returns it.
    """

    # Secure the filename (prevents directory traversal attacks)
    original_filename = secure_filename(file.filename)

    # Save the original file
    original_filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], original_filename
    )
    file.save(original_filepath)

    # Parse PDF into raw string
    pdf_data = parse_pdf(original_filepath)
    cv_data = extract_cv(pdf_data)

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    return cv_data


def _save_data_by_id(cv_id: UUID, cv: CV_data):
    db = get_db()

    with db.cursor() as cur:
        # Profile texts
        profile_data = [(cv_id, text) for text in cv.profile_texts]
        cur.executemany(
            "INSERT INTO cv_profile_texts (cv_id, profile_text) VALUES (%s, %s);",
            profile_data,
        )

        # Skills
        for skill in cv.skills:
            # Ensure the skill exists in the master table, get its ID
            cur.execute(
                """
                INSERT INTO skills (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id;
                """,
                (skill.name.strip(),),
            )
            skill_id = cur.fetchone()["id"]

            # Insert the relationship into the junction table
            cur.execute(
                """
                INSERT INTO cv_skills (cv_id, skill_id, proficiency, is_highlight)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cv_id, skill_id) DO UPDATE SET proficiency = EXCLUDED.proficiency, is_highlight = EXCLUDED.is_highlight;
                """,
                (
                    cv_id,
                    skill_id,
                    skill.proficiency,
                    skill.is_highlight,
                ),
            )

        # Job Experience
        job_data = [
            (
                cv_id,
                job.title,
                job.company_name,
                job.time_period,
                job.description,
            )
            for job in cv.job_experience
        ]
        cur.executemany(
            """
            INSERT INTO cv_job_experiences (cv_id, title, company_name, time_period, description)
            VALUES (%s, %s, %s, %s, %s);
            """,
            job_data,
        )

        # Education
        edu_data = [
            (cv_id, edu.degree, edu.school, edu.time_period, edu.description)
            for edu in cv.education
        ]
        cur.executemany(
            """
            INSERT INTO cv_educations (cv_id, degree, school, time_period, description)
            VALUES (%s, %s, %s, %s, %s);
            """,
            edu_data,
        )

        db.commit()


def replace_cv_data(cv_id: UUID, cv: CV_data):
    db = get_db()
    with db.cursor() as cur:
        # First clear all cv data from the DB
        query = """
            DELETE FROM cv_profile_texts
            WHERE cv_id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )

        query = """
            DELETE FROM cv_skills
            WHERE cv_id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )

        query = """
            DELETE FROM cv_job_experiences
            WHERE cv_id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )

        query = """
            DELETE FROM cv_educations
            WHERE cv_id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )

        # Save new data
        _save_data_by_id(cv_id, cv)


def save_cv_to_db(cv: CV_data, user_uuid: UUID, user_name: str, is_source: bool):
    new_cv_id = None

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            INSERT INTO cv (
                owner_id,
                name,
                title,
                is_source
            ) VALUES (
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id;
        """
        cur.execute(
            query,
            (user_uuid, user_name, cv.title, is_source),
        )
        new_cv_id = cur.fetchone()["id"]

        _save_data_by_id(new_cv_id, cv)

    return new_cv_id


def get_cv_data_by_id(cv_id: UUID):
    cv_data = None

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            SELECT
                c.id,
                c.name,
                c.title,

                -- 1. Aggregate Profile Texts
                (SELECT jsonb_agg(pt.profile_text)
                FROM cv_profile_texts pt
                WHERE pt.cv_id = c.id) AS profile_texts,

                -- 2. Aggregate Skills paired with their Proficiencies
                (SELECT jsonb_agg(jsonb_build_object('name', s.name, 'proficiency', cs.proficiency, 'is_highlight', cs.is_highlight))
                FROM cv_skills cs
                JOIN skills s ON cs.skill_id = s.id
                WHERE cs.cv_id = c.id) AS skills,

                -- 3. Aggregate Job Experiences as objects
                (SELECT jsonb_agg(jsonb_build_object(
                            'title', je.title,
                            'company_name', COALESCE(je.company_name, ''),
                            'time_period', je.time_period,
                            'description', je.description
                        ))
                FROM cv_job_experiences je
                WHERE je.cv_id = c.id) AS job_experience,

                -- 4. Aggregate Educations as objects
                (SELECT jsonb_agg(jsonb_build_object(
                            'degree', edu.degree,
                            'school', edu.school,
                            'time_period', edu.time_period,
                            'description', edu.description
                        ))
                FROM cv_educations edu
                WHERE edu.cv_id = c.id) AS education

            FROM cv c
            WHERE c.id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )
        cv_data = CV_data.from_dict(cur.fetchone())

    return cv_data


def get_cv_handler(cv_id: UUID):
    handler = None

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            SELECT
                handler.full_name AS name,
                handler.email AS email,
                handler.phone_num AS phone
            FROM cv
            JOIN users handler ON cv.handler_id = handler.id
            WHERE cv.id = %s
        """
        cur.execute(
            query,
            (cv_id,),
        )
        handler_data = cur.fetchone()
        if handler_data:
            handler = CV_Handler(**handler_data)

    return handler


def get_cv_owner(cv_id: UUID):
    owner = None

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            SELECT
                cv.owner_id AS id,
                owner.full_name AS name,
                owner.title AS title
            FROM cv
            JOIN users owner ON cv.owner_id = owner.id
            WHERE cv.id = %s
        """
        cur.execute(
            query,
            (cv_id,),
        )
        owner = CV_Owner(**cur.fetchone())

    return owner


def get_source_cv(user_id: UUID):
    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            SELECT id
            FROM cv
            WHERE owner_id = %s AND is_source IS TRUE
        """
        cur.execute(
            query,
            (user_id,),
        )

        cv_data = cur.fetchone()
        if cv_data:
            return get_cv_data_by_id(cv_data["id"])

    return None


def get_targeted_cvs_by_id(user_id: UUID):
    cv_list = []

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            SELECT id, job_name, date_created
            FROM cv
            WHERE owner_id = %s AND is_source IS FALSE
        """
        cur.execute(
            query,
            (user_id,),
        )

        cv_list = cur.fetchall()

    return cv_list
