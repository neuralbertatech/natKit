def string_to_float(string: str) -> float:
    """Safely convers a string to a float

    Parameters:
        string (str): The string to convert

    Returns:
        float: A float representation of the string if possible, 0.0 otherwise
    """
    if string == "" or string is None:
        return 0.0

    try:
        return float(string)
    except ValueError:
        return 0.0


def string_to_int(string: str) -> int:
    """Safely convers a string to an int

    Parameters:
        string (str): The string to convert

    Returns:
        int: An int representation of the string if possible, 0 otherwise
    """
    if string == "" or string is None:
        return 0

    try:
        return int(string)
    except ValueError:
        return 0
