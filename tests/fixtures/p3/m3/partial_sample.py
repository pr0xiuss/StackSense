# Intentional syntax error fixture for testing parse failure / partial parsing
def valid_function():
    return 42

def broken_syntax(
    # Unclosed parentheses and invalid tokens
    return ???

