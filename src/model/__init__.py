from model.project import Project
from model.task import Task
from model.user import User

Models = [Project, Task, User]

for model in Models:
    model.model_rebuild()
