
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

def collect_functions(cursor, pre_filter = None, post_filter = None, funcs = None):
	funcs = funcs or []
	for c in get_children(cursor):
		if c.kind == CursorKind.NAMESPACE:
			# FIXME: Why does funcs have to be reassigned?
			# It should be the same object.
			funcs = collect_functions(c, pre_filter, post_filter, funcs)
		elif c.kind != CursorKind.FUNCTION_DECL:
			continue
		elif not pre_filter or pre_filter(c):
			f = Function(c)
			if not post_filter or post_filter(f):
				funcs.append(f)
	return funcs

class Group:
	def __init__(self, cursor, path, funcs):
		self.path = path
		self.funcs = funcs

	def write(self, path):
		pass

def make_pre_filter_path(path):
	def f(cursor):
		return cursor.location.file.name == path
	return f

def make_pre_filter_annotation(match = "igen"):
	def f(cursor):
		for a in get_annotations(cursor):
			if a == match:
				return True
		return False
	return f

def collect(path, clang_args, pre_filter = None, post_filter = None):
	index = cindex.Index.create()
	tu = index.parse(path, clang_args)
	if not tu:
		raise RuntimeError("failed to parse %s" % (path))
	funcs = collect_functions(tu.cursor, pre_filter, post_filter)
	g = Group(tu.cursor, path, funcs)
	return g

def generate(path, gen_path, clang_args, pre_filter = None, post_filter = None):
	g = collect(path, clang_args, pre_filter, post_filter)
	print("generate: %s -> %s" % (path, gen_path))
	for f in g.funcs:
		print("  %s in %s" % (f.signature_fqn(), f.contextual_parent or "<root>"))
		print("    explicit in %s" % (f.explicitly_qualified_name))
		# print("    in %s" % (f.cursor.location.file.name))
		# print("    annotations = %r" % (get_annotations(f.cursor)))
	return g
