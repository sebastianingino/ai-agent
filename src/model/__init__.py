from .project import Project
from .task import Task
from .user import User

Models = [Project, Task, User]

for model in Models:
    model.model_rebuild()
