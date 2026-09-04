from workspace.models import Project, Idea, Task

class WorkspaceAdapter:
    def projects(self):
        return list(Project.objects.values("id", "title"))

    def ideas(self):
        return list(Idea.objects.values("id", "title"))

    def tasks(self):
        return list(Task.objects.values("id", "title"))
