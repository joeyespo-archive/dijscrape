"""\
Helper.py

Helper functions for the current Flask web application.
"""

import os
import logging
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
from logging.handlers import SMTPHandler
from flask import url_for, current_app, safe_join


def send_email(email_info, to, subject, body, attach=None):
    """Send an email to one or more recipients."""
    # TODO: Clean this function up
    if not isinstance(to, basestring):
        for single_to in to:
            send_email(email_info, single_to, subject, body)
        return
    (mailhost, mailport), login_info, address = email_info
    msg = MIMEMultipart()
    msg['From'] = address
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body))
    if attach:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(open(attach, 'rb').read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attach))
        msg.attach(part)
    mailServer = smtplib.SMTP(mailhost, mailport or smtplib.SMTP_PORT)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    if login_info:
        username, password = login_info
        mailServer.login(username, password)
    mailServer.sendmail(address, to, msg.as_string())
    # Should be mailServer.quit(), but that crashes...
    mailServer.close()


def email_errors(app, email_info=None, subject=None, admins=None, error_level=logging.ERROR):
    """Enables error reporting using SMTP for the provided app."""
    if not email_info:
        email_info = app.config.get('ERROR_EMAIL_INFO')
    if not email_info:
        return
    subject = subject or app.config.get('ERROR_EMAIL_SUBJECT', 'Error')     # TODO: Use more sensible default
    to_addresses = admins or app.config.get('ADMINS', [])                   # TODO: Make this better
    (mailhost, mailport), credentials, from_address = email_info
    mail_handler = TlsSMTPHandler(mailhost, from_address, to_addresses, subject, credentials)
    if error_level:
        mail_handler.setLevel(error_level)
    app.logger.addHandler(mail_handler)


class TlsSMTPHandler(SMTPHandler):
    """A TLS implementation of SMTPHandler."""
    
    # TODO: Merge with send_mail
    
    def emit(self, record):
        """
        Emit a record.
        
        Format the record and send it to the specified addressees.
        """
        try:
            import string
            try:
                from email.utils import formatdate
            except ImportError:
                formatdate = self.date_time
            port = self.mailport or smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port)
            msg = self.format(record)
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (self.fromaddr, string.join(self.toaddrs, ","), self.getSubject(record), formatdate(), msg)
            # --- Begin TLS support ---
            if self.username:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(self.username, self.password)
            # --- End TLS support ---
            smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
