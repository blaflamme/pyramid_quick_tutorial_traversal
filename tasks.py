import os
import logging

from pyramid.config import Configurator
from pyramid.events import NewRequest
from pyramid.events import subscriber
from pyramid.events import ApplicationCreated
from pyramid.httpexceptions import HTTPFound
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.view import view_config

from paste.httpserver import serve
import sqlite3

logging.basicConfig()
log = logging.getLogger(__file__)

here = os.path.dirname(os.path.abspath(__file__))

class Task(dict):
    def __init__(self, data, parent):
        super(Task, self).__init__(self)
        self.update(data)
        self.__name__ = str(self['id'])
        self.__parent__ = parent

    def close(self, request):
        request.db.execute("update tasks set closed = ? where id = ?",
                          (1, self['id']))
        request.db.commit()

class TaskContainer(object):

    def __init__(self, request):
        self.db = request.db
        self.__name__ = None
        self.__parent__ = None

    def __getitem__(self, key):
        key = str(key)
        rs = self.db.execute("select * from tasks where id = ?", (key,))
        row = rs.fetchone()
        if row:
            return Task(dict(id=row[0], name=row[1], closed=row[2]), self)
        raise KeyError

    def __len__(self):
        rs = self.db.execute("select count(id) as count from tasks where closed = 0")
        return rs.fetchone()[0]

    def __iter__(self):
        rs = self.db.execute("select id, name from tasks where closed = 0")
        tasks = [dict(id=row[0], name=row[1]) for row in rs.fetchall()]
        return (Task(t, self) for t in tasks)

    def add(self, name):
        self.db.execute('insert into tasks (name, closed) values (?, ?)',
                        (name, 0))
        self.db.commit()

# views
@view_config(context=TaskContainer, renderer='list.mako')
def list_view(context, request):
    tasks = context
    return {'tasks': tasks}

@view_config(name='new', context=TaskContainer, renderer='new.mako')
def new_view(context, request):
    tasks = context
    if request.method == 'POST':
        if request.POST.get('name'):
            tasks.add(request.POST['name'])
            request.session.flash('New task was successfully added!')
            return HTTPFound(location=request.resource_url(tasks))
        else:
            request.session.flash('Please enter a name for the task!')
    return {}

@view_config(name='close', context=Task)
def close_view(context, request):
    task = context
    task.close(request)
    request.session.flash('Task was successfully closed!')
    return HTTPFound(location=request.resource_url(request.root))

@view_config(context='pyramid.exceptions.NotFound', renderer='notfound.mako')
def notfound_view(self):
    return {}

# subscribers
@subscriber(NewRequest)
def new_request_subscriber(event):
    request = event.request
    settings = request.registry.settings
    request.db = sqlite3.connect(settings['db'])
    request.add_finished_callback(close_db_connection)

def close_db_connection(request):
    request.db.close()
    
@subscriber(ApplicationCreated)
def application_created_subscriber(event):
    log.warn('Initializing database...')
    f = open(os.path.join(here, 'schema.sql'), 'r')
    stmt = f.read()
    settings = event.app.registry.settings
    db = sqlite3.connect(settings['db'])
    db.executescript(stmt)
    db.commit()
    f.close()

if __name__ == '__main__':
    # configuration settings
    settings = {}
    settings['reload_all'] = True
    settings['debug_all'] = False
    settings['mako.directories'] = os.path.join(here, 'templates')
    settings['db'] = os.path.join(here, 'tasks.db')
    # session factory
    session_factory = UnencryptedCookieSessionFactoryConfig('itsaseekreet')
    # configuration setup
    config = Configurator(settings=settings, session_factory=session_factory,
                          root_factory=TaskContainer)
    # static view setup
    config.add_static_view('static', os.path.join(here, 'static'))
    # scan for @view_config and @subscriber decorators
    config.scan()
    # serve app
    app = config.make_wsgi_app()
    serve(app, host='0.0.0.0')
