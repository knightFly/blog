import orm
import xweb , time
from aiohttp import web
from model import Blog
from model import User
from apis import Page
from  apis import api
from re import compile
import apis
import model
import hashlib
import json
from config_default import configs


COOKIE_NAME = 'knight'
_COOKIE_KEY = configs['session']['secret']


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

@xweb.get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }
@xweb.get('/register')
def register():
    return {
        '__template__':'register.html'
    }


@xweb.get('/api/users')
def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = yield from User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = yield from  User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)


_RE_EAMIL = compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = compile(r'^[0-9a-f]{40}$')

@xweb.post('/api/users')
def api_register_user(*,email,name,passwd):
    if not name or not name.strip():
        raise apis.APIValueError('name')
    if not email or not _RE_EAMIL.match(email):
        raise apis.APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise apis.APIValueError('passwd')
    users = yield from model.User.findAll('email=?',[email])
    if len(users) > 0:
        raise apis.APIError('register；faild','email','email is already use')

    uid = model.next_id()
    sha1_pass = '%s%s' % (uid,passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_pass.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user,86400), max_age=86400, httponly=True)
    user.passwd = '*******'
    r.content_type = 'application/json'
    r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
    return r

@xweb.post('/api/authenticate')
def authenticate(*,email, passwd):
    if not email:
        raise apis.APIValueError('email','invalid eamil')
    if not passwd:
        raise apis.APIValueError('passwd','invalid passwd')
    users = yield from User.findAll('email=?',[email])
    if len(users) == 0:
        raise apis.APIValueError('email','email is not exist')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(passwd.encode('utf-8'))

    if user.passwd != sha1.hexdigest():
        raise apis.APIValueError('passwd','invalid passwd')
    r = web.Response()
    r.set_cookie(COOKIE_NAME,user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "******"
    r.content_type = 'application/json'
    r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
    return r


@xweb.get('/signin')
def signin():
    return {
        '__template__' : 'signin.html'
    }

@xweb.get('/manage/blogs/create')
def create_blog_get():
    return {
        '__template__' : 'blogs_create.html'
    }


@xweb.post('/manage/blogs/create')
def create_blog_post(request, *, name, summary, content):
    if check_admin(request):
        if not name or not name.strip():
            raise apis.APIValueError('name', 'name cannot be empty.')
        if not summary or not summary.strip():
            raise apis.APIValueError('summary', 'summary cannot be empty.')
        if not content or not content.strip():
            raise apis.APIValueError('content', 'content cannot be empty.')
        blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
        yield from blog.save()
        return blog
    return None


def check_admin(request):
    if request:
        user = User.find(request.__user__.id)
        return user.admin

def user2cookie(user , max_age):
    expires = str(int(time.time()) + max_age)
    s = '%s-%s-%s-%s' % (user.id,user.passwd,expires,_COOKIE_KEY)
    L = [user.id,expires,hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

