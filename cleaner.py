import sched
import time
import psycopg2
from psycopg2 import sql

DATABASE_URL = os.environ['DATABASE_URL']
s = sched.scheduler(time.time, time.sleep)
def timer(sc): 
	currtime = int(time.time())
  conn = psycopg2.connect(DATABASE_URL, sslmode='require')
  cursor = conn.cursor()
  values = (currtime,)
  insert = 'DELETE FROM questions WHERE created < %s - 86400'
	cursor.execute(insert,values)
  conn.commit()
  cursor.close()
  conn.close()
  s.enter(60, 1, timer, (sc,))

s.enter(86400, 1, timer, (s,))
s.run()
