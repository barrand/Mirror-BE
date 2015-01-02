#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import cgi
import webapp2
import jinja2
import urlparse
import os
import urllib
import json
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
from datetime import datetime, timedelta

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_ARRIVALLOG_NAME = 'default_arrival_log'
DEFAULT_TOKEN_STORAGE_NAME = 'default_instagram_token_storage'

# We set a parent key on the 'Greetings' to ensure that they are all in the same
# entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.

def arrivallog_key(arrivallog_name=DEFAULT_ARRIVALLOG_NAME):
    """Constructs a Datastore key for a Arrivallog entity with arrivallog_name."""
    return ndb.Key('Arrivallog', arrivallog_name)

def instagramTokens_key(tokenstorage_name=DEFAULT_TOKEN_STORAGE_NAME):
    return ndb.Key('Tokenstorage', tokenstorage_name)
    


class InstagramToken(ndb.Model):
    handle = ndb.StringProperty()
    userid = ndb.StringProperty()
    accessToken = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)

class Arrival(ndb.Model):
    """Models an individual Arrivallog entry."""
    deviceId = ndb.StringProperty(indexed=False)
    guestName = ndb.StringProperty(indexed=False)
    avatar = ndb.StringProperty(indexed=False)
    message = ndb.StringProperty(indexed=False)
    memberType = ndb.StringProperty(indexed=False)
    handle = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<html><body>')
        arrivallog_name = self.request.get('guestbook_name',
                                          DEFAULT_ARRIVALLOG_NAME)

        # Ancestor Queries, as shown here, are strongly consistent with the High
        # Replication Datastore. Queries that span entity groups are eventually
        # consistent. If we omitted the ancestor from this query there would be
        # a slight chance that Greeting that had just been written would not
        # show up in a query.
        arrivals_query = Arrival.query().order(-Arrival.date)
        arrivals = arrivals_query.fetch(10)

        template_values = {
            'arrivals':arrivals
        }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

class ClearHandler(webapp2.RequestHandler):
    def get(self):
        ndb.delete_multi(Arrival.query().fetch(keys_only=True))
        self.response.write('cleared all arrivals')

class ArriveHandler(webapp2.RequestHandler):
    def post(self):
        # guestbook_name = self.request.get('guestbook_name',
        #                                   DEFAULT_GUESTBOOK_NAME)
        arrival = Arrival()
        arrival.deviceId = self.request.get('deviceId', 'n/a')
        arrival.guestName = self.request.get('guestName', 'no name provided')
        arrival.avatar = self.request.get('avatar', 'http://3.bp.blogspot.com/-fSRD9SLNzHo/UVwhXCSqjZI/AAAAAAAAF8o/Pg1tdZtcL70/s1600/anonymous_avatar.png')
        arrival.message = self.request.get('message', 'no message provide')
        arrival.memberType = self.request.get('memberType', 'basic')
        arrival.handle = self.request.get('handle', 'n/a')
        arrival.put()

        self.response.write('true')
    def get(self):
        # guestbook_name = self.request.get('guestbook_name',
        #                                   DEFAULT_GUESTBOOK_NAME)
        arrival = Arrival()
        arrival.deviceId = self.request.get('deviceId', 'n/a')
        arrival.guestName = self.request.get('guestName', 'no name provided')
        arrival.avatar = self.request.get('avatar', 'http://3.bp.blogspot.com/-fSRD9SLNzHo/UVwhXCSqjZI/AAAAAAAAF8o/Pg1tdZtcL70/s1600/anonymous_avatar.png')
        arrival.message = self.request.get('message', 'no message provided')
        arrival.memberType = self.request.get('memberType', 'no memberType given')
        arrival.put()

        self.redirect('/')

class InstagramHandler(webapp2.RequestHandler):
    def get(self):

        print "got a code " + self.request.get('code')
        payload = {'client_id': 'c6cadc7fd91b4cee85388bfae1a04c2b', 
            'client_secret': '67820fc0834344a6bbebf6112ef30917',
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://ordinal-verbena-810.appspot.com/instagram',
            'code': self.request.get('code')}
        form_data = urllib.urlencode(payload)
        url = "https://api.instagram.com/oauth/access_token"
        result = urlfetch.fetch(url, 
            payload = form_data, 
            method=urlfetch.POST)
        print("got a response \n\n")
        if result.status_code == 200:
            print result.status_code
            d = json.loads(result.content)
            print d['access_token']
            print d['user']['username']
            self.response.write('<html><body> status code ' + d['access_token'])
            self.response.write('\nreturn  ' + str(result.content))
            token = InstagramToken()
            token.accessToken = d['access_token']
            token.handle = d['user']['username']
            token.userid = d['user']['id']
            token.put()
        else:
            self.response.write('<html><body> no worky ' + str(result.status_code))
                

class LobbyHandler(webapp2.RequestHandler):
    def get(self): 
        arrivals_query = Arrival.query().order(-Arrival.date)
        arrivals = arrivals_query.fetch(1)
        token = None
        arrival = None
        if len(arrivals) > 0:
            # If it is older than the expiration time
            timeDiff = datetime.now() - arrivals[0].date
            timeDeltaToCompare = timedelta(minutes = 2)
            print "diff " + str(timeDiff)
            print "compare delta " + str(timeDeltaToCompare)
            # If we have a recent checkin, get the latest token
            if timeDiff < timeDeltaToCompare:
                # Get the latest token
                tokens_query = InstagramToken.query().order(-InstagramToken.date)
                tokens = tokens_query.fetch()
                token = tokens[0]
                print "there is a recent arrival, so adding a token" + str(token)
                arrival = arrivals[0]
        template_values = {
            'arrival':arrival,
            'token':token
        }
        template = JINJA_ENVIRONMENT.get_template('lobby.html')
        self.response.write(template.render(template_values))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/arrive', ArriveHandler),
    ('/instagram', InstagramHandler),
    ('/lobby', LobbyHandler),
    ('/clear', ClearHandler)
], debug=True)
