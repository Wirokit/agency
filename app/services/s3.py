import boto3
from botocore.config import Config
from flask import current_app

# Debug S3
# boto3.set_stream_logger(name="botocore")


def get_s3_client():
    """Returns a boto3 client configured for production or testing."""
    endpoint_url = current_app.config.get("AWS_S3_ENDPOINT_URL")

    s3_config = Config(
        s3={"addressing_style": "path"},
        connect_timeout=3,
        retries={"max_attempts": 2},
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="eu-north-1",
        config=s3_config,
    )


def get_profile_img_url(id):
    s3_client = get_s3_client()

    bucket_name = current_app.config.get("S3_PROFILE_IMG_BUCKET")

    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": f"profile-img/{id}.png",
        },
        ExpiresIn=3600,  # URL expires in 1 hour
    )
