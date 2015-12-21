# -*- coding: utf-8 -*-
"""
    A real simple app for using webapp2 with auth and session.

    Routes are setup in routes.py and added in main.py
"""
# python imports
import logging
import json
import requests
from datetime import date, timedelta
import time

# appengine imports
import webapp2
from webapp2_extras import security
from webapp2_extras.auth import InvalidAuthIdError, InvalidPasswordError
from webapp2_extras.i18n import gettext as _
from webapp2_extras.appengine.auth.models import Unique
from google.appengine.ext import ndb, blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import taskqueue, users, images
from google.appengine.api.datastore_errors import BadValueError
from google.appengine.runtime import apiproxy_errors

# local imports
import models, messages, forms
from github import github
from linkedin import linkedin
from lib import utils, captcha, twitter, facebook, bitly, myhtmlparser
from lib.cartodb import CartoDBAPIKey, CartoDBException
from lib.basehandler import BaseHandler
from lib.decorators import user_required, taskqueue_method



def captchaBase(self):
    if self.app.config.get('captcha_public_key') == "" or \
                    self.app.config.get('captcha_private_key') == "":
        chtml = '<div class="alert alert-danger"><strong>Error</strong>: You have to ' \
                '<a href="http://www.google.com/recaptcha/" target="_blank">sign up ' \
                'for API keys</a> in order to use reCAPTCHA.</div>' \
                '<input type="hidden" name="recaptcha_challenge_field" value="manual_challenge" />' \
                '<input type="hidden" name="recaptcha_response_field" value="manual_challenge" />'
    else:
        chtml = captcha.displayhtml(public_key=self.app.config.get('captcha_public_key'))
    return chtml


""" MATERIALIZE handlers 

    These handlers are the core of the Platform, they give life to main user materialized screens

"""
# LANDING
class MaterializeLandingRequestHandler(BaseHandler):
    """
    Handler to show the landing page
    """

    def get(self):
        """ Returns a simple HTML form for landing """
        params = {}
        params['captchahtml'] = captchaBase(self)
        shapers = models.Shapers.query()
        params['shapers'] = []
        for shaper in shapers:
            params['shapers'].append((shaper.name, shaper.image))

        return self.render_template('materialize/landing/base.html', **params)

class MaterializeLandingShapersRequestHandler(BaseHandler):
    """
        Handler for materialized privacy policy
    """
    def get(self):
        """ returns simple html for a get request """
        params = {}        
        shapers = models.Shapers.query()
        params['total'] = shapers.count()
        params['shapers'] = []
        for shaper in shapers:
            params['shapers'].append((shaper.name, shaper.birth.strftime("%Y-%m-%d"), shaper.email, shaper.twitter, shaper.linkedin, shaper.image, shaper.bio))
        return self.render_template('materialize/landing/shapers.html', **params)

class MaterializeLandingBlogRequestHandler(BaseHandler):
    """
        Handler for materialized privacy policy
    """
    def get(self):
        """ returns simple html for a get request """
        params = {}        
        params['captchahtml'] = captchaBase(self)
        posts = models.BlogPost.query()
        params['total'] = posts.count()
        params['posts'] = []
        for post in posts:
            categories = ""
            for category in post.category:
                categories += str(category) + ", "
            params['posts'].append((post.key.id(), post.updated.strftime("%Y-%m-%d"), post.title, post.subtitle, post.blob_key, post.author, post.brief, categories[0:-2]))
        return self.render_template('materialize/landing/blog.html', **params)

class MaterializeLandingBlogPostRequestHandler(BaseHandler):
    """
        Handler for materialized privacy policy
    """
    def get(self, post_id):
        """ returns simple html for a get request """
        params = {} 
        params['captchahtml'] = captchaBase(self)
        blog = models.BlogPost.get_by_id(long(post_id))
        if blog is not None:
            params['title'] = blog.title
            params['subtitle'] = blog.subtitle
            params['blob_key'] = blog.blob_key
            params['author'] = blog.author
            params['content'] = blog.content
            return self.render_template('materialize/landing/blogpost.html', **params)
        else:
            return self.error(404)

