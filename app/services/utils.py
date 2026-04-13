from flask_bcrypt import Bcrypt
import random
import math
import fitz

# Bcrypt for password hashing
bcrypt = Bcrypt()

# Define allowed file extensions
ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_pin():
    """
    Generates a random 6-digit pin code
    """

    digits = [i for i in range(0, 10)]

    random_str = ""

    for i in range(6):
        index = math.floor(random.random() * 10)
        random_str += str(digits[index])

    ## displaying the random string
    return random_str


def parse_pdf(file):
    """Reads a PDF file from the local server and extracts all text."""
    try:
        doc = fitz.open(file)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None
