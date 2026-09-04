class AutonomousPetLoop:
    EVENTS = [
        "task_completed",
        "inactive_project",
        "new_idea",
        "deadline_warning",
    ]

    def process(self, event):
        return {"event": event, "handled": True}
