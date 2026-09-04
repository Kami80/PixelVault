import os
import urllib.request,json


def embed_text(text):
    key=os.getenv('NVIDIA_API_KEY')
    if not key:
        return None
    body=json.dumps({'input':text,'model':os.getenv('PET_EMBED_MODEL','nvidia/nemotron-3-embed-1b')}).encode()
    req=urllib.request.Request('https://integrate.api.nvidia.com/v1/embeddings',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read())['data'][0]['embedding']
