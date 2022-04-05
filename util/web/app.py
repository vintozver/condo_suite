#!run/python_env/bin/python
# -*- coding: utf-8 -*-


from util.web.request import Request, RequestProcessor


def Application(env, responder):
    req = Request(env)

    from handlers.web import Handler, HandlerError
    try:
        return RequestProcessor(Handler, req=req).process(env, responder)
    except HandlerError as err:
        raise RuntimeError('Application handler error', err)


if __name__ == '__main__':
    pass

