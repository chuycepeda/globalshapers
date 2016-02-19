# -*- coding: utf-8 -*-
import webapp2, json
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import ndb, blobstore
from google.appengine.ext.webapp import blobstore_handlers
from collections import OrderedDict, Counter
from wtforms import fields  
from bp_includes import forms, models, handlers, messages
from bp_includes.lib.basehandler import BaseHandler
from datetime import datetime, date, time, timedelta
from webapp2_extras.i18n import gettext as _
import logging


class AdminShapersHandler(BaseHandler):
   def get(self):
        p = self.request.get('p')
        q = self.request.get('q')
        c = self.request.get('c')
        forward = True if p not in ['prev'] else False
        cursor = Cursor(urlsafe=c)

        qry = models.Shapers.query()
        count = qry.count()
        PAGE_SIZE = 50
        if forward:
            shapers, next_cursor, more = qry.order(-models.Shapers.created).fetch_page(PAGE_SIZE, start_cursor=cursor)
            if next_cursor and more:
                self.view.next_cursor = next_cursor
            if c:
                self.view.prev_cursor = cursor.reversed()
        else:
            shapers, next_cursor, more = qry.order(models.Shapers.created).fetch_page(PAGE_SIZE, start_cursor=cursor)
            shapers = list(reversed(shapers))
            if next_cursor and more:
                self.view.prev_cursor = next_cursor
            self.view.next_cursor = cursor.reversed()

        def pager_url(p, cursor):
            params = OrderedDict()
            if q:
                params['q'] = q
            if p in ['prev']:
                params['p'] = p
            if cursor:
                params['c'] = cursor.urlsafe()
            return self.uri_for('admin-blog', **params)

        self.view.pager_url = pager_url
        self.view.q = q

        params = {
            "list_columns": [('name', 'Name'),
                             ('created', 'Created'),
                             ('key', 'Key'),
                             ('image', 'Image URL')],
            "shapers": shapers,
            "count": count
        }
        return self.render_template('admin_shapers.html', **params)

class AdminNewShaperHandler(BaseHandler):
    
    def post(self):
        """ Get fields from POST dict """                        
        
        try:
            if self.request.get('shaper_id') == "none":
                shaper = models.Shapers()
            else:
                shaper = models.Shapers.get_by_id(long(self.request.get('shaper_id')))
                if shaper is None:
                    shaper = models.Shapers()

            shaper.name = self.request.get('name')
            shaper.email = self.request.get('email')
            birth = self.request.get('birth')
            if (len(birth) > 9):
                shaper.birth = date(int(birth[:4]), int(birth[5:7]), int(birth[8:]))
            shaper.bio = self.request.get('bio')
            shaper.twitter = self.request.get('twitter')
            shaper.linkedin = self.request.get('linkedin')
            shaper.image = self.request.get('image')
            shaper.put()
            
            message = _(messages.saving_success)
            self.add_message(message, 'success')
            return self.redirect_to('admin-shapers')


        except Exception as e:
            logging.info('error in post: %s' % e)
            message = _(messages.saving_error)
            self.add_message(message, 'danger')
            return self.get()

class AdminShaperEditHandler(BaseHandler):
    def get(self, shaper_id):
        params = {}
        params['sh_name'] = ''
        params['sg_email'] = ''
        params['birth'] = ''
        params['bio'] = ''
        params['twitter'] = ''
        params['linkedin'] = ''
        params['image'] = ''
        params['shaper_id'] = shaper_id if len(str(shaper_id)) > 0 else 1
        if shaper_id != 1:
            shaper = models.Shapers.get_by_id(long(shaper_id))
            if shaper is not None:
                params['sh_name'] = shaper.name
                params['sh_email'] = shaper.email
                params['birth'] = shaper.birth.strftime("%Y-%m-%d")
                params['bio'] = shaper.bio
                params['twitter'] = shaper.twitter
                params['linkedin'] = shaper.linkedin
                params['image'] = shaper.image
        return self.render_template('admin_shaper_edit.html', **params)

    def post(self, shaper_id):
        try:
            shaper = models.Shapers.get_by_id(long(shaper_id))
            shaper.name = self.request.get('name')
            shaper.email = self.request.get('email')
            birth = self.request.get('birth')
            if (len(birth) > 9):
                shaper.birth = date(int(birth[:4]), int(birth[5:7]), int(birth[8:]))
            shaper.bio = self.request.get('bio')
            shaper.twitter = self.request.get('twitter')
            shaper.linkedin = self.request.get('linkedin')
            shaper.image = self.request.get('image')
            shaper.put()
            self.add_message(messages.saving_success, 'success')
            return self.redirect_to('admin-shapers')
        except:
            self.add_message(messages.saving_error, 'danger')
            return self.get(shaper_id = shaper.key.id())

class AdminShaperDeleteHandler(BaseHandler):
    def get(self, shaper_id):
        if shaper_id != 1:
            shaper = models.Shapers.get_by_id(long(shaper_id))
            if shaper is not None:
                shaper.key.delete()
            self.add_message(messages.saving_success, 'success')
        return self.redirect_to('admin-shapers')