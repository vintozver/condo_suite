# -*- coding: utf-8 -*-

import base64
import http.client
import json

import fido2.features
from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticatorData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

fido2.features.webauthn_json_mapping.enabled = True

from .... import config
from ....handlers.ext.paramed_cgi import Handler as _Handler, HandlerError as _HandlerError
from ....handlers.web import decorator as deco
from ....modules import mongo as mod_mongo
from ....modules.mongo import user as mod_mongo_user


class HandlerError(_HandlerError):
    pass


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def _server():
    rp = PublicKeyCredentialRpEntity(config.fido2_rp_name, config.fido2_rp_id)
    return Fido2Server(rp, verify_origin=lambda origin: origin == config.fido2_origin)


def _json(value):
    return json.dumps(dict(value))


class Handler(_Handler):
    @deco.session.Session()
    @deco.session.SessionUser()
    def __call__(self):
        session = self.req.context.session
        session_user = self.req.context.session_user
        try:
            operation = self.cgi_params.param_get('op') if self.req.method == 'GET' else None
        except self.cgi_params.NotFoundError:
            operation = None
        if self.req.method == 'GET':
            if operation == 'register':
                if session_user is None:
                    raise HandlerError('Authentication is required to register a credential')
                user = PublicKeyCredentialUserEntity(
                    name=session_user.email or str(session_user.id),
                    id=session_user.id.binary,
                    display_name=session_user.name,
                )
                credentials = [PublicKeyCredentialDescriptor(c.credential_id) for c in session_user.fido2]
                options, state = _server().register_begin(
                    user, credentials, user_verification=UserVerificationRequirement.PREFERRED
                )
                session['fido2_state'] = {'purpose': 'register', 'state': state}
            else:
                options, state = _server().authenticate_begin()
                session['fido2_state'] = {'purpose': 'authenticate', 'state': state}
            session.save()
            response = _json(options.public_key)
        else:
            try:
                body = json.loads(self.req.request_body.decode('utf-8'))
                pending = session.pop('fido2_state')
            except (ValueError, KeyError, TypeError):
                raise HandlerError('No FIDO2 ceremony is pending')
            response = body.get('response', body)
            if pending['purpose'] == 'register':
                if session_user is None:
                    raise HandlerError('Authentication is required to register a credential')
                auth_data = _server().register_complete(pending['state'], response)
                credential_data = auth_data.credential_data
                if credential_data is None:
                    raise HandlerError('FIDO2 response did not contain credential data')
                with mod_mongo.DbSessionController() as db_session:
                    db_session[config.name]['users'].update_one(
                        {'_id': session_user.id, 'fido2.credential_id': {'$ne': credential_data.credential_id}},
                        {'$push': {'fido2': {
                            'credential_id': credential_data.credential_id,
                            'credential_data': bytes(credential_data),
                            'sign_count': auth_data.counter,
                        }}},
                    )
                response = {}
            else:
                credential_id = _unb64(response['id'])
                credentials = []
                users = mod_mongo_user.UserDocument.objects(fido2__credential_id=credential_id)
                for user in users:
                    credentials.extend(user.fido2)
                if not credentials:
                    raise HandlerError('Unknown FIDO2 credential')
                credential = _server().authenticate_complete(
                    pending['state'],
                    [AttestedCredentialData(c.credential_data) for c in credentials],
                    response,
                )
                user = next(user for user in users if any(c.credential_id == credential.credential_id for c in user.fido2))
                session['id_user'] = user.id
                session.save()
                sign_count = AuthenticatorData(_unb64(response['response']['authenticatorData'])).counter
                with mod_mongo.DbSessionController() as db_session:
                    db_session[config.name]['users'].update_one(
                        {'_id': user.id, 'fido2.credential_id': credential.credential_id},
                        {'$set': {'fido2.$.sign_count': sign_count}},
                    )
                response = {}
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'no-store')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(response))
