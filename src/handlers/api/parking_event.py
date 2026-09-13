from .common import ApiError, BaseHandler, mod_mongo, config
from ....modules.mongo.parking_event import HistoryItem
from ....modules.mongo.security import Ref as SecurityRef
from ....modules.mongo.user import UserRef
import http.client

class Handler(BaseHandler):
    def __call__(self, action, oid, file_oid=None):
        if self.req.method == 'POST':
            from .parking_event_comment import Handler as CommentHandler
            return CommentHandler(self.req)(oid)
        def operation():
            user, agent, payload = self._authenticate()
            doc = self._get_doc(oid)
            if action == 'view':
                if not user.rbac_has_permission('parking.event/view'): raise ApiError(http.client.FORBIDDEN, 'Permission required')
                self._json(self._event(doc))
            elif action == 'file':
                if not user.rbac_has_permission('parking.event/view'): raise ApiError(http.client.FORBIDDEN, 'Permission required')
                file_id = mod_mongo.bson.objectid.ObjectId(file_oid)
                if not any(item.id == file_id and item.length for item in doc.history): raise ApiError(http.client.NOT_FOUND, 'File not found')
                with mod_mongo.DbSessionController() as db_session:
                    attachment = mod_mongo.gridfs.GridFS(db_session[config.name], 'parking_event.history').get(file_id)
                    self.req.setResponseCode(http.client.OK, http.client.responses[http.client.OK])
                    self.req.setHeader('Content-Type', attachment.content_type)
                    self.req.write(attachment.read())
            else: raise ApiError(http.client.NOT_FOUND, 'Unknown API action')
        return self._run(operation)
