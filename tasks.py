import sys
import re
import datetime
import oauth2 as oauth
import oauth2.clients.imap as imaplib
from email.parser import HeaderParser
from dateutil.parser import parse
from celery.decorators import task


number_re = re.compile('(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?')
email_re = re.compile('("?([a-zA-Z 0-9\._\-]+)"?\s+)?<?([a-zA-Z0-9\._\-]+@[a-zA-Z0-9\._\-]+)>?')


@task()
def find_phone_numbers(imap, number):
    print 'Processing message', number
    
    # TODO: Handle exceptions and bad resp
    resp, message_data = imap.fetch(number, '(BODY.PEEK[HEADER])')
    raw_message = message_data[0][1] # message_data, the data structure returned by imaplib, encodes some data re: the request type
    header = HeaderParser().parsestr(raw_message)
    # Check for multipart message
    if 'multipart' in (header['Content-Type'] or []):
        # TODO: Handle multipart messages
        print 'Skipping multipart message'
        return []
    
    # TODO: Handle exceptions and bad resp
    resp, message_data = imap.fetch(number, '(BODY.PEEK[TEXT])')
    text_payload = message_data[0][1]
    raw_phone_numbers = number_re.findall(text_payload) + number_re.findall(header['Subject'])
    # TODO: Make this more clear (flattens ['','650','555','1212'] to a string)
    raw_phone_numbers = list(set(map(''.join, raw_phone_numbers)))
    print "Phone numbers (%s): %s" % (len(raw_phone_numbers), raw_phone_numbers)
    if len(raw_phone_numbers) == 0:
        return []
    
    date_timestamp = header['Date']
    date = parse(date_timestamp)
    print 'Header date:', date, '(', date_timestamp, ')'
    
    # This may fail due to unicode issues
    try:
        name, email = email_re.match(header['From']).groups()[1:3]
        print 'From:', name, email
    except:
        from traceback import format_exc
        print format_exc()
        return []
    
    message = {
        'sender': header['From'],
        'recipient': header['To'],
        'sender_name': name,
        'sender_email': email,
        'subject': header['Subject'],
        'date_add': date,
        'payload': text_payload,
    }
    
    # TODO: Clean this up
    for raw_phone_number in raw_phone_numbers:
        # TODO: Handle numbers without area codes
        if len(str(raw_phone_number)) <= 7:
            continue
        phone_numbers.append({'value': phone_number, 'message': message})
    return phone_numbers


@task()
def scrape_gmail_messages(email, access_oauth_token, access_oauth_token_secret, consumer_key, consumer_secret):
    consumer = oauth.Consumer(consumer_key, consumer_secret)
    token = oauth.Token(access_oauth_token, access_oauth_token_secret)
    client = oauth.Client(consumer, token)
    
    # TODO: Get the email from Google contacts
    print client.request('https://www.google.com/m8/feeds/contacts/default/full?max-results=1')
    
    url = 'https://mail.google.com/mail/b/%s/imap/' % email
    imap = imaplib.IMAP4_SSL('imap.googlemail.com')
    imap.authenticate(url, consumer, token)
    
    # TODO: Handle bad resp
    resp, message_count = imap.select()
    message_count = int(message_count[0])
    print "Message count: %d" % message_count
    
    # TODO: Handle bad resp
    resp, messages = imap.search(None, 'ALL')
    messages = messages[0].split()
    
    # Find the phone numbers in each message
    phone_numbers = []
    for index in range(message_count):
        phone_numbers += find_phone_numbers(imap, messages[index])
    
    imap.logout()
    return phone_numbers
