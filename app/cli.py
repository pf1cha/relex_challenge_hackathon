import argparse
import getpass
from . import store
from .main import password_hash
parser=argparse.ArgumentParser();parser.add_argument('command',choices=['user','project']);parser.add_argument('name');parser.add_argument('--admin');args=parser.parse_args()
store.initialize()
with store.transaction() as c:
    if args.command=='user':
        password=getpass.getpass('Password: ')
        if len(password)<10:raise SystemExit('Use at least 10 characters')
        c.execute('INSERT INTO users VALUES(%s,%s,%s)',(store.uid(),args.name,password_hash(password)))
        print('Account created')
    else:
        u=c.execute('SELECT id FROM users WHERE username=%s',(args.admin,)).fetchone()
        if not u:raise SystemExit('Specify existing --admin username')
        p=store.uid();c.execute('INSERT INTO projects(id,name) VALUES(%s,%s)',(p,args.name));c.execute('INSERT INTO memberships VALUES(%s,%s,%s)',(p,u['id'],'admin'));print(p)
