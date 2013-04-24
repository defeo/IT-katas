import webapp2
from webapp2 import WSGIApplication, Route, RequestHandler
from webapp2_extras import jinja2
import yaml
import logging
from google.appengine.api import urlfetch
import xml.etree.ElementTree as ET
from almost_secure_cookie import with_session
from urlparse import urlparse
from os.path import join, dirname
from os import environ
from Crypto import Random
import base64

# config
try:
    secret = base64.b64encode(Random.new().read(15))
    logging.info('Using secret: ' + secret)
except:
    logging.warn("Using Pulcinella's secret.")
    secret = "Pulcinella's"

config = {
    'cas_host': 'https://cas-dev.uvsq.fr',
    'bosses': ['lucadefe@cas-dev.uvsq.fr'],
    'secret':  secret
    }

try:
    config.update(yaml.load(open('config.yaml', 'r')))
except IOError:
    pass


# Template engine
class TemplateHandler(RequestHandler):
    @webapp2.cached_property
    def jinja2(self):
        return jinja2.get_jinja2(app=self.app)

    def cnr(self, view, **context):
        self.response.write(self.jinja2.render_template(view, **context))
        

# Authentication management
class User(object):
    """
    User model
    """
    def __init__(self, name, domain=None):
        self.name = name
        self.domain = domain
        self.is_boss = (self.__repr__()
                        in webapp2.get_app().config['bosses'])

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__() + ('' if self.domain is None else '@' + self.domain )

def loggedin(meth):
    """
    Decorator granting access to a handler method only if the user is logged in
    """
    def wrapper(self, *args, **kw):
        user = self.session.get('user')
        if user:
            self.request.registry['user'] = User(**user)
            return meth(self, *args, **kw)
        else:
            return self.redirect_to('login', path=self.request.path)
    return with_session(wrapper)

class Login(TemplateHandler):
    """
    This handles logins using a CAS 2.0 SSO server (such as cas-dev.uvsq.fr)
    """

    @with_session
    def get(self, path='/'):
        cas_host = self.app.config['cas_host']
        domain = urlparse(cas_host).netloc
        service = (self.app.config.get('cas_service')
                   or self.req.host_url) + self.uri_for('login', path=path)
    
        ticket = self.request.GET.get('ticket')
        if ticket:
            url =  '%s/serviceValidate?service=%s&ticket=%s' % (cas_host, service, ticket)
            root = ET.fromstring(urlfetch.fetch(url, validate_certificate=True).content)
            if root[0].tag.rfind('authenticationSuccess') >= 0:
                self.session['user'] = {
                    'name' : root[0][0].text,
                    'domain': domain
                    }
                self.redirect(path)

        self.cnr('login.html', title='Login',
                 cas_host=cas_host, service=service)

class Logout(RequestHandler):
    """
    Logs out (it only erases user information from the session cookie,
    the user can keep logging in with an old cookie)
    """

    @loggedin
    def get(self):
        del self.request.registry['user']
        del self.session['user']
        self.response
        self.redirect('/login')


# Individual Katas
import vigenere

class Index(RequestHandler):
    @loggedin
    def get(self):
        self.response.write('Hello, %s' % self.request.registry['user'])


# Build the app
routes = [
    Route('/', Index),
    Route('/login', Login),
    Route('/login<path:/.*>', Login, name='login'),
    Route('/logout', Logout),
    Route('/vigenere', vigenere.Vigenere, vigenere.Vigenere.__name__),
    Route('/vigenere/download', vigenere.VigenereDownload),    
    ]
app = WSGIApplication(routes,
                      debug=environ.get('SERVER_SOFTWARE').startswith('Dev'),
                      config=config)

