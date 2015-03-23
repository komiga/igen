
from mako.template import Template

from .include import *
from .util import *

class Param:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.type = cursor.type
		self.fqn = fully_qualified_name(self.cursor)
		self.signature_unnamed = self.type.spelling
		if not self.name:
			self.signature = self.signature_unnamed
		else:
			self.signature = "%s %s" % (self.signature_unnamed, self.fqn)

class Function:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.result_type = cursor.result_type
		self.params = []

		p = self.cursor.lexical_parent
		self.contextual_parent = (p and p.kind == CursorKind.NAMESPACE) and p.spelling or None

		self.explicitly_qualified_name = \
			self.contextual_parent and \
			fully_qualified_name(self.cursor.semantic_parent, self.contextual_parent) or None

		for c in get_children(self.cursor):
			if not c.kind == CursorKind.PARM_DECL:
				continue
			self.params.append(Param(c))

		p = self.cursor.semantic_parent
		p = p.kind == CursorKind.NAMESPACE and p or None
		self.parent_fqn_parts = p and fully_qualified_name_parts(p) or []
		self.parent_fqn = fully_qualified_name(None, parts = self.parent_fqn_parts)

		self.fqn_parts = self.parent_fqn_parts + [self.name]
		self.fqn = fully_qualified_name(None, parts = self.fqn_parts)

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
			name = self.fqn,
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

class NamespaceGroup:
	def __init__(self, fqn, parts):
		self.fqn = fqn
		self.level = len(parts)
		self.parts = parts
		self.funcs = []

	def add_func(self, func):
		self.funcs.append(func)

	def open_string(self):
		if self.level == 0:
			return ""
		return "".join(["namespace %s {" % (p) for p in self.parts])

	def close_string(self):
		if self.level == 0:
			return ""
		return "}" * len(self.parts)

class Group:
	def __init__(self, cursor, path, userdata = None):
		self.path = path
		self.funcs = []
		self.funcs_by_namespace = {}
		self.userdata = userdata

	def add_funcs(self, funcs):
		for f in funcs:
			fqn = f.parent_fqn or "<root>"
			ns = self.funcs_by_namespace.get(fqn)
			if not ns:
				ns = NamespaceGroup(fqn, f.parent_fqn_parts)
				self.funcs_by_namespace[fqn] = ns
			ns.add_func(f)
			self.funcs.append(f)

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

def collect(
	path, clang_args,
	pre_filter = None, post_filter = None,
	userdata = None
):
	index = cindex.Index.create()
	tu = index.parse(path, clang_args)
	if not tu:
		raise RuntimeError("failed to parse %s" % (path))
	g = Group(tu.cursor, path, userdata)
	g.add_funcs(collect_functions(tu.cursor, pre_filter, post_filter))
	return g

def generate(
	path, gen_path, clang_args, template,
	pre_filter = None, post_filter = None,
	userdata = None
):
	g = collect(path, clang_args, pre_filter, post_filter, userdata)
	print("generate: %s -> %s" % (path, gen_path))
	if G.debug:
		for f in g.funcs:
			print("  %s in %s" % (f.signature_fqn(), f.contextual_parent or "<root>"))
			# print("    file %s" % (f.cursor.location.file.name))
			if f.explicitly_qualified_name:
				print("    explicit %s" % (f.explicitly_qualified_name))
			# print("    annotations = %r" % (get_annotations(f.cursor)))
	fp = open(gen_path, "w")
	data = template.render_unicode(group = g)
	fp.write(data.encode('utf-8', 'replace'))
	fp.close()
	return g
