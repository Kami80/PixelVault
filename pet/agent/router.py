import os

MODELS={
 'default':os.getenv('PET_AGENT_MODEL','nvidia/nemotron-3.5-lightning-30b-a3b'),
 'reasoning':'z-ai/glm-5.2',
 'coding':'poolside/laguna-xs-2.1',
 'large':'nvidia/nemotron-3-ultra-550b-a55b'
}

def choose_model(intent='default'):
    return MODELS.get(intent,MODELS['default'])
