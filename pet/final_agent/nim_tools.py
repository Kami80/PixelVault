import json

TOOL_SCHEMA = [
    {
        "type":"function",
        "function":{
            "name":"create_project",
            "description":"Create a workspace project",
            "parameters":{
                "type":"object",
                "properties":{
                    "title":{"type":"string"}
                },
                "required":["title"]
            }
        }
    }
]

def parse_tool_call(response):
    if isinstance(response, dict) and "tool_calls" in response:
        return response["tool_calls"]
    return []