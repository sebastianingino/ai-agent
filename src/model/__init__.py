from model.document import EmbeddedDocument
from model.project import Project
from model.task import Task
from model.user import User

Models = [Project, Task, User, EmbeddedDocument]

for model in Models:
    model.model_rebuild()
