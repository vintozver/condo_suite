# -*- coding: utf-8 -*-

import http.client
import json
import oauth2client.client
import config
import handlers.web.skeleton as mod_tmpl
import modules.mongo as mod_mongo
import handlers.web.decorator as deco
import handlers.ext.paramed_cgi


class HandlerError(handlers.ext.paramed_cgi.HandlerError):
    pass


class Handler(handlers.ext.paramed_cgi.Handler):
    @deco.session.Session()
    def process_authentication(self):
        session = self.req.context.session

        credentials = self.get_stored_credentials('authentication')
        if credentials is None:
            raise HandlerError('The session does not have stored credentials to proceed with authentication.')

        id_user = session.get('id_user')
        if id_user is not None:
            raise HandlerError('User merging and alteration is not supported.')

        id_token = credentials.id_token
        google_email = id_token.get('email')
        google_email_verified = id_token.get('email_verified')
        if not google_email or not google_email_verified:
            raise HandlerError('Only accounts with linked and verified email are accepted.')

        with mod_mongo.DbSessionController() as db_session:
            user_doc = db_session[config.db_mongo.name]['users'].find_one({'ext.google.email': google_email}, {'_id': True})
            if user_doc is not None:
                session['id_user'] = user_doc['_id']
                try:
                    del session['id_agent']
                except KeyError:
                    pass
                session.save()
            else:
                raise HandlerError('No user with corresponding account found.')

    def calc_perms(self, purpose, **kwargs):
        if purpose == 'authentication':
            perms = ['email']
        elif purpose == 'drive_files':
            perms = ['https://www.googleapis.com/auth/drive.file']
        else:
            raise HandlerError('Unknown purpose', purpose)
        return perms

    @deco.session.Session()
    def get_stored_credentials(self, purpose):
        credentials = self.req.context.session.get('ext', {}).get('google', {}).get('credentials', {}).get(purpose, None)
        if credentials is not None:
            return oauth2client.client.OAuth2Credentials(credentials.get('access_token'), config.google.client_id, config.google.client_secret, credentials.get('refresh_token'),
                                                         credentials.get('token_expiry'), 'https://accounts.google.com/o/oauth2/token', None, id_token=credentials.get('id_token'),
                                                         )

    @deco.session.Session()
    def store_credentials(self, purpose, credentials):
        req_session = self.req.context.session

        db_doc = dict()
        access_token = credentials.access_token
        if access_token:
            db_doc['access_token'] = access_token
        refresh_token = credentials.refresh_token
        if refresh_token:
            db_doc['refresh_token'] = refresh_token
        token_expiry = credentials.token_expiry
        if token_expiry:
            db_doc['token_expiry'] = token_expiry
        id_token = credentials.id_token
        if id_token:
            db_doc['id_token'] = id_token
        # save token to the session
        with mod_mongo.DbSessionController() as db_session:
            db_session[config.db_mongo.name]['sessions'].update({'_id': req_session.id}, {'$set': {('data.ext.google.credentials.%s' % purpose): db_doc}})
        # refresh the session because we updated the database externally
        req_session.load(req_session.id, req_session.hash)

    def redirect_authorization(self, purpose, return_url):
        flow = oauth2client.client.OAuth2WebServerFlow(config.google.client_id, config.google.client_secret,
                                                       self.calc_perms(purpose),
                                                       config.google.redirect_uri,
                                                       auth_uri='https://accounts.google.com/o/oauth2/auth',
                                                       token_uri='https://accounts.google.com/o/oauth2/token',
                                                       )
        flow.params['access_type'] = 'offline'
        flow.params['approval_prompt'] = 'force'
        flow.params['state'] = json.dumps({'purpose': purpose, 'return_url': return_url})
        url = flow.step1_get_authorize_url()
        del flow

        content = content = mod_tmpl.TemplateFactory(self.req, 'auth_ext.google').render({'view': 'redirect_authorization', 'url': url})
        self.req.setResponseCode(http.client.FOUND, 'External Authentication')
        self.req.setHeader('Location', url)
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    def process_code(self, code, purpose, return_url):
        flow = oauth2client.client.OAuth2WebServerFlow(config.google.client_id, config.google.client_secret, self.calc_perms(purpose), config.google.redirect_uri, auth_uri='https://accounts.google.com/o/oauth2/auth', token_uri='https://accounts.google.com/o/oauth2/token')
        try:
            credentials = flow.step2_exchange(code)
        except oauth2client.client.FlowExchangeError as error:
            return self.process_error('Flow exchange error', purpose, return_url)
        finally:
            del flow

        self.store_credentials(purpose, credentials)

        additional_status = None
        if purpose == 'authentication':
            try:
                self.process_authentication()
            except HandlerError as err:
                additional_status = err.args[0]

        tmpl_args = dict()
        if return_url:
            tmpl_args['return_url'] = return_url
        tmpl_args['view'] = 'success'
        if additional_status is not None:
            tmpl_args['additional_status'] = additional_status
        content = mod_tmpl.TemplateFactory(self.req, 'auth_ext.google').render(tmpl_args)
        if return_url is not None and additional_status is None:
            self.req.setResponseCode(http.client.FOUND, 'Return back')
            self.req.setHeader('Location', return_url)
        else:
            self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    def process_error(self, error, purpose, return_url):
        tmpl_args = dict()
        tmpl_args['view'] = 'failure'
        tmpl_args['error'] = error or 'Unknown'
        if return_url:
            tmpl_args['return_url'] = return_url
        content = content = mod_tmpl.TemplateFactory(self.req, 'auth_ext.google').render(tmpl_args)
        self.req.setHeader('Cache-Control', 'public, no-cache')
        self.req.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.req.write(content)

    @deco.session.Session()
    def __call__(self):
        try:
            state = self.cgi_params.param_get('state')
            if not state:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            state = json.dumps({})
        state = json.loads(state)
        purpose = state.get('purpose', 'authentication')
        return_url = state.get('return_url')
        try:
            code = self.cgi_params.param_get('code')
            if not code:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            code = None
        try:
            error = self.cgi_params.param_get('error')
            if not error:
                raise self.cgi_params.NotFoundError()
        except self.cgi_params.NotFoundError:
            error = None

        if code is None and error is None:
            return self.redirect_authorization(purpose, return_url)

        if code is not None:
            return self.process_code(code, purpose, return_url)

        return self.process_error(error, purpose, return_url)
