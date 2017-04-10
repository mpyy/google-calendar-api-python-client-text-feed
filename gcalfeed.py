# from optparse import OptionParser # in Python 2.7 optparse will be replaced by argparse
import sys
import argparse
import gflags
import httplib2
import codecs
# replaced simplejson with json
# import simplejson
import json
import re

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import OAuth2WebServerFlow
from oauth2client import tools
from oauth2client.tools import run_flow


from datetime import datetime, date, timedelta
import time
# from time import strptime
from os import getlogin, system
from os.path import expanduser, realpath, dirname, join

altuser = ''
myuser = ''
GCALFEED_CONFIG = 'config.json'
GCALFEED_OUT = 'gcal_feeds.out'


# TODO: Implement as class files
class CalFeed:
  # Constants
  GDATA_TRANSPARENT = 'transparent'
  ORDERBY = 'startTime'
  TZ = 'Europe/Helsinki'

  def __init__(self):
      # Members
      self.events = []
      self.name = ''
      self.owner = ''

  def setup(self, name, owner, userID, visibility, projection, transparents, hilitecolor, start_date, end_date):
      self.name = name
      self.owner = owner
      self.userID = userID
      self.visibility = visibility
      self.transparents = transparents
      self.start_date = start_date.isoformat() + 'T00:00:00Z'
      self.end_date = end_date.isoformat() + 'T00:00:00Z'
      self.projection = projection
      self.hilitecolor = hilitecolor

  def to_datetime(self, dt):
      try:
      # Removed .000
          retval = datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S+' + dt[-5:])  # string end 02:00 or 03:00
      except ValueError:
          retval = datetime.strptime(dt, '%Y-%m-%d')
      return retval

  def get_eventdate(self, event_dt):
    retval = None
    try:
      retval = event_dt['dateTime']
    except KeyError:
      retval = event_dt['date']
    return retval

  def get_structtime(self, time_str):
    retval = ''

    # Handle all-day events
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    if pattern.match(time_str):
      time_str = time_str + 'T00:00:00+00:00'

    # Removed .000
    retval = time.strptime(time_str, '%Y-%m-%dT%H:%M:%S+' + time_str[-5:])  # string end 02:00 or 03:00
    return retval

  def make_event(self, cal, title, a_when):
    return Event(cal, title, a_when)

#  def exclude_event(self, an_event, a_when):
  def exclude_event(self, an_event):
    # never exclude events
    return False

  def fetch_events(self):
    feed = service.events().list(calendarId=self.userID, timeMin=self.start_date, timeMax= self.end_date, orderBy=self.ORDERBY, singleEvents=True, timeZone=self.TZ).execute()

    # Loop through the feed and extract each entry
    for an_event in feed['items']:
          # title = an_event.title.text
          # use this in case title is empty
      #          title = "{0}".format(an_event.title.text)
      title = an_event['summary']

      # TBD: work with recurrences
      #          for a_when in an_event.when:
      try:
        # if self.to_datetime(an_event['end']['dateTime']) < datetime.now():
        if self.to_datetime(self.get_eventdate(an_event['end'])) < datetime.now():
            continue
      except KeyError:
        # if self.to_datetime(an_event['end']['date']) < datetime.now():
        if self.to_datetime(self.get_eventdate(an_event['end'])) < datetime.now():
            continue

            # skip entries based on their transparency
      if self.transparents == 'no':
          if an_event['transparency'].value.lower() == self.GDATA_TRANSPARENT.lower():
            # Don't skip if the calendar is a "common" calendar
            # TODO: Implement event feed configuration as a JSON file so transparency can be set for each calendar
            if self.owner != 'common':
                continue
      elif self.transparents == 'only':
        if an_event['transparency'].value.lower() != self.GDATA_TRANSPARENT.lower():
        # Don't skip if the calendar is a "common" calendar
        # TODO: Change transparency to be selected calendar by calendar
            if self.owner != 'common':
                continue

      # if self.exclude_event(an_event, a_when):
      if self.exclude_event(an_event):
          continue

            # Append to the events list
      # self.events.append(self.make_event(self, title, a_when))
      self.events.append(self.make_event(self, title, an_event))

  def list_events(self):
      retval = []
      for evt in self.events:
          retval.append(evt.print_event())
      return retval

  def count(self):
      return len(self.events)


class WorkCalFeed(CalFeed):
    # Constants
    LATE_TIME = 16

    def __init__(self):
        CalFeed.__init__(self)

    def make_event(self, cal, title, a_when):
        return WorkEvent(cal, title, a_when)

    def is_working_late(self, a_when):
        retval = False
        try:
            # tm1 = self.get_structtime(a_when.start_time)
            tm1 = self.get_structtime(self.get_eventdate(a_when['start']))
            d1 = date(tm1.tm_year, tm1.tm_mon, tm1.tm_mday)
            w1 = d1.weekday()
            h1 = tm1.tm_hour
            # tm2 = self.get_structtime(a_when.end_time)
            tm2 = self.get_structtime(self.get_eventdate(a_when['end']))
            d2 = date(tm2.tm_year, tm2.tm_mon, tm2.tm_mday)
            w2 = d2.weekday()
            h2 = tm2.tm_hour
            if w2 >= 0 and w2 <= 4 and h2 > self.LATE_TIME:
                retval = True
        except ValueError:
            pass
        return retval

