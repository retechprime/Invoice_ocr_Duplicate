import json,os
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from backend.core.config import CONFIG_DIR

router=APIRouter(prefix='/api/dictionary',tags=['dictionary'])
PATH=os.path.join(CONFIG_DIR,'invoice_dictionary.json')

class Term(BaseModel):
    category:str
    field:str
    term:str

def load():
    with open(PATH,encoding='utf-8') as f:return json.load(f)

def save(data):
    tmp=PATH+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f: json.dump(data,f,indent=2,ensure_ascii=False)
    os.replace(tmp,PATH)

@router.get('')
def get_dictionary(): return load()

@router.post('/term')
def add_term(item:Term):
    data=load(); section=data.setdefault(item.category,{})
    values=section.setdefault(item.field,[])
    normalized=item.term.strip().lower()
    if not normalized: raise HTTPException(400,'Empty term')
    if normalized not in [str(x).strip().lower() for x in values]: values.append(item.term.strip())
    save(data); return data

@router.delete('/term')
def delete_term(item:Term):
    data=load(); values=data.get(item.category,{}).get(item.field,[])
    data[item.category][item.field]=[x for x in values if str(x).strip().lower()!=item.term.strip().lower()]
    save(data); return data
