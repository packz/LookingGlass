
def rl_generate(list_size=6, wordlist= '/usr/share/dict/american-english'):
    import subprocess
    Random_Sample = subprocess.Popen([
        'rl',
        '--count', str(list_size*5),
        wordlist], stdout=subprocess.PIPE)
    PreGrep = subprocess.check_output(['grep',
                                '--extended-regexp', "^[a-z]+$",
                                '--max-count', str(list_size),
                                ], stdin=Random_Sample.stdout)
    return PreGrep.split('\n')[:-1]

def generate(words=4):
    import random
    Minimum_Words = 4
    RND = random.SystemRandom()
    Lert = False
    try:
        words = int(words)
    except:
        words = Minimum_Words
    if words < Minimum_Words:
        words = Minimum_Words
        Lert = 'you had less than %s words - overriding' % Minimum_Words
    ret = {
        'word_count':words,
        'value':' '.join(RND.sample(rl_generate(list_size=words+1), words)),
        }
    if Lert: ret['warn'] = Lert
    return ret
