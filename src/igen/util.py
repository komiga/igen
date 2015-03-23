
from .include import *

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

def fully_qualified_name_parts(cursor, until = None):
	parts = [cursor.spelling]
	p = cursor
	while True:
		p = p.semantic_parent
		# print("%s: %s" % (p.kind, p.spelling))
		# TODO: Other valid parts?
		if not p or p.kind != CursorKind.NAMESPACE or (until and p.spelling == until):
			break
		parts.append(p.spelling)
	return parts[::-1]

def fully_qualified_name(cursor, until = None, parts = None):
	return "::".join(parts or fully_qualified_name_parts(cursor, until))
