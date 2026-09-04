"""Final Pet Agent tool registry foundation."""

TOOLS = {}

def tool(name):
    def deco(fn):
        TOOLS[name] = fn
        return fn
    return deco

@tool('analyze_workspace')
def analyze_workspace(context=None):
    return {'status':'ready','summary':'Workspace analysis tool placeholder'}

@tool('create_idea')
def create_idea(title, description=''):
    return {'action':'create_idea','title':title,'description':description,'requires_approval':True}

@tool('convert_idea_to_project')
def convert_idea_to_project(idea_id):
    return {'action':'convert_idea_to_project','idea_id':idea_id,'requires_approval':True}
