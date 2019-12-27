
import os

from .include import *

class AttrDict(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__

	def __init__(self, **kwargs):
		for key, value in kwargs.iteritems():
			setattr(self, key, value)

global G
G = AttrDict(
	debug = False,
	children_cache = {},
	parse_options = cindex.TranslationUnit.PARSE_NONE,
	clang_index = None,
)

def clang_index():
	if not G.clang_index:
		G.clang_index = cindex.Index.create()
	return G.clang_index

def visit(cursor, visitor, userdata):
	cindex.conf.lib.clang_visitChildren(
		cursor, cindex.callbacks['cursor_visit'](visitor), userdata
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
	children = G.children_cache.get(cursor.hash, None)
	# print("hit: %s / %s %d %s" % (children and "yes" or "no ", cursor.kind, cursor.hash, cursor.spelling))
	if not children:
		children = Cursor_get_children(cursor)
		G.children_cache[cursor.hash] = children
	return children

def get_annotations(cursor):
	return [
		c.displayname \
		for c in get_children(cursor) \
		if c.kind == CursorKind.ANNOTATE_ATTR
	]

def has_annotation(cursor, name):
	for c in get_children(cursor):
		if c.kind != CursorKind.ANNOTATE_ATTR:
			continue
		elif type(name) == list and c.displayname in name:
			return True
		elif c.displayname == name:
			return True
	return False

def fully_qualified_name_parts(cursor, until = None):
	until_cursor = until and until[0] or None
	until_parts = until and until[1] or None

	p = cursor
	parts = []
	while p and (not until or p != until_cursor):
		parts.append(p.spelling)
		p = p.semantic_parent
		# TODO: Other valid parts?
		if p and p.kind != CursorKind.NAMESPACE:
			break

	# Reverse
	parts = parts[::-1]

	# Trim parts if until_cursor wasn't part of the tree
	if until_parts and p != until_cursor:
		matching = 0
		for i in range(min(len(parts), len(until_parts))):
			if parts[i] != until_parts[i]:
				break
			matching += 1
		parts = parts[matching:]

	return parts

def fully_qualified_name(cursor, until = None, parts = None):
	if parts == None:
		parts = fully_qualified_name_parts(cursor, until)
	return "::".join(parts) or None

def mtime(path):
	if os.path.exists(path):
		stat = os.stat(path)
		return stat.st_mtime
	return 0

def splitext(path):
	p, e = os.path.splitext(path)
	if e:
		e = e[1:]
	return p, e
