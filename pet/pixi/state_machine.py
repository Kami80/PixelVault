PET_STATES={
'idle':{'animation':'idle'},
'walking':{'animation':'walk'},
'working':{'animation':'work'},
'thinking':{'animation':'think'},
'celebrate':{'animation':'celebrate'},
'sleeping':{'animation':'sleep'}
}

def state_for_event(event):
    return PET_STATES.get(event, PET_STATES['idle'])