#    def exclude_event(self, an_event, a_when):
    def exclude_event(self, an_event):
        retval = False
        # exclude event from other users during normal working hours
        # DEBUG: print "{0}".format(an_event.title.text) + '\t' + self.owner + '\t' + myuser + '\t' + a_when.start_time
    #        if self.owner != myuser and not self.is_working_late(a_when):
        if self.owner != myuser and not self.is_working_late(an_event):
            retval = True
            # DEBUG: print 'Excluding: ' + "{0}".format(an_event.title.text) + '\t' + a_when.start_time + '\t' + a_when.end_time
        return retval


class Event:
    # Constants
    WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    ANSI_CSI = '\x1b['
    ANSI_RESET = ANSI_CSI + '0m'

    def __init__(self, cal, title, a_when):
        self.cal = cal
        self.title = title
        self.a_when = a_when

    def get_weekday(self, tm):
        d = date(tm.tm_year, tm.tm_mon, tm.tm_mday)
        return self.WEEKDAYS[d.weekday()]

    def ansi_color(self, str):
        retval = str
        if self.cal.hilitecolor != '':
            retval = self.ANSI_CSI + self.cal.hilitecolor + 'm' + str + self.ANSI_RESET
        return retval

    def get_short_date_time(self):
        retval = None
        try:
            # self.cal = bad?
            # tm = self.cal.get_structtime(self.a_when.start_time)
            tm = self.cal.get_structtime(self.cal.get_eventdate(self.a_when['start']))
            tm1 = '%s' % (time.mktime(tm),)
            tm2 = '%s %s.%s.' % (self.get_weekday(tm), tm.tm_mday, tm.tm_mon,)
            tm3 = '%d:%02d' % (tm.tm_hour, tm.tm_min,)
        except ValueError:
            # tm = time.strptime(self.a_when.start_time, '%Y-%m-%d')
            tm = time.strptime(self.cal.get_eventdate(self.a_when['start']), '%Y-%m-%d')
            tm1 = '%s' % (time.mktime(tm),)
            tm2 = '%s %s.%s.' % (self.get_weekday(tm), tm.tm_mday, tm.tm_mon,)
            tm3 = ''
        retval = [tm1, tm2, tm3]
        return retval

    def add_endtime(self):
        retval = ''
        # if this is not my login, add the end time for events outside office hours
        # awkward? self.cal.owner, self.cal.is_working_late, self.cal.get_structtime
        if (self.cal.owner == altuser and myuser != users[0]):
            # self.cal = bad?
            # tm = self.cal.get_structtime(self.a_when.end_time)
            tm = self.cal.get_structtime(self.cal.get_eventdate(self.a_when['end']))
            t = str(tm.tm_hour)
            if tm.tm_min != 0:
                t += ':' + str(tm.tm_min)
            retval = '-' + t
        return retval


    def print_event(self):
        retval = ''
        content = self.get_short_date_time()
        title = self.title
        # Append owner's initial to entries from other calendars
        # bad to use self.cal.owner?
        if self.cal.owner == altuser:
            title = title + ' (' + self.cal.owner.upper()[0] + ')'
        content.append(title)
        content.append(self.add_endtime())
        # Replace with colored items using a Python list comprehension
        for i,x in enumerate(content):
            # skip first column and empty columns
            if i > 0 and x <> '':
                content[i] = self.ansi_color(x)

            retval = '\t'.join(content)
        return retval


class WorkEvent(Event):
    def __init__(self, cal, title, a_when):
        Event.__init__(self, cal, title, a_when)

    def add_endtime(self):
        retval = ''
        # if this is not my login, add the end time for events outside office hours
        # awkward? self.cal.owner, self.cal.is_working_late, self.cal.get_structtime
        if (self.cal.owner == altuser and myuser != users[0]) and self.cal.is_working_late(self.a_when):
            # self.cal = bad?
            # tm = self.cal.get_structtime(self.a_when.end_time)
            tm = self.cal.get_structtime(self.cal.get_eventdate(self.a_when['end']))
            t = str(tm.tm_hour)
            if tm.tm_min != 0:
                t += ':' + str(tm.tm_min)
            retval = '-' + t
        return retval


