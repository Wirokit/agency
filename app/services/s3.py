import os
import boto3
from botocore.config import Config

S3_PROFILE_IMG_BUCKET = os.environ.get("S3_PROFILE_IMG_BUCKET")

# Debug S3
# boto3.set_stream_logger(name="botocore")


def get_s3_client():
    return boto3.client(
        "s3",
        config=Config(signature_version="s3v4"),
        region_name="eu-north-1",
        endpoint_url="https://s3.eu-north-1.amazonaws.com",
    )


def get_profile_img_url(id):
    s3_client = get_s3_client()

    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": S3_PROFILE_IMG_BUCKET,
            "Key": f"profile-img/{id}.png",
        },
        ExpiresIn=3600,  # URL expires in 1 hour
    )
