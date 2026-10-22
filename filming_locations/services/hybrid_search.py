"""로컬 키워드 검색과 벡터 순위의 RRF 결합. 외부 API 호출 없음."""
import math
import re
from collections import Counter

def tokens(text):
    words=re.findall(r'[가-힣a-z0-9]+',text.casefold())
    return Counter(words+[w[i:i+2] for w in words if len(w)>2 for i in range(len(w)-1)])

def lexical_rank(question,documents):
    query=tokens(question)
    vectors=[tokens(d.get('title','')+' '+d['text']) for d in documents]
    frequencies=Counter(t for v in vectors for t in v)
    average=sum(sum(v.values()) for v in vectors)/max(1,len(vectors))
    scores=[]
    for vector in vectors:
        length=sum(vector.values());score=0.
        for token in query:
            count=vector[token]
            if not count:continue
            idf=math.log(1+(len(vectors)-frequencies[token]+.5)/(frequencies[token]+.5))
            score+=idf*count*2.2/(count+1.2*(.25+.75*length/max(average,1)))
        scores.append(score)
    return [i for i in sorted(range(len(documents)),key=lambda i:(-scores[i],i)) if scores[i]>0]

def fuse(dense,lexical,limit):
    scores={}
    for ranking in (dense,lexical):
        for rank,key in enumerate(ranking,1):scores[key]=scores.get(key,0)+1/(60+rank)
    return sorted(scores,key=lambda key:(-scores[key],str(key)))[:limit]
