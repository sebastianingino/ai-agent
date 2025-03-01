from typing import Optional

from model.project import Project
from model.user import User
from actions.action import Action


class ProjectNew(Action):
    name: str
    description: Optional[str] = None

    effective = True
    unsafe = False
 
    async def preflight(self, user: User):
        return not any(p.name == self.name for p in user.projects)
        

    async def execute(self, user: User):
        project = Project(name=self.name, owner=user.id, description=self.description)
        project.members.append(user.id)
        user.projects.append(project)
        await project.save()
        await user.save()
        return True
