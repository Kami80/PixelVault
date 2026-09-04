def project_event(project_id):
    return {"emotion": "focused", "target": project_id}

def task_event(task_id):
    return {"emotion": "working", "target": task_id}

def idea_event(idea_id):
    return {"emotion": "curious", "target": idea_id}