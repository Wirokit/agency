import io
import json
from unittest.mock import patch
from app.services.bedrock import CV_data


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
        assert response_data["success"] == True

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
        assert response_data["success"] == True

    # Test CV deletion
    with pin_user.session_transaction() as sess:
        response = pin_user.delete(
            "/api/cv",
            data={
                "cvListJson": json.dumps([sess["cv_id"]]),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
