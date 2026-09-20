import json
import numpy as np
from paddleocr import PaddleOCR

class PaddleEngine:
    def __init__(self): self.ocr=PaddleOCR(lang='en')
    @staticmethod
    def safe(v):
        if isinstance(v,np.ndarray): return v.tolist()
        if isinstance(v,(np.integer,np.floating)): return v.item()
        if isinstance(v,dict): return {k:PaddleEngine.safe(x) for k,x in v.items()}
        if isinstance(v,list): return [PaddleEngine.safe(x) for x in v]
        return v
    def predict(self,path):
        results=self.ocr.predict(path); blocks=[]
        for res in results or []:
            data=res.json() if hasattr(res,'json') and callable(res.json) else (res.json if hasattr(res,'json') else res)
            if isinstance(data,str):
                try:data=json.loads(data)
                except: data={}
            payload=data.get('res',data) if isinstance(data,dict) else {}
            texts=payload.get('rec_texts',[]); scores=payload.get('rec_scores',[]); boxes=payload.get('rec_boxes',[])
            for i,text in enumerate(texts): blocks.append({'block_id':len(blocks),'block_order':len(blocks),'label':'text','text':str(text),'confidence':float(scores[i]) if i<len(scores) else None,'bbox':self.safe(boxes[i]) if i<len(boxes) else []})
        return blocks
