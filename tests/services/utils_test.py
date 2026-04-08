from app.services.utils import ALLOWED_EXTENSIONS, allowed_file


def test_allowed_file():
    """Verify that allowed_file function filters correctly"""

    ALLOWED_EXTENSIONS.clear()
    ALLOWED_EXTENSIONS.add("pdf")
    ALLOWED_EXTENSIONS.add("png")

    # Test for valid inputs
    result = allowed_file("super_amazing_file.pdf")
    assert result == True
    result = allowed_file("mypic.PNG")
    assert result == True

    # Test for invalid input
    result = allowed_file("secret.virus")
    assert result == False
    result = allowed_file("hmm.pngg")
    assert result == False
