EMOTIONS = {
    'idle':'idle',
    'thinking':'thinking',
    'happy':'celebrate',
    'focused':'working',
    'sleepy':'sleep'
}

def emotion_for_event(event):
    return EMOTIONS.get(event,'idle')