class MaterializeLandingFaqRequestHandler(BaseHandler):
    """
        Handler for materialized frequented asked questions
    """
    def get(self):
        """ returns simple html for a get request """
        params = {} 
        params['captchahtml'] = captchaBase(self)
        return self.render_template('materialize/landing/faq.html', **params)

class MaterializeLandingLicenseRequestHandler(BaseHandler):
    """
        Handler for materialized privacy policy
    """
    def get(self):
        """ returns simple html for a get request """
        params = {} 
        params['captchahtml'] = captchaBase(self)
        return self.render_template('materialize/landing/license.html', **params)

class MaterializeLandingContactRequestHandler(BaseHandler):
    """
        Handler for materialized contact us
    """
    def get(self):
        """ returns simple html for a get request """
        params = {} 
        params['captchahtml'] = captchaBase(self)
        params['exception'] = self.request.get('exception')

        params['t'] = str(self.request.get('t')) if len(self.request.get('t')) > 1 else 'no'

        return self.render_template('materialize/landing/contact.html', **params)

    def post(self):
        """ validate contact form """
        if not self.form.validate():
            _message = _(messages.post_error)
            self.add_message(_message, 'danger')
            return self.get()

        import bp_includes.lib.i18n as i18n
        from bp_includes.external import httpagentparser

        remote_ip = self.request.remote_addr
        city = i18n.get_city_code(self.request)
        region = i18n.get_region_code(self.request)
        country = i18n.get_country_code(self.request)
        coordinates = i18n.get_city_lat_long(self.request)
        user_agent = self.request.user_agent
        exception = self.request.POST.get('exception')
        name = self.form.name.data.strip()
        email = self.form.email.data.lower()
        message = self.form.message.data.strip()
        template_val = {
            "name": name,
            "email": email,
            "ip": remote_ip,
            "city": city,
            "region": region,
            "country": country,
            "coordinates": coordinates,
            "message": message
        }
        try:
            # parsing user_agent and getting which os key to use
            # windows uses 'os' while other os use 'flavor'
            ua = httpagentparser.detect(user_agent)
            _os = ua.has_key('flavor') and 'flavor' or 'os'

            operating_system = str(ua[_os]['name']) if "name" in ua[_os] else "-"
            if 'version' in ua[_os]:
                operating_system += ' ' + str(ua[_os]['version'])
            if 'dist' in ua:
                operating_system += ' ' + str(ua['dist'])

            browser = str(ua['browser']['name']) if 'browser' in ua else "-"
            browser_version = str(ua['browser']['version']) if 'browser' in ua else "-"

            template_val = {
                "name": name,
                "email": email,
                "ip": remote_ip,
                "city": city,
                "region": region,
                "country": country,
                "coordinates": coordinates,

                "browser": browser,
                "browser_version": browser_version,
                "operating_system": operating_system,
                "message": message
            }
        except Exception as e:
            logging.error("error getting user agent info: %s" % e)

        try:
            subject = _("Alguien ha enviado un mensaje")
            # exceptions for error pages that redirect to contact
            if exception != "":
                subject = "{} (Exception error: {})".format(subject, exception)

            body_path = "emails/contact.txt"
            body = self.jinja2.render_template(body_path, **template_val)

            email_url = self.uri_for('taskqueue-send-email')
            taskqueue.add(url=email_url, params={
                'to': self.app.config.get('contact_recipient'),
                'subject': subject,
                'body': body,
                'sender': self.app.config.get('contact_sender'),
            })

            message = _(messages.contact_success)
            self.add_message(message, 'success')
            return self.redirect_to('contact')

        except (AttributeError, KeyError), e:
            logging.error('Error sending contact form: %s' % e)
            message = _(messages.post_error)
            self.add_message(message, 'danger')
            return self.redirect_to('contact')

    @webapp2.cached_property
    def form(self):
        return forms.ContactForm(self)


""" SMALL MEDIA handlers

    These handlers are used to serve small media files from datastore

"""
class MediaDownloadHandler(BaseHandler):
    """
    Handler for Serve Vendor's Logo
    """
    def get(self, kind, media_id):
        """ Handles download"""

        params = {}

        if kind == 'profile':
            user_info = self.user_model.get_by_id(long(media_id))        
            if user_info != None:
                if user_info.picture != None:
                    self.response.headers['Content-Type'] = 'image/png'
                    self.response.out.write(user_info.picture)


        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('No image')




