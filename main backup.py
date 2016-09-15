import webapp2
import cgi
import jinja2
import os
from google.appengine.ext import db

# set up jinja
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True,
                               extensions = ['jinja2.ext.autoescape'])


class Blog(db.Model):
    title = db.StringProperty(required = True)
    text = db.StringProperty(required = True)
    added = db.DateTimeProperty(auto_now_add = True)


class Handler(webapp2.RequestHandler):
    """ A base RequestHandler class for our app.
        The other handlers inherit form this one.
    """

    def renderError(self, error_code):
        """ Sends an HTTP error code and a generic "oops!" message to the client. """

        self.error(error_code)
        self.response.write("Oops! Something went wrong.")


class Index(Handler):
    """ Handles requests coming in to '/' (the root of our site)
        e.g. www.build-a-blog.com/
    """

    def get(self):
        blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5")
        t = jinja_env.get_template("base.html")
        response = t.render(
                        posts = blog_posts,
                        error = self.request.get("error"))
        self.response.write(response)

class NewPost(Handler):
    """ Handles requests coming in to '/newpost'
        e.g. www.build-a-blog.com/post
    """

    def get(self):
        t = jinja_env.get_template("newpost.html")
        response = t.render(
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

        if not validBlog:
            t = jinja_env.get_template("newpost.html")
            response = t.render(
                                title = new_blog_title,
                                text = new_blog_text, 
                                error = error)
            self.response.write(response)
        else:
            # construct a blog object for the new blog post
            blog_post = Blog(title = new_blog_title, text = new_blog_text)
            blog_post.put()

            # render the confirmation message
            t = jinja_env.get_template("add-confirmation.html")
            response = t.render(blog_post = blog_post)
            self.response.write(response)

class BlogPosts(Handler):
    def get(self):

        count_all = db.GqlQuery("SELECT * FROM Blog")
        count = count_all.count()

        clicked_page = self.request.get("page")
        disp_page1 = ""
        disp_page2 = ""
        if clicked_page:    
            if clicked_page == "all":
                blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC")
                disp_page1 = "1"
                disp_page2 = str(count)
            else:
                goto_page = int(clicked_page) * 5 - 5
                blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5 OFFSET " + str(goto_page))
                if (int(clicked_page) * 5 - 5) == 0:
                    disp_page1 = "1"
                else:
                    disp_page1 = str(int(clicked_page) * 5 - 5)
                if count < (int(clicked_page) * 5):
                    disp_page2 = count
                else:
                    disp_page2 = str(int(clicked_page) * 5)
        else:
            blog_posts = db.GqlQuery("SELECT * FROM Blog ORDER BY added DESC LIMIT 5")
            disp_page1 = "1"
            disp_page2 = "5"

        add_to = 0
        if count % 5 > 0:
            add_to = 1
        page_count = int(count / 5) + add_to

        html_pages = []

        for x in range(page_count):
            html_pages.append(x + 1)

        t = jinja_env.get_template("blog.html")
        response = t.render(
                        posts = blog_posts,
                        disp_page1 = disp_page1,
                        disp_page2 = disp_page2,
                        html_pages = html_pages,
                        count = count,
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
        blog_post = Blog.get_by_id( int(id) )
        t = jinja_env.get_template("single-blog.html")
        response = t.render(
                        title = blog_post.title,
                        text = blog_post.text,
                        date = blog_post.added,
                        id = id,
                        error = self.request.get("error"))
        #response = "<html>" + str(blog_post.added) + "</html>"
        self.response.write(response)

app = webapp2.WSGIApplication([
    ('/', Index),
    ('/newpost', NewPost),
    ('/blog', BlogPosts),
    (webapp2.Route('/blog/<id:\d+>', ViewPostHandler))
], debug=True)