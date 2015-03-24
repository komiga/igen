
from mako.template import Template

from .include import *
from .util import *

class Param:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.type = cursor.type
		self.fqn = fully_qualified_name(self.cursor)
		self.default_value = None

		for c in get_children(self.cursor):
			if c.kind != CursorKind.ANNOTATE_ATTR:
				continue
			elif c.spelling.startswith("igen_default:"):
				self.default_value = c.spelling.replace("igen_default:", "")
				break

		self.signature_unnamed = self.type.spelling
		if not self.name:
			self.signature = self.signature_unnamed
		else:
			self.signature = "%s %s" % (self.signature_unnamed, self.fqn)

		if self.default_value:
			dv = " = " + self.default_value
			self.signature_unnamed += dv
			self.signature += dv

class Function:
	def __init__(self, cursor):
		self.cursor = cursor
		self.name = cursor.spelling
		self.result_type = cursor.result_type
		self.params = []

		lp = self.cursor.lexical_parent
		sp = self.cursor.semantic_parent
		self.ctx_parent = (lp and lp.kind == CursorKind.NAMESPACE) and lp or None
		self.ctx_parent_name = self.ctx_parent and lp.spelling or None
		self.ctx_parent_parts = fully_qualified_name_parts(self.ctx_parent)
		self.xqn = fully_qualified_name(sp, until = (lp, self.ctx_parent_parts))
		#print(
		#	"func %s: %s, %s == %r, xqn: %s" % (
		#	self.name, sp.spelling, lp.spelling, sp == lp, self.xqn
		#))

		for c in get_children(self.cursor):
			if c.kind != CursorKind.PARM_DECL:
				continue
			self.params.append(Param(c))

		sp = sp.kind == CursorKind.NAMESPACE and sp or None
		self.parent_fqn_parts = sp and fully_qualified_name_parts(sp) or []
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
		self.indent = self.level > 0 and "\t" or ""

	def add_func(self, func):
		self.funcs.append(func)

	def open_string(self):
		return "".join(["namespace %s {" % (p) for p in self.parts])

	def close_string(self):
		return "}" * len(self.parts)

class Group:
	def __init__(self, cursor, path, userdata = None):
		self.cursor = cursor
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
	index = clang_index()
	tu = index.parse(path, args = clang_args, options = G.parse_options)
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
			print("  %s in %s" % (f.signature_fqn(), f.ctx_parent_name or "<root>"))
			# print("    file %s" % (f.cursor.location.file.name))
			if f.xqn:
				print("    explicit %s" % (f.xqn))
			# print("    annotations = %r" % (get_annotations(f.cursor)))
	data = template.render_unicode(group = g)
	with open(gen_path, "w") as f:
		f.write(data.encode('utf-8', 'replace'))
	return g
