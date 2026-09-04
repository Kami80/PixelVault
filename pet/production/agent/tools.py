class PetTools:
    def __init__(self, adapter):
        self.adapter = adapter

    def search_projects(self):
        return self.adapter.projects()

    def search_ideas(self):
        return self.adapter.ideas()

    def search_tasks(self):
        return self.adapter.tasks()

    def create_project_from_idea(self, idea_id):
        return {"action": "create_project_from_idea", "idea_id": idea_id, "requires_approval": True}
