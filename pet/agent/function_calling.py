import json

TOOLS={
'create_idea': 'Create an idea object',
'create_project':'Create a project object',
'create_task':'Create a task object',
'convert_idea_to_project':'Convert idea into project'
}

def parse_tool_call(text):
    try:
        data=json.loads(text)
        if data.get('tool') in TOOLS:
            return data
    except Exception:
        pass
    return None
