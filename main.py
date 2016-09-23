import webapp2, cgi, jinja2, os, re
from google.appengine.ext import db
from datetime import datetime
import hashutils

# set up jinja
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True,
                               extensions = ['jinja2.ext.autoescape'])

def get_posts(limit, offset):
    return db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5 OFFSET " + str(offset))

# a list of pages that anyone is allowed to visit
# (any others require logging in)
allowed_routes = [
    "/login",
    "/logout",
    "/register"
]

class User(db.Model):
    """ Represents a user on our site """
    username = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)

class Blog(db.Model):
    title = db.StringProperty(required = True)
    text = db.StringProperty(required = True)
    added = db.DateTimeProperty(auto_now_add = True)
    #owner = db.ReferenceProperty(User, required = True)
    owner = db.ReferenceProperty(User)

class Handler(webapp2.RequestHandler):
    """ A base RequestHandler class for our app.
        The other handlers inherit form this one.
    """

    def renderError(self, error_code):
        """ Sends an HTTP error code and a generic "oops!" message to the client. """
        self.error(error_code)
        self.response.write("Oops! Something went wrong.")

    def login_user(self, user):
        """ Logs in a user specified by a User object """
        user_id = user.key().id()
        self.set_secure_cookie('user_id', str(user_id))

    def logout_user(self):
        """ Logs out the current user """
        self.set_secure_cookie('user_id', '')

    def read_secure_cookie(self, name):
        """ Returns the value associated with a name in the user's cookie,
            or returns None, if no value was found or the value is not valid
        """
        cookie_val = self.request.cookies.get(name)
        if cookie_val:
            return hashutils.check_secure_val(cookie_val)

    def set_secure_cookie(self, name, val):
        """ Adds a secure name-value pair cookie to the response """
        cookie_val = hashutils.make_secure_val(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

    def initialize(self, *a, **kw):
        """ Any subclass of webapp2.RequestHandler can implement a method called 'initialize'
            to specify what should happen before handling a request.

            Here, we use it to ensure that the user is logged in.
            If not, and they try to visit a page that requires an logging in (like /ratings),
            then we redirect them to the /login page
        """
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        #self.user = uid and User.get_by_id(int(uid))
        self.user = User.get_by_id(int(uid)) if uid else None

        if not self.user and self.request.path not in allowed_routes:
            self.redirect('/login')
            return

    def get_user_by_name(self, username):
        """ Given a username, try to fetch the user from the database """
        user = db.GqlQuery("SELECT * from User WHERE username = '%s'" % username)
        if user:
            return user.get()


class Index(Handler):
    """ Handles requests coming in to '/' (the root of our site)
        e.g. www.build-a-blog.com/
    """

    def get(self):
        welcome = "Welcome to my Build-A-Blog. To get started, click New Blog Post to enter a new blog entry, or click All Blog Posts or My Blog Posts to view posts that have already been entered. Have fun!"

        uid = self.read_secure_cookie('user_id')
        user =  User.get_by_id(int(uid))

        blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5")
        t = jinja_env.get_template("base.html")
        response = t.render(
                        LoggedInUser = user.username,
                        posts = blog_posts,
                        welcome = welcome,
                        userID = user.key().id(),
                        error = self.request.get("error"))
        self.response.write(response)

class NewPost(Handler):
    """ Handles requests coming in to '/newpost'
        e.g. www.build-a-blog.com/post
    """

    def get(self):
        uid = self.read_secure_cookie('user_id')
        user =  User.get_by_id(int(uid))

        t = jinja_env.get_template("newpost.html")
        response = t.render(
                        LoggedInUser = user.username,
                        userID = user.key().id(),
                        error = self.request.get("error"))
        self.response.write(response)

    def post(self):
        new_blog_title = self.request.get("blog-title")
        new_blog_text = self.request.get("blog-text")
        validBlog = True

        # if the user typed nothing at all, redirect and yell at them
        if (not new_blog_title) or (new_blog_title.strip() == ""):
            error = "The blog post must have a title in order to submit."
            validBlog = False

        if (not new_blog_text) or (new_blog_text.strip() == ""):
            error = "The blog post must have text in order to submit."
            validBlog = False

        if ((not new_blog_title) or (new_blog_title.strip() == "")) and ((not new_blog_text) or (new_blog_text.strip() == "")):
            error = "No blog post to submit. Must enter Title and Text!"
            validBlog = False

        uid = self.read_secure_cookie('user_id')
        user =  User.get_by_id(int(uid))

        if not validBlog:
            t = jinja_env.get_template("newpost.html")
            response = t.render(
                                title = new_blog_title,
                                text = new_blog_text,
                                LoggedInUser = user.username, 
                                userID = user.key().id(),
                                error = error)
            self.response.write(response)
        else:
            # construct a blog object for the new blog post
            blog_post = Blog(title = new_blog_title, text = new_blog_text, owner = self.user)
            blog_post.put()

            # render the confirmation message
            t = jinja_env.get_template("add-confirmation.html")
            response = t.render(
                                LoggedInUser = user.username,
                                userID = user.key().id(),
                                blog_post = blog_post)
            self.response.write(response)

class BlogPosts(Handler):
    def get(self):

        myblogposts = self.request.get("user")
        if myblogposts:
            bloguserdb =  User.get_by_id(int(myblogposts))
            bloguser = bloguserdb.key()

        if myblogposts:
            #count_all = db.GqlQuery("SELECT * FROM Blog WHERE owner = " + str(bloguser))
            count_all = Blog.all().filter("owner", self.user)
        else:
            count_all = db.GqlQuery("SELECT * FROM Blog")

        count = count_all.count()

        clicked_page = self.request.get("page")
        disp_page1 = ""
        disp_page2 = ""
        next = ""
        previous = ""
        if clicked_page:    
            if clicked_page == "all":
                if myblogposts:
                    #blog_posts = db.GqlQuery("SELECT * FROM Blog WHERE owner = " + str(bloguser) + " ORDER BY added DESC")
                    blog_posts = Blog.all().filter("owner", self.user)
                else:
                    blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC")

                disp_page1 = "1"
                disp_page2 = str(count)
                previous = ""
                next = ""
            else:
                goto_page = int(clicked_page) * 5 - 5
                blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5 OFFSET " + str(goto_page))
                #blog_posts = get_posts(5, goto_page)
                if (int(clicked_page) * 5 - 5) == 0:
                    disp_page1 = "1"
                    previous = ""
                    #next = '<td><a href="/blog?page=' + str(int(clicked_page) + 1) +'">Next</a></td>'
                else:
                    disp_page1 = str(int(clicked_page) * 5 - 5)
                    previous = '<td><a href="/blog?page=' + str(int(clicked_page) - 1) +'">Previous</a></td>'
                    #next = '<td><a href="/blog?page=' + str(int(clicked_page) + 1) +'">Next</a></td>'
                if count < (int(clicked_page) * 5):
                    disp_page2 = count
                else:
                    disp_page2 = str(int(clicked_page) * 5)
        else:
            if myblogposts:
                #blog_posts = db.GqlQuery("SELECT * FROM Blog WHERE owner = " + str(self.user) + " ORDER BY added DESC LIMIT 5")
                blog_posts = Blog.all().filter("owner", self.user)
                #blog_posts = get_posts(self.user, 0)
            else:
                blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5")
                #blog_posts = Blog.all().filter("owner", self.user)

            disp_page1 = "1"
            disp_page2 = "5"
            #next = '<td><a href="/blog?page=1">Next</a></td>'

        add_to = 0
        if count % 5 > 0:
            add_to = 1
        page_count = int(count / 5) + add_to

        html_pages = []

        for x in range(page_count):
            html_pages.append(x + 1)


        if clicked_page:
            if clicked_page == "all":
                previous = ""
                next = ""
            else:
                if int(clicked_page) >= page_count:
                    #previous = '<td><a href="/blog?page=' + str(int(clicked_page) - 1) +'">Previous</a></td>'
                    previous = '<a href="/blog?page=' + str(int(clicked_page) - 1) +'">Previous</a>'
                    next = ""
                elif int(clicked_page) == 1:
                    previous = ""
                    #next = '<td><a href="/blog?page=' + str(int(clicked_page) + 1) +'">Next</a></td>'
                    next = '<a href="/blog?page=' + str(int(clicked_page) + 1) +'">Next</a>'
                else:
                    #previous = '<td><a href="/blog?page=' + str(int(clicked_page) - 1) +'">Previous</a></td>'
                    #next = '<td><a href="/blog?page=' + str(int(clicked_page) + 1) +'">Next</a></td>'
                    previous = '<a href="/blog?page=' + str(int(clicked_page) - 1) + '">Previous</a>'
                    next = '<a href="/blog?page=' + str(int(clicked_page) + 1) + '">Next</a>'
        else:
            previous = ""
            next = '<td><a href="/blog?page=2">Next</a></td>'

        uid = self.read_secure_cookie('user_id')
        user =  User.get_by_id(int(uid))

        t = jinja_env.get_template("blog.html")
        response = t.render(
                        posts = blog_posts,
                        disp_page1 = disp_page1,
                        disp_page2 = disp_page2,
                        previous = previous,
                        next = next,
                        html_pages = html_pages,
                        count = count,
                        LoggedInUser = user.username,
                        userID = user.key().id(),
                        error = self.request.get("error"))
        self.response.write(response)

    def post(self):
        #counter = self.request.get("page")
        #blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5 OFFSET 5")
        #t = jinja_env.get_template("blog.html")
        #response = t.render(
        #                posts = blog_posts,
        #                error = self.request.get("error"))
        #self.response.write(response)
        #if counter:
        #    next_counter = int(counter) + 1
        #else:
        #    next_counter = 1
        
        #self.redirect('/blog?page=' + str(next_counter))
        self.redirect('/blog')

class ViewPostHandler(Handler):
    def get(self, id):
        uid = self.read_secure_cookie('user_id')
        user =  User.get_by_id(int(uid))

        blog_post = Blog.get_by_id( int(id) )
        t = jinja_env.get_template("single-blog.html")
        response = t.render(
                        title = blog_post.title,
                        text = blog_post.text,
                        date = blog_post.added,
                        id = id,
                        Author = blog_post.owner.username,
                        userID = user.key().id(),
                        error = self.request.get("error"))
        #response = "<html>" + str(blog_post.added) + "</html>"
        self.response.write(response)

class Login(Handler):

    def render_login_form(self, error=""):
        t = jinja_env.get_template("login.html")
        response = t.render(error=error)
        self.response.write(response)

    def get(self):
        """ Display the login page """
        self.render_login_form()

    def post(self):
        """ User is trying to log in """
        submitted_username = self.request.get("username")
        submitted_password = self.request.get("password")

        user = self.get_user_by_name(submitted_username)
        if not user:
            self.render_login_form(error = "Invalid username")
        elif not hashutils.valid_pw(submitted_username, submitted_password, user.pw_hash):
            self.render_login_form(error = "Invalid password")
        else:
            self.login_user(user)
            self.redirect("/")

class Logout(Handler):

    def get(self):
        """ User is trying to log out """
        self.logout_user()
        self.redirect("/login")

class Register(Handler):

    def validate_username(self, username):
        """ Returns the username string untouched if it is valid,
            otherwise returns an empty string
        """
        USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
        if USER_RE.match(username):
            return username
        else:
            return ""

    def validate_password(self, password):
        """ Returns the password string untouched if it is valid,
            otherwise returns an empty string
        """
        PWD_RE = re.compile(r"^.{3,20}$")
        if PWD_RE.match(password):
            return password
        else:
            return ""

    def validate_verify(self, password, verify):
        """ Returns the password verification string untouched if it matches
            the password, otherwise returns an empty string
        """
        if password == verify:
            return verify

    def get(self):
        """ Display the registration page """
        t = jinja_env.get_template("register.html")
        response = t.render(errors={})
        self.response.out.write(response)

    def post(self):
        """ User is trying to register """
        submitted_username = self.request.get("username")
        submitted_password = self.request.get("password")
        submitted_verify = self.request.get("verify")

        username = self.validate_username(submitted_username)
        password = self.validate_password(submitted_password)
        verify = self.validate_verify(submitted_password, submitted_verify)

        errors = {}
        existing_user = self.get_user_by_name(username)
        has_error = False

        if existing_user:
            errors['username_error'] = "A user with that username already exists"
            has_error = True
        elif (username and password and verify):
            # create new user object
            pw_hash = hashutils.make_pw_hash(username, password)
            user = User(username=username, pw_hash=pw_hash)
            user.put()

            self.login_user(user)
        else:
            has_error = True

            if not username:
                errors['username_error'] = "That's not a valid username"

            if not password:
                errors['password_error'] = "That's not a valid password"

            if not verify:
                errors['verify_error'] = "Passwords don't match"

        if has_error:
            t = jinja_env.get_template("register.html")
            response = t.render(username=username, errors=errors)
            self.response.out.write(response)
        else:
            self.redirect('/')

app = webapp2.WSGIApplication([
    ('/', Index),
    ('/newpost', NewPost),
    ('/blog', BlogPosts),
    ('/login', Login),
    ('/logout', Logout),
    ('/register', Register),
    (webapp2.Route('/blog/<id:\d+>', ViewPostHandler)),
], debug=True)