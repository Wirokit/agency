import io
import json
from unittest.mock import patch
from app.services.bedrock import CV_data
from models import Skill


def test_source_cv(admin_user):
    mocked_cv_data = CV_data(
        name="Mock Person",
        title="Title",
        profile_texts=["Profile"],
        skills=[
            Skill(name="Skill 1", proficiency=2, is_highlight=False),
            Skill(name="Skill 3", proficiency=5, is_highlight=True),
        ],
        job_experience=[],
        education=[],
    )

    user_id = ""
    with admin_user.session_transaction() as sess:
        user_id = sess["user_id"]

    cv_id = ""
    with patch("app.services.bedrock._query_bedrock_for_json") as mock_bedrock:
        # Define what bedrock should return
        mock_bedrock.return_value = json.loads(mocked_cv_data.toJSON())

        fake_pdf_content = b"%PDF-1.1\n%%EOF"
        fake_file = (io.BytesIO(fake_pdf_content), "test_cv.pdf")

        response = admin_user.put(
            f"/api/source-cv/{user_id}",
            data={"file": fake_file},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data["success"] is True
        cv_id = response_data["cv_id"]

    # Ensure that the CV is now in the db
    cv_response = admin_user.get(f"/api/cv/{cv_id}")
    assert cv_response.status_code == 200
    cv_response_data = json.loads(cv_response.data)
    assert cv_response_data["cv_data"]
