#! /usr/bin/python

import Milter
import StringIO
import time
import email
import sys
import sqlite3
import logging

import os.path
from os import chmod

from hashcash import check, mint
from re import sub

from socket import AF_INET, AF_INET6
from Milter.utils import parse_addr
if True:
  from multiprocessing import Process as Thread, Queue
else:
  from threading import Thread
  from Queue import Queue


def read_settings_py():
  """
  Using a bit of hackery, get the HASHCASH['BITS'] setting for MILTER
  """
  Settings = '/home/pi/thirtythirty/thirtythirty/settings.py'
  Locals = {'__file__':Settings}
  execfile(Settings, Locals)
  return Locals['HASHCASH']['BITS']['MILTER']

REQUIRED_BITS = read_settings_py()


logq = Queue(maxsize=4)
logging.basicConfig(filename='/tmp/milter.log', level=logging.DEBUG)

Doublespend_DB = '/var/spool/postfix/hashcash-milter/hashcash.db'
Socket = '/var/spool/postfix/hashcash-milter/hashcash.sock'
Expiration_Days = 7

IP_Mode_List = {
  '127.0.0.1':'out',     # local processes sending mail out - interface lo
  '192.168.10.1':'in',   # tor servers sending mail in      - interface lo:1
  }

def create_db():
  DB = sqlite3.connect(Doublespend_DB,
                       detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
  C = DB.cursor()
  C.execute("""
  CREATE TABLE spent(id integer primary key autoincrement not null,
  hashcash text not null,
  timestamp datetime default current_timestamp not null);
  """)
  DB.commit()

if not os.path.exists(Doublespend_DB):
  create_db()

class myMilter(Milter.Base):

  def __init__(self):  # A new instance with each new connection.
    self.id = Milter.uniqueID()  # Integer incremented with each call.

  # each connection runs in its own thread and has its own myMilter
  # instance.  Python code must be thread safe.  This is trivial if only stuff
  # in myMilter instances is referenced.
  @Milter.noreply
  def connect(self, IPname, family, hostaddr):
    self.IP = hostaddr[0]
    self.port = hostaddr[1]
    
    if family == AF_INET6:
      self.flow = hostaddr[2]
      self.scope = hostaddr[3]
    else:
      self.flow = None
      self.scope = None
    self.IPname = IPname  # Name from a reverse IP lookup
    self.H = None
    self.fp = None
    self.receiver = self.getsymval('j')

    self.hashcash_val = None
    self.hashcash_pass = False
    self.hashcash_mode = 'in'
    for M in IP_Mode_List.keys():
      if M == self.IP:
        self.hashcash_mode = IP_Mode_List[M]
    self.doublespend_cleanup()
    self.log("connect from %s [%s]" % (IPname, self.IP) )
    
    return Milter.CONTINUE


  def hello(self, heloname):
    self.H = heloname
    self.log("HELO %s" % heloname)
    # FIXME: check HELO vs list of legal servers
    return Milter.CONTINUE

  def envfrom(self, mailfrom, *str):
    self.F = mailfrom
    self.R = []  # list of recipients
    self.fromparms = Milter.dictfromlist(str)	# ESMTP parms
    self.user = self.getsymval('{auth_authen}')	# authenticated user
    self.log("mail from:", mailfrom, *str)
    self.fp = StringIO.StringIO()
    self.canon_from = '@'.join(parse_addr(mailfrom))
    self.fp.write('From %s %s\n' % (self.canon_from,time.ctime()))
    return Milter.CONTINUE

  @Milter.noreply
  def envrcpt(self, to, *str):
    rcptinfo = to,Milter.dictfromlist(str)
    self.R.append(rcptinfo)
    
    return Milter.CONTINUE

  @Milter.noreply
  def header(self, name, hval):
    self.fp.write("%s: %s\n" % (name,hval))	# add header to buffer
    if name == 'X-Hashcash':
      self.hashcash_val = hval
      if self.hashcash_mode == 'in':
        # FIXME: whine whine whine - multiple recipients
        First_Mailto = sub('[<>]', '', self.R[0][0])
        # FIXME: we should probably parse out the sender's fingerprint here and see if we even want their mail.
        self.hashcash_pass = check(stamp=self.hashcash_val,
                                   resource=First_Mailto,
                                   check_expiration=60 * 60 * 24 * Expiration_Days, # in seconds
                                   bits=REQUIRED_BITS,
                                   )
        logging.debug("%s Hashcash for %s [%s]" % (
          time.strftime('%Y%b%d %H:%M:%S'),
          First_Mailto,
          self.hashcash_pass
          ))
        if self.hashcash_pass is True:
          # just an insert as we can't Milter.REJECT yet
          self.doublespend_insert(self.hashcash_val)
    return Milter.CONTINUE

  def doublespend_insert(self, hc=None):
    doublespend_db = sqlite3.connect(Doublespend_DB,
                                     detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = doublespend_db.cursor()
    cursor.execute('insert into spent(hashcash) values (?);',
                   (hc,))
    doublespend_db.commit()

  def doublespend_cleanup(self, days=Expiration_Days):
    doublespend_db = sqlite3.connect(Doublespend_DB,
                                     detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = doublespend_db.cursor()
    cursor.execute("""
                  delete
                  from spent
                  where
                  spent.timestamp < datetime('now', ?);
                  """, ('-%s days' % days,)) # ugly, but tenable
    doublespend_db.commit()

  @Milter.noreply
  def eoh(self):
    self.fp.write("\n")
    return Milter.CONTINUE

  @Milter.noreply
  def body(self, chunk):
    self.fp.write(chunk)
    return Milter.CONTINUE

  def eom(self):
    if ((self.hashcash_pass is not True) and (self.hashcash_mode == 'in')):
      self.setreply('550','5.7.1','Hashcash required for this MX')
      return Milter.REJECT
    if self.hashcash_mode == 'in':
        doublespend_db = sqlite3.connect(Doublespend_DB,
                                         detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        cursor = doublespend_db.cursor()
        cursor.execute("""
        select timestamp as "[timestamp]"
        from spent
        where hashcash = ?
        order by timestamp desc;
        """, (self.hashcash_val,))
        Rows = cursor.fetchall()
        if len(Rows) != 1:
          self.setreply(
            '550',
            '5.7.1',
            'You are double-spending.  Generate another.')
          logging.debug("%s Hashcash double-spend %s" % (time.strftime('%Y%b%d %H:%M:%S'), Rows[1][0]))
          return Milter.REJECT
        else:
          self.addheader('Authentication-Results', 'Pass')
    elif self.hashcash_mode == 'out':
      # FIXME: whine whine whine - multiple recipients
      First_Mailto = sub('[<>]', '', self.R[0][0])
      logging.debug("%s Generating Hashcash - embrace the suck." % (time.strftime('%Y%b%d %H:%M:%S')))
      # FIXME: mint() takes `ext` as an arg - that should be the fingerprint of the sender probably
      HC = mint(First_Mailto,
                stamp_seconds=True,
                bits=REQUIRED_BITS)
      logging.debug("%s Hashcash generated for `%s`" % (time.strftime('%Y%b%d %H:%M:%S'), First_Mailto))
      # belt and suspenders
      self.doublespend_insert(HC)
      if self.hashcash_val is None:
        self.addheader('X-Hashcash', HC)
      else:
        self.chgheader('X-Hashcash', 1, HC)
    else:
      # DANGER DANGER
      return Milter.TEMPFAIL
    self.fp.seek(0)
    msg = email.message_from_file(self.fp)
    return Milter.ACCEPT

  def close(self):
    # always called, even when abort is called.  Clean up
    # any external resources here.
    return Milter.CONTINUE

  def abort(self):
    # client disconnected prematurely
    return Milter.CONTINUE

  ## === Support Functions ===

  def log(self,*msg):
    logq.put((msg,self.id,time.time()))

def background():
  while True:
    t = logq.get()
    if not t: break
    msg,id,ts = t
    logging.info("%s [%d]" % (time.strftime('%Y%b%d %H:%M:%S',time.localtime(ts)),id))
    for i in msg: logging.info(i)

## ===
    
def main():
  bt = Thread(target=background)
  bt.start()
  socketname = Socket
  timeout = 600
  Milter.factory = myMilter
  flags = Milter.ADDHDRS + Milter.CHGHDRS
  Milter.set_flags(flags)
  logging.info("%s milter startup" % time.strftime('%Y%b%d %H:%M:%S'))
  Milter.runmilter("pythonfilter", socketname, timeout)
  logq.put(None)
  bt.join()
  logging.info("%s bms milter shutdown" % time.strftime('%Y%b%d %H:%M:%S'))

if __name__ == "__main__":
  # daemonize --- sloppily.
  import os
  import sys
  pid = os.fork()
  if pid > 0:
    sys.exit(0)
    
  pid = os.fork()
  if pid > 0:
    sys.exit(0)

  main()
