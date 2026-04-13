from uuid import UUID
from app.services.bedrock import CV_data, CV_education, CV_experience
from app.services.cv import CV, CV_settings

TEST_CV_SETTINGS = CV_settings(
    first_name_only=False,
    job_description="tester",
    extra_profile_text="A really nice person",
)

TEST_CV_EXPERIENCE_1 = CV_experience(
    title="Professional",
    company_name="Fortune 6-7",
    time_period="Yesterday - Today",
    description="Fails to Excel",
)
TEST_CV_EXPERIENCE_2 = CV_experience(
    title="Amateur",
    company_name="Life",
    time_period="Birth - Death",
    description="Having fun",
)

TEST_CV_EDUCATION_1 = CV_education(
    degree="Bachelor of Bachelors",
    school="Dating Apps",
    time_period="Way too long",
    description="Ghost",
)
TEST_CV_EDUCATION_2 = CV_education(
    degree="Primary School Diploma",
    school="Top School",
    time_period="Teen years",
    description="Angst included",
)

TEST_CV_DATA = CV_data(
    name="John Doe",
    title="Faceless Entity",
    profile_texts=["Finally,"],
    skills=["JavaScript", "React", "NotPython"],
    highlight_skills=["Jump rope", "Rock climbing"],
    job_experience=[
        TEST_CV_EXPERIENCE_1,
        TEST_CV_EXPERIENCE_2,
    ],
    education=[TEST_CV_EDUCATION_1, TEST_CV_EDUCATION_2],
)

TEST_CV = CV(
    id=UUID("52c49cb8-555a-4804-b46d-ff6d50c032da"),
    data_owner="test_owner",
    settings=TEST_CV_SETTINGS,
    cv_data=TEST_CV_DATA,
    pin_code="012345",
)
