
import subprocess
import thirtythirty.settings as TTS

def __rand(which=None, number=1):
    ret = []
    Random_Lines = subprocess.check_output([
        'rl', '--count', str(number), '%s/%s' % (TTS.COVERNAME_DB['directory'], which)])[:-1]
    for X in Random_Lines.split(','):
        ret.append( X.strip() )
    return ret

def generate():
    return {'value':'%s %s' % (__rand(TTS.COVERNAME_DB['first'])[0],
                               __rand(TTS.COVERNAME_DB['last'])[0]),}

def search(cleartext=None,
           encoded=None,
           method='metaphone',
           numResults=10,
           debug=False):
    Fields = {'Raw':0,
              'nysiis':1,
              'soundex':2,
              'metaphone':3,
              '2metaphone':4}
    
    ret = []
    Dictionary = TTS.COVERNAME_DB['first']

    Query = cleartext.upper()
    FL_Test = cleartext.upper().split(' ')
    Whole_Name = False
    if len(FL_Test) != 1:
        Dictionary = TTS.COVERNAME_DB['last']
        Query = FL_Test[-1]
        Whole_Name = True

        
    try: Find_Field = subprocess.check_output([
        'awk', '-F', ',',
        '($%s ~ "%s" && $1 ~ /%s/)' % (Fields[method]+1,
                                       encoded.upper(),
                                       Query[:2],
                                       ),
        '%s/%s' % (TTS.COVERNAME_DB['directory'], Dictionary)])[:-1]
    except: return []
    for Line in Find_Field.split('\n'):
        Raw = Line.split(',')
        if len(Raw) < Fields[method]: continue
        Name = Raw[Fields['Raw']].strip()
        Search = Raw[Fields[method]].strip()
        
        Score = 0
        if Query == Name: Score += 10
        for C in range(0, len(Query)-1):
            if debug: print C, Query, Name, len(Query), len(Name), Score
            if C >= len(Name): break
            if Query[C] == Name[C]:
                Score += 1
        if Whole_Name:
            ret.append( {'name':'%s %s' % (FL_Test[0].upper(), Name),
                         'score':Score} )
        else:
            ret.append( {'name':Name,
                         'score':Score} )
    # FIXME: if len(ret) == 0 we should do a more exhaustive search
    Z = sorted(ret, key=lambda K: K['score'])
    Z.reverse()
    return Z[:numResults]
