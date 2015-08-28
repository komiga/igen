
import os
import time
import re
import hashlib
import json
from mako.template import Template

from .include import *
from . import igen
from .util import *

def configure(
	libclang_path,
	source_basepath,
	tmp,
	template_path
):
	os.stat_float_times(False)
	cindex.Config.set_library_path(libclang_path)

	G.tool_interface_configured = True
	G.SOURCE_BASEPATH = source_basepath
	G.F_TEMPLATE = template_path
	G.F_CACHE = os.path.join(tmp, "igen_cache")
	G.F_USERS = os.path.join(tmp, "igen_users")
	G.PASS_ANNOTATIONS = [
		"igen_interface",
		"igen_private",
	]

class Source:
	def __init__(self, spec):
		self.path = spec["path"]
		self.included = spec["included"]
		assert os.path.exists(self.path), "source does not exist: %s" % (self.path)
		self.time = mtime(self.path)

class Interface:
	def __init__(self, spec):
		self.path = spec["path"]
		self.sources = [
			Source(source_spec) for source_spec in spec["sources"]
		]
		self.gen_path = spec["gen_path"]
		self.doc_group = spec["doc_group"]

		self.doc_path = os.path.join(
			"doc/gen_interface",
			re.sub(r'(.+)/src/' + G.SOURCE_BASEPATH + r'/(.+)\..+$', r'\1_\2.dox', self.path).replace("/", "_")
		)

		self.group = None
		self.data = None
		self.data_hash = None

		assert len(self.sources) > 0, "no sources for %s" % (self.gen_path)

		cache = G.cache.get(self.gen_path, {})
		self.check_time = cache.get("check_time", 0)
		self.path_time = mtime(self.path)

		self.needs_check = (
			G.do_check or
			self.check_time < self.path_time or
			True in (self.check_time < source.time for source in self.sources)
		)

		gen_exists = os.path.isfile(self.gen_path)
		self.gen_hash = None
		if self.needs_check and gen_exists:
			with open(self.gen_path, "r") as f:
				self.gen_hash = hashlib.md5(f.read()).digest()
		elif not gen_exists:
			# Make sure the file exists, since we're parsing the hierarchy
			# that #includes it. Due to -fsyntax-only this doesn't cause
			# issues, but it's better to be on the safe side.
			with open(self.gen_path, "w") as f:
				pass

	def link_doc(self):
		if not os.path.exists("doc/gen_interface"):
			os.mkdir("doc/gen_interface")
		if os.path.exists(self.doc_path):
			os.remove(self.doc_path)
		os.symlink(os.path.join("../..", self.gen_path), self.doc_path)

	def load(self):
		def pre_filter(cursor):
			path = cursor.location.file.name
			#path = re.sub(
			#	r'^tmp/include/' + G.SOURCE_BASEPATH + r'/([^/]+)/(.+)$',
			#	r'lib/\1/src/\2',
			#	cursor.location.file.name
			#)
			return (
				True in (s.path == path for s in self.sources) and (
					cursor.raw_comment != None or
					has_annotation(cursor, G.PASS_ANNOTATIONS)
				)
			)
		def post_filter(function):
			# function.xqn == self.namespace or
			function.annotations = get_annotations(function.cursor)
			function.anno_private = "igen_private" in function.annotations
			return True

		self.group = igen.Group(None)
		for source in self.sources:
			if source.included:
				# Skip sources that are included by the interface
				continue
			funcs = igen.parse_and_collect(source.path, G.clang_args, pre_filter, post_filter)
			self.group.add_funcs(funcs)

		self.data = G.template.render_unicode(
			group = self.group,
			interface = self,
		).encode("utf-8", "replace")
		self.data_hash = not G.do_force and hashlib.md5(self.data).digest() or None
		self.needs_build = G.do_force or self.data_hash != self.gen_hash
		self.check_time = int(time.mktime(time.localtime()))

	def write(self):
		with open(self.gen_path, "w") as f:
			f.write(self.data)

	def set_cache(self):
		G.cache[self.gen_path] = {
			"check_time" : self.check_time,
		}

