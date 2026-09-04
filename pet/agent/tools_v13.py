from django.apps import apps


def _find(model_name, text):
    results=[]
    for model in apps.get_models():
        if model.__name__.lower()==model_name.lower():
            qs=model.objects.all()
            if hasattr(model,'title'):
                qs=qs.filter(title__icontains=text)
            elif hasattr(model,'name'):
                qs=qs.filter(name__icontains=text)
            for o in qs[:10]:
                results.append({'type':model_name.lower(),'id':o.pk,'title':getattr(o,'title',getattr(o,'name',str(o)))})
    return results


def search_objects(query):
    return {'objects': _find('Project',query)+_find('Idea',query)+_find('Task',query)}


def create_draft(kind, data):
    return {'requires_approval':True,'action':'create_'+kind,'payload':data}

TOOLS={
    'search_objects': search_objects,
    'create_project': lambda data:create_draft('project',data),
    'create_task': lambda data:create_draft('task',data),
    'create_idea': lambda data:create_draft('idea',data),
}
