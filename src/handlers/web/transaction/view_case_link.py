# -*- coding: utf-8 -*-

import typing
from . import view
from ....modules.mongo import agent as mod_mongo_agent
from ....modules.mongo import user as mod_mongo_user
from ....handlers.web import skeleton as mod_tmpl


class ViewHandler(view.ViewHandler):
    def check_permissions(self, agent: mod_mongo_agent.AgentDocument, user: mod_mongo_user.UserDocument) -> bool:
        txn_options = self.txn.options
        try:
            creator = txn_options['creator']
        except (KeyError, TypeError):
            creator = {}
        # check agent
        if agent is None:
            return False
        try:
            txn_id_agent = creator.get('agent', {}).get('_id')
        except AttributeError:
            txn_id_agent = None
        if not txn_id_agent or not agent.id or txn_id_agent != agent.id:
            return False
        # check user
        if user is None:
            return False
        try:
            txn_id_user = creator.get('user', {}).get('_id')
        except AttributeError:
            txn_id_user = None
        if not txn_id_user or not user.id or txn_id_user != user.id:
            return False

        return True

    def render_object(self) -> typing.Any:
        txn = self.txn
        txn_options = txn.options

        def render_ref(ref):
            if not ref:
                return None
            return {key: str(value) if key == '_id' else value for key, value in ref.items()}

        creator = txn_options['creator']

        return {
            'type': txn.type,
            'state': txn.state,
            'last_mod': txn.last_mod.isoformat(),
            'options': {
                'cases': [str(case_id) for case_id in txn_options['cases']],
                'comment': txn_options['comment'],
                'creator': {
                    'agent': render_ref(creator.get('agent')),
                    'user': render_ref(creator.get('user')),
                },
            }
        }

    def render_form(self, req) -> str:
        txn = self.txn
        txn_options = txn.options
        tmpl_args = dict()
        tmpl_args['txn'] = txn
        tmpl_args['cases'] = txn_options['cases']
        tmpl_args['comment'] = txn_options['comment']
        tmpl_args['creator'] = txn_options['creator']
        return mod_tmpl.TemplateFactory(req, 'transaction.case_link').render(tmpl_args)