class Collector:
	EXT_FILTER = {"hpp"}
	THRESHOLD = 150

	def __init__(self):
		assert G.tool_interface_configured, "tooling not configured"
		self.groups = []
		self.path_exists = set()
		self.paths = []
		self.user_paths = []
		self.users = []

	def m_1(self, group, data, group_name):
		assert not data.doc_group
		data.doc_group = group_name

	def m_2(self, group, data, group_name):
		data.ingroups.append(group_name)

	def m_3(self, group, data, path):
		_, extension = splitext(path)
		if extension == "gen_interface":
			assert not data.gen_path, "a gen_interface was already included!"
			data.gen_path = group.src + '/' + path
			# return True

	def m_4(self, group, data):
		data.sources_included = True

	def m_5(self, group, data, path):
		data.sources.append(AttrDict(
			path = group.src_inner + '/' + path,
			included = data.sources_included,
		))

	def m_6(self, group, data, pattern):
		pattern = "^%s/%s$" % (group.src_inner, pattern)
		pattern_regex = re.compile(pattern)
		# print("  checking source pattern: %s" % (pattern))
		for path in self.paths:
			if pattern_regex.search(path):
				# print("    match: %s" % (path))
				data.sources.append(AttrDict(
					path = path,
					included = data.sources_included,
				))

	MATCHERS = [
		(re.compile(r'@defgroup\s+(.+)\s+.+$'), m_1),
		(re.compile(r'@ingroup\s+(.+)$'), m_2),
		(re.compile(r'#include.+[<"](.+)[>"]'), m_3),
		(re.compile(r'//\s*igen-following-sources-included$'), m_4),
		(re.compile(r'//\s*igen-source:\s*([^\s]+)$'), m_5),
		(re.compile(r'//\s*igen-source-pattern:\s*([^\s]+)$'), m_6),
	]

	def add_groups(self, path, src_inner_prefix):
		for name in os.listdir(path):
			if not os.path.isdir(os.path.join(path, name)):
				continue
			src = path + '/' + name + '/' + "src"
			self.groups.append(AttrDict(
				name = name,
				src = src,
				src_inner = src + '/' + G.SOURCE_BASEPATH + '/' + src_inner_prefix + name,
				user_paths = [],
			))

	def process_file(self, group, path):
		path_no_ext, _ = splitext(path)
		data = AttrDict(
			slug = path_no_ext,
			path = path,
			gen_path = None,
			sources_included = False,
			sources = [],
			doc_group = None,
			ingroups = [],
		)

		primary_source = path_no_ext + ".cpp"
		if primary_source in self.path_exists:
			data.sources.append(AttrDict(
				path = primary_source,
				included = False,
			))

		cont = True
		line_position = 1
		# print("\nprocess: %s" % (path))
		with open(path, "r") as f:
			for line in f:
				if Collector.THRESHOLD < line_position:
					break
				elif line == "":
					continue
				for matcher in Collector.MATCHERS:
					pattern, func = matcher
					m = pattern.match(line)
					if m != None:
						# print("match: %s -> %s" % (pattern.pattern, line[:-1]))
						cont = not func(self, group, data, *m.groups())
						break
				line_position = line_position + 1
				if not cont:
					break

		if not data.gen_path:
			return False

		if not data.doc_group and len(data.ingroups) > 0:
			data.doc_group = data.ingroups[-1]
		del data["ingroups"]
		del data["sources_included"]
		self.users.append(data)
		return True

	def collect(self):
		for group in self.groups:
			for root, _, files in os.walk(group.src):
				for rel_path in files:
					path = root + '/' + rel_path
					# print(splitext(path))
					_, extension = splitext(rel_path)
					self.path_exists.add(path)
					self.paths.append(path)
					if extension in Collector.EXT_FILTER:
						group.user_paths.append(path)
				group.user_paths.sort()
		self.paths.sort()

		for group in self.groups:
			for path in group.user_paths:
				self.process_file(group, path)

	def write(self):
		with open(G.F_USERS, "w") as f:
			json.dump({"users" : self.users}, f)

def build(argv):
	assert G.tool_interface_configured, "tooling not configured"

	arg_sep_index = argv.index("--")
	argv = argv[1:arg_sep_index]
	argv_rest = argv[arg_sep_index + 1:]

	def opt(name):
		return (
			os.environ.get(name.upper(), False) or
			("--" + name) in argv
		)

	G.debug = opt("debug") != False
	G.do_force = opt("force") != False
	G.do_check = opt("check") != False or G.do_force
	G.template = Template(filename = G.F_TEMPLATE)
	G.cache = {}

	if os.path.isfile(G.F_CACHE):
		with open(G.F_CACHE, "r") as f:
			G.cache = json.load(f)

	flag_exclusions = {
		"-MMD",
		"-MP",
	}
	G.clang_args = [
		"-fsyntax-only",
		"-DIGEN_RUNNING",
	] + [a for a in argv_rest if a not in flag_exclusions]

	#if G.debug:
	#	print("clang_args: %r" % G.clang_args)

	interfaces = {}
	with open(G.F_USERS, "r") as f:
		users = json.load(f)["users"]
		if len(users) == 0:
			print("note: no igen users")
		for spec in users:
			i = Interface(spec)
			interfaces[i.gen_path] = i

	for i in interfaces.values():
		if not i.needs_check:
			continue

		print("\ncheck: %s" % (i.gen_path))
		for source in i.sources:
			print("  from %s%s" % (source.path, source.included and " (included)" or ""))
		i.load()
		if G.debug and len(i.group.funcs) > 0:
			print("")
			for f in i.group.funcs:
				print("  %s" % f.signature_fqn())

		if not i.needs_build:
			continue
		print("writing")
		i.write()
		i.link_doc()

	G.cache = {}
	for i in interfaces.values():
		i.set_cache()

	with open(G.F_CACHE, "w") as f:
		json.dump(G.cache, f)
