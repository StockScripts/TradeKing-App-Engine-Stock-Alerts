from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.api import xmpp
from google.appengine.api import mail
import logging
import cgi, os, urllib

import quote

class Alert(db.Model):
  ticker     = db.StringProperty()
  hi_price   = db.FloatProperty()
  low_price  = db.FloatProperty()
  user       = db.UserProperty()
  curr_price = db.FloatProperty()

class MainPage(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    path = os.path.join(os.path.dirname(__file__), 'set_alerts.html')
    query = Alert.all().filter('user = ', user)
    template_values = {
      'alerts': query.fetch(1000),
      'user' : user,
    }
    self.response.out.write(template.render(path, template_values))

class CheckAlerts(webapp.RequestHandler):
  def get(self):
    query = Alert.all()
    alerts = query.fetch(1000)
    
    users   = {}
    tickers = set()
    
    for alert in alerts:
      user   = alert.user
      ticker = alert.ticker.upper()
      
      if user in users:
        users[user].append(alert)
      else:
        users[user] = [alert]
      
      tickers.add(ticker)
    
    q = quote.quote()
    
    d = q.get_quote(list(tickers))
    
    prices = self.getData(d)
    
    for user, alerts in users.items():
      for alert in alerts:
        hi_price  = float(alert.hi_price)
        low_price = float(alert.low_price)
        ticker    = alert.ticker.upper()
        user_address = '%s@gmail.com' % (user)
        
        if prices[ticker] > hi_price:
          self.response.out.write("Broke above %s's limit of $%.2f for %s" % (user.nickname(),hi_price,ticker) )
          
          chat_message_sent = False
          msg = "%s went up to %.2f!" % (ticker,prices[ticker])
          status_code = xmpp.send_message(user_address, msg)
          chat_message_sent = (status_code == xmpp.NO_ERROR)
          
        if prices[ticker] < low_price:
          self.response.out.write("Broke below %s's limit of $%.2f for %s" % (user.nickname(),low_price,ticker) )
          
          chat_message_sent = False
          msg = "%s went down to %.2f!" % (ticker,prices[ticker])
          status_code = xmpp.send_message(user_address, msg)
          chat_message_sent = (status_code == xmpp.NO_ERROR)
          
          user_address = user.email()
          
          if not mail.is_email_valid(user_address):
            # prompt user to enter a valid address
          else:
            confirmation_url = createNewUserConfirmation(self.request)
            sender_address = "rpibic@gmail.com"
            subject = "Alert for %s" % (ticker)
            body = "Broke below %s's limit of $%.2f for %s" % (user.nickname(),low_price,ticker)
            
            mail.send_mail(sender_address, user_address, subject, body)
    for alert in alerts:
      alert.curr_price = prices[alert.ticker]
  
  def getData(self,stocks):
    d = {}
    for stock in stocks:
      d[stock['instrument']['sym'].upper()] = float(stock['quote']['lastprice'])
    return d
    
class AddAlert(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    
    user = users.get_current_user()

    if not user:
      self.response.out.write("no user found, redirecting to login...")
      self.redirect(users.create_login_url(self.request.uri))
    else:
      ticker    = urllib.unquote( cgi.escape(self.request.get('ticker'   )).upper() )
      hi_price  = urllib.unquote( cgi.escape(self.request.get('hi_price' )).lower() )
      low_price = urllib.unquote( cgi.escape(self.request.get('low_price')).lower() )
      
      query = Alert.all()
      query.filter('user = '  , user)
      query.filter('ticker = ', ticker)
      
      prev_alerts = query.fetch(1)
      
      if prev_alerts:
        prev_alert = prev_alerts[0]
        
        prev_alert.hi_price  = float(hi_price)
        prev_alert.low_price = float(low_price)
        prev_alert.put()
      else:
        alert = Alert()
        
        alert.ticker    = ticker
        alert.hi_price  = float(hi_price)
        alert.low_price = float(low_price)
        alert.user      = user
        
        alert.put()

application = webapp.WSGIApplication(
  [('/check_alerts', CheckAlerts),
   ('/add_alert', AddAlert),
   ('/', MainPage),])
   
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
