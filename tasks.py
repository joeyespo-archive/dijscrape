import re
import time
import dateutil
import psycopg2
import xml.dom.minidom
import oauth2 as oauth
import oauth2.clients.imap as imaplib
from datetime import datetime
from email import message_from_string
from celery.decorators import task
try:
    from bundle_config import config
except:
    config = None
if config and 'postgres' not in config:
    print '***WARNING*** Expected bundle_config.config to include postgres settings but they are missing.'

# TODO: Handle bad resp values and exceptions


number_re = re.compile('(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?')
email_re = re.compile('("?([a-zA-Z 0-9\._\-]+)"?\s+)?<?([a-zA-Z0-9\._\-]+@[a-zA-Z0-9\._\-]+)>?')


@task()
def scrape_gmail_messages(mailbox_to_scrape, access_oauth_token, access_oauth_token_secret, consumer_key, consumer_secret):
    phone_numbers = []
    try:
        start_datetime = datetime.now()
        
        consumer = oauth.Consumer(consumer_key, consumer_secret)
        token = oauth.Token(access_oauth_token, access_oauth_token_secret)
        client = oauth.Client(consumer, token)
        
        # Get the email address from Google contacts
        resp, xmldoc = client.request('https://www.google.com/m8/feeds/contacts/default/full?max-results=0')
        email = get_id(xmldoc)
        
        # Connect with IMAP
        url = 'https://mail.google.com/mail/b/%s/imap/' % email
        imap = imaplib.IMAP4_SSL('imap.googlemail.com')
        imap.authenticate(url, consumer, token)
        
        # Get messages and message count
        resp, message_count = imap.select(mailbox_to_scrape)
        message_count = int(message_count[0])
        print "Message count: %d" % message_count
        resp, messages = imap.search(None, 'ALL')
        messages = messages[0].split()
        scrape_gmail_messages.update_state(state="PROGRESS", meta={"current": 0, "total": message_count})
        
        # Find the phone numbers in each message
        for index in range(message_count):
            print 'Message %s/%s' % (index, message_count)
            try:
                phone_numbers += find_phone_numbers(imap, messages[index])
                scrape_gmail_messages.update_state(state="PROGRESS", meta={"current": index + 1, "total": message_count})
            except:
                print 'Error: could not parse message #%s. Skipping.' % index
                from traceback import format_exc
                print format_exc()
                print
        
        imap.logout()
        end_datetime = datetime.now()
        
        # Log the process and its performance
        if config:
            try:
                conn = psycopg2.connect(
                    host = config['postgres']['host'],
                    port = int(config['postgres']['port']),
                    user = config['postgres']['username'],
                    password = config['postgres']['password'],
                    database = config['postgres']['database'],
                )
                cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO processed (message_count, phone_number_count, start_time, end_time) VALUES (%s, %s, %s, %s)", (message_count, len(phone_numbers), start_datetime, end_datetime))
                except psycopg2.ProgrammingError:
                    # Error, reset the connection
                    conn.rollback()
                    # Add table and retry
                    cur.execute("CREATE TABLE processed (message_count integer, phone_number_count integer, start_time timestamp, end_time timestamp);")
                    cur.execute("INSERT INTO processed (message_count, phone_number_count, start_time, end_time) VALUES (%s, %s, %s, %s)", (message_count, len(phone_numbers), start_datetime, end_datetime))
                    print 'Database table "processed" created.'
                conn.commit()
                cur.close()
            except:
                print 'Error: could not log performance.'
                from traceback import format_exc
                print format_exc()
            finally:
                conn.close()
        else:
            print 'Processed %s: Phone Numbers = %s, Start = %s, End = %s' % (message_count, len(phone_numbers), start_datetime.strftime('%m/%d/%Y %I:%M:%S %p'), end_datetime.strftime('%m/%d/%Y %I:%M:%S %p'))
        
        return phone_numbers
    except:
        from traceback import format_exc
        print format_exc()
        return phone_numbers


@task()
def find_phone_numbers(imap, number):
    # TODO: Clean up debugging info
    resp, message_data = imap.fetch(number, '(BODY[])')
    raw_message = message_data[0][1]    # Encodes some data re: the request type
    msg = message_from_string(raw_message)
    
    # Get email content
    content = ''
    for part in msg.walk():
        c_type = part.get_content_type()
        if part.get_content_type() == 'text/plain':
            content += '\n' + part.get_payload()
    
    # Find the phone numbers
    # TODO: Use finditer to get the MatchObject instances for highlighting the matched numbers in the results
    raw_phone_numbers = number_re.findall(content) + number_re.findall(msg['Subject'])
    # TODO: Make this more clear (flattens ['','650','555','1212'] to a string) then accept only numbers with ten or more digits
    phone_numbers = list(set(map(''.join, raw_phone_numbers)))
    phone_numbers = filter(lambda x: len(x) >= 10, phone_numbers)
    print 'Phone numbers (%s): %s' % (len(phone_numbers), phone_numbers)
    if len(phone_numbers) == 0:
        return []
    
    date_timestamp = msg['Date']
    date = dateutil.parser.parse(date_timestamp)
    print 'Header date:', date, '(', date_timestamp, ')'
    
    # This may fail due to unicode issues
    try:
        name, email = email_re.match(msg['From']).groups()[1:3]
        print 'From:', name, email
    except:
        from traceback import format_exc
        print format_exc()
        return []
    
    # TODO: Use classes instead of dictionaries
    message_info = {
        'sender': msg['From'],
        'recipient': msg['To'],
        'sender_name': name,
        'sender_email': email,
        'subject': msg['Subject'],
        'date_add': date,
        'content': content,
    }
    phone_number_objects = []
    for phone_number in phone_numbers:
        phone_number_objects.append({'value': phone_number, 'formatted_value': format_phone_number(phone_number), 'message': message_info})
    return phone_number_objects


def format_phone_number(s):
    try:
        # TODO: Use a library instead
        prefix = ''
        if s.startswith('+'):
            prefix = s[0]
            s = s[1:]
        
        if len(s) == 7:
            formatted = '%s-%s' % (s[0:3], s[3:7])
        elif len(s) == 10:
            formatted = '%s-%s-%s' % (s[0:3], s[3:6], s[6:10])
        else:
            formatted = s
        return prefix + formatted
    except:
        return s


def get_id(xmldoc):
    document = xml.dom.minidom.parseString(xmldoc)
    feedElement = document.firstChild
    for childNode in feedElement.childNodes:
        if childNode.localName == 'id':
            return xml_get_text(childNode)
    return ''


def xml_get_text(node):
    rc = []
    for node in node.childNodes:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)
