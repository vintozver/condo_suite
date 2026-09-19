# -*- coding: utf-8 -*-

import typing
from . import view
from ....modules.mongo import agent as mod_mongo_agent
from ....modules.mongo import user as mod_mongo_user
from ....handlers.web import skeleton as mod_tmpl


class ViewHandler(view.ViewHandler):
    def check_permissions(self, agent: mod_mongo_agent.AgentDocument, user: mod_mongo_user.UserDocument) -> bool:
        txn_options = self.txn.options
        # check agent
        if agent is None:
            return False
        try:
            txn_id_agent = txn_options.get('agent', {}).get('_id')
        except KeyError:
            txn_id_agent = None
        if not txn_id_agent or not agent.id or txn_id_agent != agent.id:
            return False
        # check user
        if user is None:
            return False
        try:
            txn_id_user = txn_options.get('user', {}).get('_id')
        except KeyError:
            txn_id_user = None
        if not txn_id_user or not user.id or txn_id_user != user.id:
            return False

        return True

    def render_object(self) -> typing.Any:
        txn = self.txn
        txn_options = txn.options

        def yield_entities(entities):
            for entity_type, entity_id in entities:
                yield {
                    'type': entity_type,
                    'id': str(entity_id),
                }

        return {
            'type': txn.type,
            'state': txn.state,
            'last_mod': txn.last_mod.isoformat(),
            'options': {
                'entities': list(yield_entities(txn_options['items'])),
            }
        }

    def render_form(self, req) -> str:
        txn = self.txn
        txn_options = txn.options
        tmpl_args = dict()
        tmpl_args['txn'] = txn
        tmpl_args['entities'] = txn_options['items']
        return mod_tmpl.TemplateFactory(req, 'transaction.link').render(tmpl_args)
