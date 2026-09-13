# -*- coding: utf-8 -*-

import datetime

from ... import config
from ...modules import mongo as mod_mongo
from . import Transaction


class CaseLink(Transaction):
    @classmethod
    def type(cls):
        return 'case_link'

    def commit(self, txn):
        options = txn.options or {}
        try:
            first = mod_mongo.bson.ObjectId(options['case'])
            second = mod_mongo.bson.ObjectId(options['linked_case'])
        except (KeyError, TypeError, ValueError):
            return False, 'Invalid case link options'
        if first == second:
            return False, 'A case cannot be linked to itself'
        comment = options.get('comment')
        if not isinstance(comment, str) or not comment:
            return False, 'A comment is required'

        with mod_mongo.DbSessionController() as db_session:
            collection = db_session[config.name]['case']
            for case_id, other_id in ((first, second), (second, first)):
                item = {
                    'dt': datetime.datetime.utcnow(),
                    'comment': comment,
                    'linked_case_id': other_id,
                }
                result = collection.update_one(
                    {'_id': case_id, 'transactions': {'$elemMatch': {'_id': txn.id, 'state': 'pending'}}},
                    {'$push': {'history': item},
                     '$set': {'transactions.$.state': 'applied'}},
                )
                if not result.matched_count:
                    existing = collection.find_one({
                        '_id': case_id,
                        'history': {'$elemMatch': {'comment': comment, 'linked_case_id': other_id}},
                    })
                    if existing is None:
                        return False, 'Case link is not pending'
        return True

    def cleanup(self, txn):
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['case'].update_many(
                {'transactions': {'$elemMatch': {'_id': txn.id}}},
                {'$pull': {'transactions': {'_id': txn.id}}},
            )

    def rollback(self, txn):
        # A link is only visible after both case records have been updated.
        self.cleanup(txn)


CaseLink.register()
