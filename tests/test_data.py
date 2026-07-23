from models import CV_data, JobExperience, Education, Skill

TEST_PROFILES = ["Finally,", "A working test"]

TEST_SKILLS = [
    Skill(
        name="Charisma",
        proficiency=4,
        is_highlight=True,
    ),
    Skill(
        name="Wisdom",
        proficiency=2,
        is_highlight=True,
    ),
    Skill(
        name="Strength",
        proficiency=1,
        is_highlight=False,
    ),
]

TEST_EXPERIENCE = [
    JobExperience(
        title="Professional",
        company_name="Fortune 6-7",
        time_period="Yesterday - Today",
        description="Fails to Excel",
    ),
    JobExperience(
        title="Amateur",
        company_name="Life",
        time_period="Birth - Death",
        description="Having fun",
    ),
]

TEST_EDUCATION = [
    Education(
        degree="Bachelor of Bachelors",
        school="Dating Apps",
        time_period="Way too long",
        description="Ghost",
    ),
    Education(
        degree="Primary School Diploma",
        school="Top School",
        time_period="Teen years",
        description="Angst included",
    ),
]

TEST_CV_DATA = CV_data(
    id="4d05812b-eaec-4110-8310-71d3e74ddce6",
    name="John Doe",
    title="Faceless Entity",
    show_skill_levels=True,
    profile_texts=TEST_PROFILES,
    skills=TEST_SKILLS,
    job_experience=TEST_EXPERIENCE,
    education=TEST_EDUCATION,
)

TEST_ADMIN = {
    "id": "daae7e07-173a-4849-a6ba-5932ab43d942",
    "user_type_id": 1,
    "username": "admin",
    "is_disabled": False,
    "password_hash": "",
    "require_pw_update": False,
    "full_name": "Admin User",
    "title": "Arbitrator of Authority",
    "office": "The Matrix",
    "email": "admin@test.com",
    "phone_num": "0123456789",
    "pin_code": None,
}


def setup_database(app):
    """Helper to fill the testing db"""
    from app.db import get_db

    with app.app_context():
        db = get_db()
        with db, db.cursor() as cur:
            query = """
                INSERT INTO users (
                    id,
                    username,
                    is_disabled,
                    password_hash,
                    require_pw_update,
                    full_name,
                    title,
                    office,
                    user_type_id,
                    phone_num,
                    email,
                    pin_code
                ) VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """

            cur.execute(
                query,
                (
                    TEST_ADMIN["id"],
                    TEST_ADMIN["username"],
                    TEST_ADMIN["is_disabled"],
                    TEST_ADMIN["password_hash"],
                    TEST_ADMIN["require_pw_update"],
                    TEST_ADMIN["full_name"],
                    TEST_ADMIN["title"],
                    TEST_ADMIN["office"],
                    TEST_ADMIN["user_type_id"],
                    TEST_ADMIN["phone_num"],
                    TEST_ADMIN["email"],
                    TEST_ADMIN["pin_code"],
                ),
            )
            db.commit()
