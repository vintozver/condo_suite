# -*- coding: utf-8 -*-

import datetime

from ... import config
from ...modules import mongo as mod_mongo
from ...modules.mongo import transaction as mod_mongo_transaction
from ...util.defer import the_app
from . import Transaction


class CaseLink(Transaction):
    @classmethod
    def type(cls):
        return 'case_link'

    def commit(self, txn):
        options = txn.options or {}
        try:
            case_ids = options['cases']
        except (KeyError, TypeError):
            return False, 'Invalid case link options'
        if len(case_ids) < 2 or len(set(case_ids)) != len(case_ids):
            return False, 'At least two different cases are required'
        comment = options.get('comment')
        if not isinstance(comment, str) or not comment:
            return False, 'A comment is required'

        with mod_mongo.DbSessionController() as db_session:
            collection = db_session[config.name]['case']
            if collection.count_documents({'_id': {'$in': case_ids}}) != len(case_ids):
                return False, 'Case not found'
            for case_id in case_ids:
                history = [{
                    'dt': datetime.datetime.now(datetime.timezone.utc),
                    'comment': comment,
                    'link': other_id,
                } for other_id in case_ids if other_id != case_id]
                collection.update_one(
                    {'_id': case_id, 'pending_txns': {'$ne': txn.id}},
                    {'$push': {'history': {'$each': history}},
                     '$addToSet': {'pending_txns': txn.id}},
                )
        return True

    def cleanup(self, txn):
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.name]['case'].update_many(
                {'pending_txns': txn.id}, {'$pull': {'pending_txns': txn.id}})

    def rollback(self, txn):
        options = txn.options or {}
        try:
            case_ids = options['cases']
        except (KeyError, TypeError):
            return
        comment = options.get('comment')
        with mod_mongo.DbSessionController() as db_session:
            collection = db_session[config.name]['case']
            for case_id in case_ids:
                other_ids = [other_id for other_id in case_ids if other_id != case_id]
                collection.update_one(
                    {'_id': case_id, 'pending_txns': txn.id},
                    {'$pull': {
                        'history': {'comment': comment, 'link': {'$in': other_ids}},
                        'pending_txns': txn.id,
                    }},
                )


CaseLink.register()


def case_link(case_ids, comment):
    """Create a `case_link` transaction and enqueue it for processing.

    `case_ids` must contain at least two distinct case ObjectIds; `comment` is required.
    Returns the id of the created transaction.
    """
    if len(case_ids) < 2 or len(set(case_ids)) != len(case_ids):
        raise ValueError('At least two different cases are required')
    if not isinstance(comment, str) or not comment:
        raise ValueError('A comment is required')

    txn = mod_mongo_transaction.Transaction(type=CaseLink.type(), options={'cases': case_ids, 'comment': comment})
    txn.save()
    the_app.send_task('handlers.defer.TransactionProcessor', kwargs={'id_txn': txn.id})
    return txn.id
