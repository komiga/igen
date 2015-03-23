
from igen.include import *
from igen.igen import *
from igen.util import *

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
		x = Group(tu.cursor, p)

	print("groups:")
	for g in groups.values():
		print("  %s:" % g.path)
		for f in g.funcs:
			print("    %s in %s" % (f.signature_fqn(), f.contextual_parent or "<root>"))

if __name__ == "__main__":
	main()
