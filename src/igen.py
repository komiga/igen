
# import os.path
from clang import cindex
from clang.cindex import CursorKind

global opts
global G_children_cache
G_children_cache = {}

def visit(cursor, visitor, children):
	cindex.conf.lib.clang_visitChildren(
		cursor, cindex.callbacks['cursor_visit'](visitor), children
	)

# Unfortunately, cindex.Cursor.get_children() gives an iterator instead of
# the list.
def Cursor_get_children(cursor):
	def visitor(child, parent, children):
		assert child != cindex.conf.lib.clang_getNullCursor()
		child._tu = cursor._tu
		children.append(child)
		return 1 # continue

	children = []
	visit(cursor, visitor, children)
	return children

def get_children(cursor):
	children = G_children_cache.get(cursor.hash, None)
	# print("hit: %s / %s %d %s" % (children and "yes" or "no ", cursor.kind, cursor.hash, cursor.spelling))
	if not children:
		children = Cursor_get_children(cursor)
		G_children_cache[cursor.hash] = children
	return children

def get_annotations(cursor):
	return [
		c.displayname \
		for c in get_children(cursor) \
		if c.kind == CursorKind.ANNOTATE_ATTR
	]

def fully_qualified_name_parts(cursor):
	parts = [cursor.spelling]
	p = cursor
	while True:
		p = p.semantic_parent
		# print("%s: %s" % (p.kind, p.spelling))
		# TODO: Other valid parts?
		if not p or p.kind != CursorKind.NAMESPACE:
			break
		parts.append(p.spelling)
	return parts[::-1]

def fully_qualified_name(cursor, parts = None):
	return "::".join(parts or fully_qualified_name_parts(cursor))

class Param(object):
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

class Function(object):
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

		self.fully_qualified_name_parts = fully_qualified_name_parts(self.cursor)
		self.fully_qualified_name = fully_qualified_name(None, self.fully_qualified_name_parts)
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

class Group(object):
	def __init__(self, cursor, path):
		self.path = path
		self.funcs = collect_functions(cursor, path)

def main():
	from optparse import OptionParser, OptionGroup

	parser = OptionParser(
		prog = "igen",
		usage = "usage: %prog [options] [clang-args*]"
	)
	parser.disable_interspersed_args()
	(opts, clang_args) = parser.parse_args()

	if len(clang_args) == 0:
		parser.error("missing clang-args")

	paths = []
	for a in clang_args:
		if not a.startswith('-'):
			paths.append(a)
		else:
			break

	cindex.Config.set_library_file("libclang.so")
	#cindex.Config.set_library_file("/usr/lib/llvm-3.5/lib/libclang.so.1")
	#print("Config.library_file: %s" % cindex.Config.library_file)

	index = cindex.Index.create()

	tu = index.parse(None, clang_args)
	if not tu:
		parser.error("unable to load input")

	print("collecting")
	groups = {}
	for p in paths:
		groups[p] = Group(tu.cursor, p)

	print("groups:")
	for g in groups.values():
		print("  %s:" % g.path)
		for f in g.funcs:
			print("    %s in %s" % (f.signature_fqn(), f.contextual_parent or "<root>"))

if __name__ == "__main__":
	main()
