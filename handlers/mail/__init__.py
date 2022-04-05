# -*- coding: utf-8 -*-

import email
import email.header
import email.utils
import http.client
import dateutil.parser


import config
import modules.mongo as mod_mongo
import util.defer


import util.handler


class Handler(util.handler.Handler):
    def __call__(self):
        msg = email.message_from_bytes(self.req.request_body)

        def decode_header(val):
            return ''.join([header_value if isinstance(header_value, str) else header_value.decode(header_encoding or 'ascii') for header_value, header_encoding in email.header.decode_header(val)])

        messageId = msg.get('Message-ID')
        if messageId is None:
            raise HandlerError('Message-ID header is missing')
        messageDate = msg.get('Date')
        if messageDate is None:
            raise HandlerError('Date header is missing')
        try:
            messageDate = dateutil.parser.parse(messageDate)
        except ValueError:
            raise HandlerError('Date header has incorrect value', messageDate)
        messageFrom = msg.get('From')
        if messageFrom is not None:
            messageFromName, messageFromAddress = email.utils.parseaddr(decode_header(messageFrom))
        else:
            messageFromName, messageFromAddress = None, None
        messageTo = msg.get('To')
        if messageTo is not None:
            messageToName, messageToAddress = email.utils.parseaddr(decode_header(messageTo))
        else:
            messageToName, messageToAddress = None, None
        messageSubject = decode_header(msg.get('Subject'))

        # Check mailbox config and find
        route_mailbox = None
        if messageToAddress is not None:
            for mailbox, mailbox_cfg in config.mail.mailboxes.items():
                mailbox_email = mailbox_cfg.get('email')
                if mailbox_email is not None and mailbox_email == messageToAddress:
                    route_mailbox = mailbox
                    break

        if route_mailbox is not None:
            db_doc = mod_mongo.bson.son.SON()
            db_doc['_id'] = messageId
            db_doc['date'] = messageDate
            if messageFrom is not None:
                db_doc['from'] = mod_mongo.bson.son.SON((('name', messageFromName), ('email', messageFromAddress)))
            if messageTo is not None:
                db_doc['to'] = mod_mongo.bson.son.SON((('name', messageToName), ('email', messageToAddress)))
            if messageSubject is not None:
                db_doc['subject'] = messageSubject
            db_doc['raw'] = mod_mongo.bson.binary.Binary(self.req.request_body)

            with mod_mongo.DbSessionController() as db_session:
                try:
                    db_session[config.db_mongo.name]['mailbox.%s' % mailbox].insert_one(db_doc)
                except mod_mongo.pymongo.errors.DuplicateKeyError:
                    pass

            # Queue a task to process a message from the mailbox
            util.defer.the_app.send_task('handlers.defer.mail.%s.Process' % mailbox, args=(messageId, ))

        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Content-Type', 'text/plain; charset=utf-8')
        self.req.write('Mail processed')


class HandlerError(util.handler.HandlerError):
    pass
