import logging
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders


class GmailHandler(logging.Handler):
    def __init__(self, gmail_user, gmail_password, toaddrs, subject, level=logging.ERROR):
        logging.Handler.__init__(self, level or logging.NOTSET)
        self.gmail_user = gmail_user
        self.gmail_password = gmail_password
        self.toaddrs = toaddrs
        self.subject = subject
    
    def emit(self, record):
        text = self.format(record)
        send_gmail(self.gmail_user, self.gmail_password, self.toaddrs, self.subject, text)


def send_gmail(gmail_user, gmail_password, to, subject, text, attach = None):
    if not isinstance(to, basestring):
        for single_to in to:
            send_gmail(gmail_user, gmail_password, single_to, subject, text)
        return
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(text))
    if attach:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(open(attach, 'rb').read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attach))
        msg.attach(part)
    mailServer = smtplib.SMTP("smtp.gmail.com", 587)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(gmail_user, gmail_password)
    mailServer.sendmail(gmail_user, to, msg.as_string())
    # Should be mailServer.quit(), but that crashes...
    mailServer.close()