""" BIG MEDIA handlers

    These handlers operate files larger than the 1Mb, upload and serve.

"""
class BlobFormHandler(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):
    """
        To better handle text inputs included in same file form, please refer to bp_admin/blog.py
    """
    def get(self):
        upload_url = blobstore.create_upload_url('/blobstore/upload/')
        self.response.out.write('<html><body>')
        self.response.out.write('<form action="%s" method="POST" enctype="multipart/form-data">' % upload_url)
        self.response.out.write('''Upload File: <input type="file" name="file"><br> <input type="submit"
            name="submit" value="Submit"> <input type="hidden" name="_csrf_token" value="%s"> </form></body></html>''' % self.session.get('_csrf_token'))

class BlobUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            upload = self.get_uploads()[0]
            user_photo = models.Media(blob_key=upload.key())
            #photo_url = images.get_serving_url(upload.key())
            user_photo.put()
            self.redirect('/blobstore/serve/%s' % upload.key())
        except:
            self.error(404)

class BlobDownloadHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key)




""" CRONJOB + TASKQUEUE handlers

    These handlers obey to cron.yaml in order to produce recurrent, autonomous tasks

"""
class WelcomeCronjobHandler(BaseHandler):
    def get(self):
        welcome_url = self.uri_for('taskqueue-welcome')
        taskqueue.add(url=welcome_url, params={
            'offset': 0
        })
        
class WelcomeHandler(BaseHandler):
    """
    Core Handler for sending users welcome message
    Use with TaskQueue
    """

    @taskqueue_method
    def post(self):
        count = 0
        offset = int(self.request.get("offset"))
        attempt = 1
        if (self.request.get("attempt")):
            attempt = int(self.request.get("attempt")) + 1

        #Case "One taskqueue, many homes"
        homes = models.Home.query()
        for home in homes:
            if home.cfe.rpu != -1 and home.cfe.connected and home.tips_email_counter == 0:
                logging.info("Welcoming Home ID: %s" % home.key.id())
                count += 1
                if count > offset:
                    try:
                        for habitant in home.habitant:
                            user_info = self.user_model.get_by_id(long(habitant))
                            if user_info != None:
                                _username = user_info.name
                                logging.info("Welcome message being sent to: %s" % user_info.email)
                                subject = messages.email_welcome_subject
                                template_val = {
                                    "username": _username,
                                    "_url": self.uri_for("history", _full=True),
                                    "support_url": self.uri_for("contact", _full=True),
                                    "twitter_url": self.app.config.get('twitter_url'),
                                    "facebook_url": self.app.config.get('facebook_url'),
                                    "faq_url": self.uri_for("faq", _full=True)
                                }
                                body_path = "emails/welcome.txt"
                                body = self.jinja2.render_template(body_path, **template_val)
                                email = user_info.email
                                email_url = self.uri_for('taskqueue-send-email')
                                
                                taskqueue.add(url=email_url, params={
                                    'to': str(user_info.email),
                                    'subject': subject,
                                    'body': body,
                                })

                        home.tips_email_counter = 1
                        home.tips_email_lastdate = date.today()
                        home.put()

                    except Exception, e:
                        logging.error("Error welcoming home: %s. Retrying taskqueue in 5 seconds." % e)
                        logging.info("Attempt number: %s" % attempt)
                        time.sleep(5)
                        if attempt < 10:
                            welcome_url = self.uri_for('taskqueue-welcome')
                            taskqueue.add(url=welcome_url, params={
                                'offset': count - 1,
                                'attempt': attempt,
                            })
                        else:
                            welcome_url = self.uri_for('taskqueue-welcome')
                            taskqueue.add(url=welcome_url, params={
                                'offset': count,
                            })
                        break




