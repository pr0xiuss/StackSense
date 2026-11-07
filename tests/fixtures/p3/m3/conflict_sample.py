# Conflicting / duplicate declarations fixture for testing ambiguous local resolution
def execute_task():
    return "first_version"


class TaskRunner:
    def execute_task(self):
        return "class_method"


def execute_task():
    # Duplicate definition in the same file scope
    return "second_version"

