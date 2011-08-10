import sys
import re
import datetime
import dateutil
import oauth2 as oauth
import oauth2.clients.imap as imaplib
from email import message_from_string
from xml.dom import minidom
from celery.decorators import task

# TODO: Handle bad resp values and exceptions


number_re = re.compile('(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?')
email_re = re.compile('("?([a-zA-Z 0-9\._\-]+)"?\s+)?<?([a-zA-Z0-9\._\-]+@[a-zA-Z0-9\._\-]+)>?')


@task()
def scrape_gmail_messages(access_oauth_token, access_oauth_token_secret, consumer_key, consumer_secret):
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
    
    # Get message count
    resp, message_count = imap.select()
    message_count = int(message_count[0])
    print "Message count: %d" % message_count
    
    # Get messages
    resp, messages = imap.search(None, 'ALL')
    messages = messages[0].split()
    
    # Find the phone numbers in each message
    phone_numbers = []
    for index in range(message_count):
        phone_numbers += find_phone_numbers(imap, messages[index])
    
    imap.logout()
    return phone_numbers


@task()
def find_phone_numbers(imap, number):
    # TODO: Clean up debugging info
    print 'Processing message', number
    
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
    raw_phone_numbers = number_re.findall(content) + number_re.findall(msg['Subject'])
    # TODO: Make this more clear (flattens ['','650','555','1212'] to a string)
    phone_numbers = list(set(map(''.join, raw_phone_numbers)))
    # TODO: Handle numbers without area codes
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
    prefix = ''
    if s.startswith('+'):
        prefix = s[0]
        s = s[1:]
    # TODO: Clean this up
    if len(s) == 7:
        formatted = '%s-%s' % (s[0:3], s[3:7])
    elif len(s) == 10:
        formatted = '%s-%s-%s' % (s[0:3], s[3:6], s[6:10])
    else:
        formatted = s
    return prefix + formatted


def get_id(xmldoc):
    document = minidom.parseString(xmldoc)
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
