from sqlalchemy.orm.session import Session
from werkzeug.local import Local

local = Local()
session: Session = local('session')
peer = local('peer')
user = local('user')
