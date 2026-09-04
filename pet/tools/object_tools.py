def linked_object(kind, obj_id, title):
    return {'type':kind,'id':obj_id,'title':title,'url':f'/{kind}/{obj_id}/'}


def convert_idea_to_project(idea):
    return {'status':'proposal','source':idea,'requires_approval':True}
