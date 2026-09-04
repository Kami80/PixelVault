from .router import choose_model

def make_plan(message, context=None):
    m=message.lower()
    actions=[]
    if 'project' in m or 'idea' in m:
        actions.append({'tool':'create_project','reason':'convert concept into project draft'})
    if 'task' in m or 'plan' in m:
        actions.append({'tool':'create_task','reason':'create actionable steps'})
    return {'model':choose_model(), 'actions':actions, 'context':context or {}}
