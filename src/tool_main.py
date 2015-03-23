
import sys
import argparse

from mako.template import Template

from igen.include import *
from igen import igen
from igen.util import *

def main():
	parser = argparse.ArgumentParser(
		prog = "igen",
		usage = "igen [options] path gen_path template_path -- clang-args",
	)

	parser.add_argument("path", type = str, help = "path to parse")
	parser.add_argument("gen_path", type = str, help = "path to generate")
	parser.add_argument("template_path", type = str, help = "path to template")

	if "--" not in sys.argv:
		parser.error("missing clang-args")

	arg_sep_index = sys.argv.index("--")
	opts = parser.parse_args(sys.argv[1:arg_sep_index])
	clang_args = sys.argv[arg_sep_index + 1:]

	if len(clang_args) == 0:
		parser.error("missing clang-args")

	cindex.Config.set_library_file("libclang.so")
	G.debug = True

	template = Template(filename = opts.template_path)
	igen.generate(
		opts.path, opts.gen_path, clang_args,
		template = template,
		userdata = None,
		pre_filter = igen.make_pre_filter_path(opts.path),
		post_filter = None
	)

if __name__ == "__main__":
	main()
