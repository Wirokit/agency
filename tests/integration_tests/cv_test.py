import io
import json
from unittest.mock import patch
from app.services.bedrock import CV_data, CV_education, CV_experience
from tests.test_data import TEST_CV


def test_cv_list(authenticated_user):
    response = authenticated_user.get("/api/cv")

    # The base test db contains 1 CV, so length of "data" should be 1
    response_data = json.loads(response.data)
    cv_list = response_data["data"]
    assert len(cv_list) == 1


def test_cv_creation_and_deletion_by_admin(authenticated_user):
    mocked_cv_data = CV_data(
        name="Mock Person",
        title="Title",
        profile_texts=["Profile"],
        skills=["Skill_1", "Skill_2"],
        highlight_skills=["Highlight_1", "Highlight_2"],
        job_experience=[],
        education=[],
    )

    with patch("app.services.bedrock._query_bedrock_for_json") as mock_bedrock:
        # Define what bedrock should return
        mock_bedrock.return_value = json.loads(mocked_cv_data.toJSON())

        fake_pdf_content = b"%PDF-1.1\n%%EOF"
        fake_file = (io.BytesIO(fake_pdf_content), "test_cv.pdf")

        response = authenticated_user.post(
            "/api/cv",
            data={
                "file": fake_file,
                "firstNameOnly": False,
                "job_description": "",
                "extra_profile_text": "",
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["success"] is True

    # Ensure that the CV is now in the db
    list_response = authenticated_user.get("/api/cv")

    # The base test db contains 1 CV, so length of "data" should now be 2
    list_response_data = json.loads(list_response.data)
    cv_list = list_response_data["data"]
    assert len(cv_list) == 2

    # Ensure that the new CV's data matches
    new_cv = cv_list[0]
    assert new_cv["data_owner"] == mocked_cv_data.name

    # Attempt to delete both CVs from the db
    delete_response = authenticated_user.delete(
        "/api/cv", data={"cvListJson": json.dumps([cv["id"] for cv in cv_list])}
    )
    assert delete_response.status_code == 200

    # Ensure that the CV table is now empty
    list_response = authenticated_user.get("/api/cv")
    list_response_data = json.loads(list_response.data)
    cv_list = list_response_data["data"]
    assert len(cv_list) == 0


def test_cv_update_by_admin(authenticated_user):
    mocked_cv_data = CV_data(
        name="New Person",
        title="Updated",
        profile_texts=["Fresh profile"],
        skills=["Skilling"],
        highlight_skills=["Highlighting"],
        job_experience=[
            CV_experience(
                title="Experiencer",
                company_name="Provider",
                time_period="Often",
                description="Much was seen. More was heard.",
            )
        ],
        education=[
            CV_education(
                degree="Student",
                school="A place of learning",
                time_period="Third semester",
                description="Time of my life",
            )
        ],
    )

    # Update CV
    response = authenticated_user.patch(
        "/api/cv-edit",
        data={
            "cv_id": str(TEST_CV.id),
            "cv_json": mocked_cv_data.toJSON(),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200

    # Get the updated CV
    response = authenticated_user.get(f"/api/cv/{str(TEST_CV.id)}")
    assert response.status_code == 200
    response_data = json.loads(response.data)
    cv_data = CV_data.fromJSON(response_data["data"]["cv_json"])

    # DB data should now match the mocked CV data
    assert cv_data == mocked_cv_data


def test_cv_update_and_deletion_by_pin_user(pin_user):
    mocked_cv_data = CV_data(
        name="Mock Person",
        title="Title",
        profile_texts=["Profile"],
        skills=["Skill_1", "Skill_2"],
        highlight_skills=["Highlight_1", "Highlight_2"],
        job_experience=[],
        education=[],
    )

    # Test CV update
    with patch("app.services.bedrock._query_bedrock_for_json") as mock_bedrock:
        # Define what bedrock should return
        mock_bedrock.return_value = json.loads(mocked_cv_data.toJSON())

        fake_pdf_content = b"%PDF-1.1\n%%EOF"
        fake_file = (io.BytesIO(fake_pdf_content), "test_cv.pdf")

        response = pin_user.patch(
            "/api/cv",
            data={
                "file": fake_file,
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["success"] is True

    # Test CV deletion
    response = pin_user.delete(
        "/api/cv",
        data={
            "cvListJson": json.dumps([str(TEST_CV.id)]),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
