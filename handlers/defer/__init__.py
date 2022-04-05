# -*- coding: utf-8 -*-


import typing
import datetime
import modules.mongo as mod_mongo
import modules.mongo.transaction as mod_mongo_transaction
import config
import util.defer


transaction_class_registry = dict()  # type: typing.Mapping


class Transaction(util.defer.Task):
    abstract = True
    ignore_result = True

    @classmethod
    def register(cls):
        try:
            txn_type = cls.type()
        except NotImplementedError:
            txn_type = None

        if txn_type is not None:
            if txn_type in transaction_class_registry:
                raise RuntimeError('Duplicate Transaction.type() detected', txn_type)

            transaction_class_registry[txn_type] = cls

    # @classmethod
    # def retry(self, txn):
    #     raise TransactionRetryError()

    def run(self, id_txn, action='acquire'):
        txn = mod_mongo_transaction.Transaction.objects(id=id_txn).get()
        if txn.type != self.type():
            raise TransactionError('Unexpected transaction type', txn.type)
        txn_state = txn.state
        # txn state is volatile and should not be considered accurate beyond this point.
        # We can only use it as a reference point but should always use atomic check and modify if necessary
        if txn_state == 'initial':
            if self.handle_acquire(txn):
                return self.handle_commit(txn)
        elif txn_state == 'pending':
            if action in ('commit', ):
                return self.handle_commit(txn)
        elif txn_state == 'applied':
            if action in ('complete', 'recover'):
                return self.handle_complete(txn)
        elif txn_state == 'cancelling':
            if action in ('cancel', 'recover'):
                return self.handle_cancel(txn)
        elif txn_state in ('completed', 'cancelled'):
            pass
        else:
            raise TransactionError('Unexpected transaction state', txn_state)

    def handle_acquire(self, txn):  # must be called by run method only
        with mod_mongo.DbSessionController() as db_session:
            db_res = db_session[config.db_mongo.name]['transaction'].update_one(
                mod_mongo.bson.son.SON([('_id', txn.id), ('type', self.type()), ('state', 'initial')]),
                {'$set': {'state': 'pending', 'last_mod': datetime.datetime.utcnow()}},
            )
        if db_res.matched_count <= 0:
            return False
        return self.run(txn.id, 'commit')  # this simple call may be replaced by task invocation if necessary

    def handle_commit(self, txn):  # must be called by run or handle_commit methods only
        commit_result = self.commit(txn)
        if commit_result is None:
            ok = True
            reason = ''
        elif isinstance(commit_result, bool):
            ok = commit_result
            reason = ''
        else:
            ok = commit_result[0]
            reason = commit_result[1]

        if ok:
            with mod_mongo.DbSessionController() as db_session:
                db_res = db_session[config.db_mongo.name]['transaction'].update_one(
                    mod_mongo.bson.son.SON([('_id', txn.id), ('type', self.type()), ('state', 'pending')]),
                    {'$set': {'state': 'applied', 'last_mod': datetime.datetime.utcnow()}},
                )
            if db_res.matched_count:
                return self.run(txn.id, 'complete')  # this simple call may be replaced by task invocation if necessary
            else:
                return False
        else:
            with mod_mongo.DbSessionController() as db_session:
                db_res = db_session[config.db_mongo.name]['transaction'].update_one(
                    mod_mongo.bson.son.SON([('_id', txn.id), ('type', self.type()), ('state', 'pending')]),
                    {'$set': {
                        'state': 'cancelling', 'last_mod': datetime.datetime.utcnow(),
                        'reason_to_cancel': reason
                    }},
                )
            if db_res.matched_count:
                return self.run(txn.id, 'cancel')  # this simple call may be replaced by task invocation if necessary
            else:
                return False

    def handle_complete(self, txn):  # must be called by run method only
        self.cleanup(txn)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['transaction'].update_one(
                mod_mongo.bson.son.SON([('_id', txn.id), ('type', self.type()), ('state', 'applied')]),
                {'$set': {'state': 'completed', 'last_mod': datetime.datetime.utcnow()}},
            )
        txn.reload()
        self.on_complete(txn)

    def handle_cancel(self, txn):
        self.rollback(txn)
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['transaction'].update_one(
                mod_mongo.bson.son.SON([('_id', txn.id), ('type', self.type()), ('state', 'cancelling')]),
                {'$set': {'state': 'cancelled', 'last_mod': datetime.datetime.utcnow()}},
            )
        txn.reload()
        self.on_cancel(txn)

    # Implementation interface

    @classmethod
    def type(cls) -> str:
        raise NotImplementedError

    def commit(self, txn: mod_mongo_transaction.Transaction) -> bool:
        raise NotImplementedError

    def cleanup(self, txn: mod_mongo_transaction.Transaction) -> None:
        raise NotImplementedError

    def rollback(self, txn: mod_mongo_transaction.Transaction) -> None:
        raise NotImplementedError

    def on_complete(self, txn: mod_mongo_transaction.Transaction) -> None:
        pass

    def on_cancel(self, txn: mod_mongo_transaction.Transaction) -> None:
        pass


class TransactionError(Exception):
    pass


class TransactionRetryError(TransactionError):
    pass


class TransactionProcessor(util.defer.Task):
    ignore_result = True

    def run(self, id_txn, action='acquire'):
        oid_txn = mod_mongo.bson.ObjectId(id_txn)
        txn = mod_mongo_transaction.Transaction.objects(id=oid_txn).get()
        if txn is None:
            raise TransactionError('Transaction not found', id_txn)

        txn_type = txn.type
        try:
            txn_cls = transaction_class_registry[txn_type]
        except KeyError:
            raise TransactionError('Transaction type is unknown or not registered', txn_type)

        util.defer.the_app.send_task('%s.%s' % (txn_cls.__module__, txn_cls.__name__), kwargs={
            'id_txn': oid_txn,
            'action': action,
        })


__all__ = ['Transaction', 'TransactionError', 'TransactionProcessor']
