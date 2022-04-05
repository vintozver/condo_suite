#!/usr/bin/env python



import imaplib
import util.web.request
import io

import config


class MailboxProcessorError(Exception):
    pass


class MailboxProcessor(object):
    def __init__(self, mailbox, imap_handle):
        self.mailbox = mailbox  # may be used for routing purposes
        self.imap_handle = imap_handle

    def process(self):
        return self.process_mailbox()

    def process_mailbox(self):
        logging.info('MailboxProcessor: %s', 'Processing mailbox')
        retcode, messages = self.imap_handle.search(None, '(UNSEEN)')
        if retcode == 'OK':
            messages = messages[0].split()
            for message in messages:
                fetch_code, fetch_data = self.imap_handle.fetch(message, '(RFC822)')
                if fetch_code == 'OK':
                    logging.debug('MailoxProcessor: %s', 'Request invocation')
                    req = util.web.request.Request({'wsgi.input': io.BytesIO(fetch_data[0][1])})
                    import handlers.mail
                    try:
                        handlers.mail.Handler(req)()
                    except handlers.mail.HandlerError as err:
                        sys.stderr.write('Error processing the request: %s\n' % repr(err))


if __name__ == '__main__':
    import logging
    import sys
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    del ch
    del logger

    import argparse
    parser = argparse.ArgumentParser(prog='[IMAP Listener]')
    parser.add_argument('--mailbox', required=True)
    args_parsed = parser.parse_args(sys.argv[1:], )

    try:
        mailbox_details = config.mail.mailboxes[args_parsed.mailbox]
    except KeyError:
        raise RuntimeError('Mailbox connection params not found')

    logging.debug('Mailbox connection: %s', repr(mailbox_details))

    M = imaplib.IMAP4_SSL(mailbox_details['host'], mailbox_details.get('port', imaplib.IMAP4_SSL_PORT))
    logging.info('%s', 'Connected to mailbox')
    try:
        M.login(mailbox_details['user'], mailbox_details['password'])
        logging.info('%s', 'Authenticated')
        M.select('INBOX')
        MailboxProcessor(args_parsed.mailbox, M).process()
    finally:
        logging.info('%s', 'Closing the mailbox')
        M.close()
        logging.info('%s', 'Disconnecting from mailbox')
        M.logout()

