# -*- coding: utf-8 -*-
import socket
#import threading

import datetime
import re
import imaplib
import sys
from email.parser import HeaderParser
from dateutil.parser import parse

from models import *
import settings
from utils import num, uniqify

nanp_pattern = '(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?'
number_re = re.compile(nanp_pattern)
email_re = re.compile('("?([a-zA-Z 0-9\._\-]+)"?\s+)?<?([a-zA-Z0-9\._\-]+@[a-zA-Z0-9\._\-]+)>?')


class Analizer:
    found_phones = 0

    def __init__(self, imap, number, user, mailbox):
        #threading.Thread.__init__(self)
        self.number = number
        self.imap = imap
        self.user = user
        self.mailbox = mailbox

    def search_phone(self):
        print 'processing message num: ' + str(self.number)
        try:
            response, message_data = self.imap.fetch(self.number, '(BODY.PEEK[HEADER])')
        except:
            print "Exception in HEADER"
            return False

        raw_message = message_data[0][1] # message_data, the data structure returned by imaplib, encodes some data re: the request type
        header = HeaderParser().parsestr(raw_message)

        if header['Content-Type'] is not None and 'multipart' in header['Content-Type']:
            print "INcorrect content type"
            return False # right now we're just skipping any multipart messages. this needs to be rewritten to parse the text parts of said messgs.
        try:
            response, message_data = self.imap.fetch(self.number, '(BODY.PEEK[TEXT])')
        except:
            print "Exception in TEXT"
            return False

        text_payload = message_data[0][1]
        found_digits = number_re.findall(text_payload)
        found_digits += number_re.findall(header['Subject'])

        if len(found_digits) > 0:
            print "Message %d has numbers." % num(self.number)
            print found_digits
            ### need to cast the Date header into a MySQL object.
            ts = header['Date']
            print 'header date: ' + str(ts)
            if parse(ts) is not None: #making sure the date header is not empty
                date = parse(ts)

            print 'about to insert into the database'
            ### sometimes it fails due to unicode issues
            print 'about to parse name and email from header'
            print 'header: ' + str(header['From'])
            try:
                name, email = email_re.match(header['From']).groups()[1:3]
            except:
                print "Unexpected error:", sys.exc_info()[0]
                return False
            print 'parsing name and email from FROM header: ' + str(name) + ', ' + str(email)

            try:
                m = Message(
                    user=self.user,
                    sender=header['From'][:255],
                    recipient=header['To'][:255],
                    sender_name=str(name)[:255],
                    sender_email=email[:255],
                    subject=header['Subject'][:255],
                    date_add=date,
                    payload=str(text_payload[:65534])
                )
                m.save()
            except Exception as e:
                print "Can't save", "test", e
            pure_digits = uniqify(map(''.join, found_digits)) # the phone number regexp will create lists like ['','650','555','1212']. this collapses the list into a string.

            print 'We found pure digits: ' + str(pure_digits)
            for phone_number in pure_digits:
                if len(str(phone_number)) > 7:  # for now, we want numbers with area codes only.
                    print phone_number
                    PhoneNumber(value=phone_number, message=m, user=self.user, mailbox=self.mailbox).save()
                    self.found_phones += 1


class IMAPConnecter:
    def __init__(self, host, port, email=False, password=False, ssl=True):
        self.email = email
        self.password = password
        self.host = host
        self.port = port
        self.ssl = ssl
        self.mail_count = 0

    def get_connection(self):
        print self.host, self.port
        imap = imaplib.IMAP4_SSL(self.host, self.port)
        imap.login(self.email, self.password)
        response, mail_count = imap.select()
        self.mail_count = int(mail_count[0])
        return imap

    def get_outh_connection(self, consumer, token):
        import oauth2.clients.imap as imaplib
        url = "https://mail.google.com/mail/b/%s/imap/" % self.email
        conn = imaplib.IMAP4_SSL('imap.googlemail.com')
        #conn.debug = 4
        conn.authenticate(url, consumer, token)
        response, mail_count = conn.select()
        self.mail_count = int(mail_count[0])
        return conn

    def check_connection(self):
        u'''
            Checker if servers host, port correct.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self.host, self.port))
            s.shutdown(2)
            return True
        except:
            return False

    def get_mail_count(self):
        return self.mail_count


class Scraper:
    u'''
        port 993 - SSL connection
        port 143 - simple connection (unsecured)
    '''
    def __init__(self, host, user, email, password=False, oauth_token=False, oauth_secret=False, port=993, ssl=True):
        self.email = email
        self.password = password
        self.host = host
        self.port = port
        self.user = user
        self.oauth_token = oauth_token
        self.oauth_secret = oauth_secret
        self.analizers = []

    def run(self):
        if self.oauth_token and self.oauth_secret:
            print 'Connecting to the Google IMAP server with oauth'
            import oauth2 as oauth

            consumer = oauth.Consumer(settings.GOOGLE_TOKEN, settings.GOOGLE_SECRET)
            token = oauth.Token(self.oauth_token, self.oauth_secret)
            conn = IMAPConnecter(self.host, self.port, self.email)
            imap = conn.get_outh_connection(consumer, token)
        else:
            print 'Connecting to the Google IMAP server with credentials'
            conn = IMAPConnecter(self.host, self.port, self.email, self.password)
            imap = conn.get_connection()

        print "Messages to process: %d" % conn.get_mail_count()

        response, list_of_messages = imap.search(None, 'ALL')
        mlist = list_of_messages[0].split()
        mailbox = MailBox.objects.get(username=self.email)

        phones = 0
        for item in range(0, conn.get_mail_count()):
            analizer = Analizer(imap, mlist[item], self.user, mailbox)
            analizer.search_phone()
            phones += analizer.found_phones
        print phones
        
        return phones