# Main
def main(argv):
    global altuser
    global myuser
    global users
    global service

    users = ('my_user_name', 'another_user_name')
    myuser = getlogin()
    altuser = ''
    for x in users:
        if myuser <> x:
            altuser = x
            break

    # 2017-02-25: Set up data for OAuth Flow object (client secrets):

    script_real_path = dirname(realpath(__file__))
    CLIENT_SECRETS = join(script_real_path, 'client_secrets.json')
    OAUTH2_STORAGE = join(script_real_path, 'calendar.dat')
    GCAL_SCOPE = 'https://www.googleapis.com/auth/calendar.readonly'

    # Calendar feeds defined as JSON file
    infile = join(script_real_path, GCALFEED_CONFIG)
    with open(infile) as f:
        all_cals = json.load(f)

    scope = 'https://www.google.com/calendar/feeds/'
    outfile = join(script_real_path, GCALFEED_OUT)

    # 2017-02-25: Moved gflags here
    FLAGS = gflags.FLAGS

    LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    gflags.DEFINE_enum('logging_level', 'INFO', LOG_LEVELS, 'Set the level of logging detail.')
    gflags.DEFINE_boolean('noauth_local_webserver', False, 'Disable the local server feature.')
    gflags.DEFINE_list('auth_host_port', [8080, 8090], 'Set the auth host port.')
    gflags.DEFINE_string('auth_host_name', 'localhost', 'Set the auth host name.')

    # To disable the local server feature, uncomment the following line:
    # FLAGS.auth_local_webserver = False
    # FLAGS.noauth_local_webserver = True

    # 2017-02-25: Parse arguments first before initiating OAuth2 Flow

    parser = argparse.ArgumentParser(
        description='Fetch Calendar data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[tools.argparser])

    parser.add_argument('-d', '--days', action='store', dest='days', type=int, help='number of days to fetch events')
    parser.add_argument('-c', '--cals', action='append', dest='cals', help='calendars to fetch')
    parser.add_argument('-t', '--test', action='store', dest='test', choices=('yes','no'), help='don\'t write to file')
    parser.add_argument('-u', '--user', action='store', dest='user', help='switch current user')
    parser.add_argument('-r', '--transparents', action='store', dest='transparents', choices=('only','no','both'), help='select what to do with transparent events')

    parser.set_defaults(days=7, cals=[myuser], test='no', skip='yes')

    # Parse the command-line flags.
    flags = parser.parse_args(argv[1:])

    if flags.days < 1 or flags.days > 365:
        parser.error("-d, --days option must be between 1 and 365")

    if flags.user != None:
        altuser = myuser
        myuser = flags.user

    delta = timedelta(flags.days)

    for x in flags.cals:
        if x not in [y['name'] for y in all_cals]:
            parser.error("-c, --cals option not defined: " + x)

    # Set up a Flow object to be used if we need to authenticate. This
    # sample uses OAuth 2.0, and we set up the OAuth2WebServerFlow with
    # the information it needs to authenticate. Note that it is called
    # the Web Server Flow, but it can also handle the flow for native
    # applications
    # The client_id and client_secret can be found in Google Developers Console

    # Perform OAuth 2.0 authorization.
    FLOW = flow_from_clientsecrets(CLIENT_SECRETS, scope=GCAL_SCOPE)

    # If the Credentials don't exist or are invalid, run through the native client
    # flow. The Storage object will ensure that if successful the good
    # Credentials will get written back to a file.
    storage = Storage(OAUTH2_STORAGE)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(FLOW, storage, FLAGS)

    #if credentials is None or credentials.invalid == True:
    #  credentials = run(FLOW, storage)

    # Create an httplib2.Http object to handle our HTTP requests and authorize it
    # with our good Credentials.
    http = httplib2.Http()
    http = credentials.authorize(http)

    # Build a service object for interacting with the API. Visit
    # the Google Developers Console
    # to get a developerKey for your own application.
    service = build(serviceName='calendar', version='v3', http=http)

    start_date = date.today()
    end_date = start_date+delta


    def in_option_cals(x):
        return x['name'] in flags.cals

    def make_calfeed(special):
        retval = None
        if special:
            retval = WorkCalFeed()
        else:
            retval = CalFeed()
        return retval

    # Set up calendar feeds
    calfeeds = []
    for a_cal in filter(in_option_cals, all_cals):
        a_calfeed = make_calfeed(a_cal['special'])
        transparents = a_cal['transparents']
        if flags.transparents != None:
            if flags.transparents.lower() == 'only':
                transparents = 'only'
            elif flags.transparents.lower() == 'no':
                transparents = 'no'
            else:
                transparents = 'both'

        a_calfeed.setup(a_cal['name'], a_cal['owner'], a_cal['userID'], a_cal['visibility'], a_cal['projection'], transparents, a_cal['hilitecolor'], start_date, end_date)
        calfeeds.append(a_calfeed)

    # Parse events
    events = []
    for a_calfeed in calfeeds:
        a_calfeed.fetch_events()
        # DEBUG: print a_calfeed.name + '\t' + str(a_calfeed.count()) + '\t' + str(a_calfeed)
        # DEBUG: events.append('-- ' + a_calfeed.name + ' --')
        events.extend(a_calfeed.list_events())

    # DEBUG: print len(events)

    if flags.test == 'no':
        # with open(outfile, 'w') as f:
        with codecs.open(outfile, encoding='utf-8', mode='w') as f:
            f.write('\n'.join(sorted(events)))
        # If using GeekTool, refresh the widgets. See https://www.tynsoe.org and http://flipmartin.net/software/applescript-tips-for-geektool-3
        # system("osascript -e 'tell application \"GeekTool Helper\" to refresh all'")
    else:
        print ('\n'.join(sorted(events))).encode('utf8')


if __name__ == '__main__':
    main(sys.argv)
