"""
Using redirect route instead of simple routes since it supports strict_slash
Simple route: http://webapp-improved.appspot.com/guide/routing.html#simple-routes
RedirectRoute: http://webapp-improved.appspot.com/api/webapp2_extras/routes.html#webapp2_extras.routes.RedirectRoute
"""
from webapp2_extras.routes import RedirectRoute
from bp_includes import handlers as handlers

secure_scheme = 'https'

_routes = [
    # Landing
    RedirectRoute('/', handlers.MaterializeLandingRequestHandler, name='landing', strict_slash=True),   
    RedirectRoute('/shapers/', handlers.MaterializeLandingShapersRequestHandler, name='shapers', strict_slash=True),
    RedirectRoute('/blog/', handlers.MaterializeLandingBlogRequestHandler, name='blog', strict_slash=True),
    RedirectRoute('/blog/<post_id>/', handlers.MaterializeLandingBlogPostRequestHandler, name='blog-post', strict_slash=True),
    RedirectRoute('/contact/', handlers.MaterializeLandingContactRequestHandler, name='contact', strict_slash=True),
    RedirectRoute('/faq/', handlers.MaterializeLandingFaqRequestHandler, name='faq', strict_slash=True),

    # Statics
    RedirectRoute(r'/robots.txt', handlers.RobotsHandler, name='robots', strict_slash=True),
    RedirectRoute(r'/humans.txt', handlers.HumansHandler, name='humans', strict_slash=True),
    RedirectRoute(r'/sitemap.xml', handlers.SitemapHandler, name='sitemap', strict_slash=True),
    RedirectRoute(r'/crossdomain.xml', handlers.CrossDomainHandler, name='crossdomain', strict_slash=True),

    # Blob handlers for media
    RedirectRoute('/media/serve/<kind>/<media_id>/', handlers.MediaDownloadHandler, name='media-serve', strict_slash=True),
    RedirectRoute('/blobstore/form/', handlers.BlobFormHandler, name='blob-form', strict_slash=True),
    RedirectRoute('/blobstore/upload/', handlers.BlobUploadHandler, name='blob-upload', strict_slash=True),
    RedirectRoute('/blobstore/serve/<photo_key>', handlers.BlobDownloadHandler, name='blob-serve', strict_slash=True)   
]

def get_routes():
    return _routes

def add_routes(app):
    if app.debug:
        secure_scheme = 'http'
    for r in _routes:
        app.router.add(r)