""" REST API preparation handlers

    These handlers obey to interactions with key-holder developers

"""
class APIIncomingHandler(BaseHandler):
    """
    Core Handler for incoming interactions
    """

    def post(self):
        KEY = "mwkMqTWFnK0LzJHyfkeBGoS2hr2KG7WhHqSGX0SbDJ4"
        SECRET = "152731fe2b14da111a72127d642e73c779e530b3"
        
        api_key = ""
        api_secret = ""
        args = self.request.arguments()
        for arg in args:
            logging.info("argument: %s" % arg)
            for key,value in json.loads(arg).iteritems():
                if key == "api_key":
                    api_key = value
                if key == "api_secret":
                    api_secret = value
                if key == "method":
                    if value == "101":
                        logging.info("parsing method 101")
                    elif value == "201":
                        logging.info("parsing method 201")

                        

        if api_key == KEY and api_secret == SECRET:
            logging.info("Attempt to receive incoming message with key: %s." % api_key)

            # DO SOMETHING WITH RECEIVED PAYLOAD

        else:
            logging.info("Attempt to receive incoming message without appropriate key: %s." % api_key)
            self.abort(403)

class APIOutgoingHandler(BaseHandler):
    """
    Core Handler for outgoing interactions with simpplo
    """

    def post(self):
        from google.appengine.api import urlfetch
        
        KEY = "mwkMqTWFnK0LzJHyfkeBGoS2hr2KG7WhHqSGX0SbDJ4"
        _URL = ""


        api_key = ""
        api_secret = ""
        args = self.request.arguments()
        for arg in args:
            logging.info("argument: %s" % arg)
            for key,value in json.loads(arg).iteritems():
                if key == "api_key":
                    api_key = value
                if key == "api_secret":
                    api_secret = value
                if key == "method":
                    if value == "101":
                        logging.info("parsing method 101")
                    elif value == "201":
                        logging.info("parsing method 201")
                        

        if api_key == KEY:
            logging.info("Attempt to send outgoing message with appropriate key: %s." % api_key)
            
            # DO SOMETHING WITH RECEIVED PAYLOAD
            #urlfetch.fetch(_URL, payload='', method='POST') 

        else:
            logging.info("Attempt to send outgoing message without appropriate key: %s." % api_key)
            self.abort(403)
       
class APITestingHandler(BaseHandler):
    """
    Core Handler for testing interactions with simpplo
    """

    def get(self):
        from google.appengine.api import urlfetch
        import urllib

        try:
            _url = self.uri_for('mbapi-out', _full=True)
            urlfetch.fetch(_url, payload='{"api_key": "mwkMqTWFnK0LzJHyfkeBGoS2hr2KG7WhHqSGX0SbDJ4","channel": "CHANNELHERE","container": "CONTENTSHERE"}', method="POST")
        except:
            pass
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Tests went good... =)')




""" WEB  static handlers

    These handlers are just to be a full website in the web background.

"""
class RobotsHandler(BaseHandler):
    def get(self):
        params = {
            'scheme': self.request.scheme,
            'host': self.request.host,
        }
        self.response.headers['Content-Type'] = 'text/plain'

        def set_variables(text, key):
            return text.replace("{{ %s }}" % key, params[key])

        self.response.write(reduce(set_variables, params, open("bp_content/themes/%s/templates/seo/robots.txt" % self.get_theme).read()))

class HumansHandler(BaseHandler):
    def get(self):
        params = {
            'scheme': self.request.scheme,
            'host': self.request.host,
        }
        self.response.headers['Content-Type'] = 'text/plain'

        def set_variables(text, key):
            return text.replace("{{ %s }}" % key, params[key])

        self.response.write(reduce(set_variables, params, open("bp_content/themes/%s/templates/seo/humans.txt" % self.get_theme).read()))

class SitemapHandler(BaseHandler):
    def get(self):
        params = {
            'scheme': self.request.scheme,
            'host': self.request.host,
        }
        self.response.headers['Content-Type'] = 'application/xml'

        def set_variables(text, key):
            return text.replace("{{ %s }}" % key, params[key])

        self.response.write(reduce(set_variables, params, open("bp_content/themes/%s/templates/seo/sitemap.xml" % self.get_theme).read()))

class CrossDomainHandler(BaseHandler):
    def get(self):
        params = {
            'scheme': self.request.scheme,
            'host': self.request.host,
        }
        self.response.headers['Content-Type'] = 'application/xml'

        def set_variables(text, key):
            return text.replace("{{ %s }}" % key, params[key])

        self.response.write(reduce(set_variables, params, open("bp_content/themes/%s/templates/seo/crossdomain.xml" % self.get_theme).read()))
