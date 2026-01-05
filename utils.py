import random
import math


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


# --- Testing functions ---

if __name__ == "__main__":
    print(f"Generated pin: {generate_pin()}")
