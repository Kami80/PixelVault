from .tools_v13 import TOOLS
from .planner import make_plan

def run_agent(message, context=None):
    plan=make_plan(message,context)
    results=[]
    for action in plan['actions']:
        results.append({'tool':action['tool'],'status':'approval_required','reason':action['reason']})
    return {'plan':plan,'results':results,'emotion':'thinking' if results else 'happy'}
