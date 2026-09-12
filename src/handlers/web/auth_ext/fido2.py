# -*- coding: utf-8 -*-

import base64
import http.client
import json
import urllib.parse

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AttestationConveyancePreference,
    AuthenticatorData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    UserVerificationRequirement,
)

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


def _server(req):
    host = req.getHeader('Host')
    rp_id = urllib.parse.urlsplit('//%s' % host).hostname
    rp = PublicKeyCredentialRpEntity(name=config.business_name, id=rp_id)
    scheme = 'https' if req.isSecure() else 'http'
    return Fido2Server(
        rp=rp,
        attestation=AttestationConveyancePreference.ENTERPRISE,
        verify_origin=lambda origin: origin == '%s://%s' % (scheme, host)
    )


def _json(value):
    # This JSON is embedded in an HTML script block by the authentication page.
    return json.dumps(dict(value)).replace('<', '\\u003c')


def authentication_begin(req, session):
    options, state = _server(req).authenticate_begin()
    session['fido2_state'] = {'purpose': 'authenticate', 'state': state}
    session.save()
    return _json(options.public_key)


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
                credentials = [
                    PublicKeyCredentialDescriptor(type=PublicKeyCredentialType.PUBLIC_KEY, id=c.id)
                    for c in session_user.fido2_credentials
                ]
                options, state = _server(self.req).register_begin(
                    user=user, credentials=credentials, user_verification=UserVerificationRequirement.PREFERRED
                )
                session['fido2_state'] = {'purpose': 'register', 'state': state}
                session.save()
                response = _json(options.public_key)
            else:
                response = authentication_begin(self.req, session)
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
                auth_data = _server(self.req).register_complete(pending['state'], response)
                credential = auth_data.credential_data
                if credential is None:
                    raise HandlerError('FIDO2 response did not contain credential data')
                with mod_mongo.DbSessionController() as db_session:
                    db_session[config.name]['users'].update_one(
                        {'_id': session_user.id, 'fido2_credentials.id': {'$ne': credential.credential_id}},
                        {'$push': {'fido2_credentials': {
                            'id': credential.credential_id,
                            'data': bytes(credential),
                            'aaguid': credential.aaguid,
                            'sign_count': auth_data.counter,
                        }}},
                    )
                response = {}
            else:
                credential_id = _unb64(response['id'])
                credentials = []
                users = mod_mongo_user.UserDocument.objects(fido2_credentials__id=credential_id)
                for user in users:
                    credentials.extend(user.fido2_credentials)
                if not credentials:
                    raise HandlerError('Unknown FIDO2 credential')
                credential = _server(self.req).authenticate_complete(
                    state=pending['state'],
                    credentials=[AttestedCredentialData(c.data) for c in credentials],
                    response=response,
                )
                user = next(user for user in users if any(c.id == credential.credential_id for c in user.fido2_credentials))
                session['id_user'] = user.id
                session.save()
                sign_count = AuthenticatorData(_unb64(response['response']['authenticatorData'])).counter
                with mod_mongo.DbSessionController() as db_session:
                    db_session[config.name]['users'].update_one(
                        {'_id': user.id, 'fido2_credentials.id': credential.credential_id},
                        {'$set': {'fido2_credentials.$.sign_count': sign_count}},
                    )
                response = {}
        self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'no-store')
        self.req.setHeader('Content-Type', 'application/json; charset=utf-8')
        self.req.write(json.dumps(response))
