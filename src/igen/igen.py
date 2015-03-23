
from .include import *
from .util import *

class Param:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.type = cursor.type
		self.fully_qualified_name = fully_qualified_name(self.cursor)
		self.signature_unnamed = self.type.spelling
		if not self.name:
			self.signature = self.signature_unnamed
		else:
			self.signature = "%s %s" % (self.signature_unnamed, self.fully_qualified_name)

class Function:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.result_type = cursor.result_type
		self.params = []

		p = self.cursor.lexical_parent
		self.contextual_parent = (p and p.kind == CursorKind.NAMESPACE) and p.spelling or None

		for c in get_children(self.cursor):
			if not c.kind == CursorKind.PARM_DECL:
				continue
			self.params.append(Param(c))

		sp = self.cursor.semantic_parent
		self.explicitly_qualified_name = sp and fully_qualified_name(sp, self.contextual_parent) or None
		self.fully_qualified_name_parts = fully_qualified_name_parts(self.cursor)
		self.fully_qualified_name = fully_qualified_name(None, parts = self.fully_qualified_name_parts)
		self.args_signature = ", ".join(p.signature for p in self.params)
		self.args_signature_unnamed = ", ".join(p.signature_unnamed for p in self.params)

	def signature(self, name = None, named_args = True):
		name = name or self.name
		return (
			"%s %s(%s)" % (
				self.result_type.spelling,
				name,
				named_args and self.args_signature or self.args_signature_unnamed,
			)
		)

	def signature_fqn(self, named_args = True):
		return self.signature(
			name = self.fully_qualified_name,
			named_args = named_args,
		)

def collect_functions(cursor, path, funcs = None):
	funcs = funcs or []
	for c in get_children(cursor):
		if c.kind == CursorKind.NAMESPACE:
			collect_functions(c, path, funcs)
		elif c.kind == CursorKind.FUNCTION_DECL:
			if path == c.location.file.name:
				funcs.append(Function(c))
	return funcs

class Group:
	def __init__(self, cursor, path):
		self.path = path
		self.funcs = collect_functions(cursor, path)
