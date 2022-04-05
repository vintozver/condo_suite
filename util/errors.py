# Common errors

class GenericError(Exception):
	pass

class NotFoundError(GenericError):
	pass

class ArgumentError(GenericError):
	pass

class AbstractError(GenericError):
	pass

class SecurityError(GenericError):
	pass

class AuthenticationError(SecurityError):
	pass

class HandlerError(GenericError):
	pass

