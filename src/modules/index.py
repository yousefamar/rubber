# This file is part of Rubber and thus covered by the GPL
# (c) Emmanuel Beffara, 2004--2005
"""
Indexing support with package 'index'.

|This package allows several bibliographies in one document. Each occurence of
|the \\newcites macro creates a new bibliography with its associated commands,
|using a new aux file. This modules behaves like the default BibTeX module for
|each of those files.

This module handles the processing of the document's indices using makeindex.
It stores an MD5 sum of the source (.idx) file between two runs, in order to
detect modifications.

The following directives are provided to specify options for makeindex:

  order <ordering> =
    Modify the ordering to be used. The argument must be a space separated
    list of:
    - standard = use default ordering (no options, this is the default)
    - german = use German ordering (option "-g")
    - letter = use letter instead of word ordering (option "-l")

  path <directory> =
    Add the specified directory to the search path for styles.

  style <name> =
    Use the specified style file.

They all accept an optional argument first, enclosed in parentheses as in
"index.path (foo,bar) here/", to specify which index they apply to. Without
this argument, they apply to all indices declared at the point where they
occur.
"""

import os
from os.path import *
import re, string

import rubber
from rubber import _
from rubber.util import *

class Index:
	"""
	This class represents a single index.
	"""
	def __init__ (self, env, source, target):
		"""
		Initialize the index, by specifying the source file (generated by
		LaTeX) and the target file (the output of makeindex).
		"""
		self.env = env
		self.msg = env.msg
		self.pbase = env.src_base
		self.source = env.src_base + "." + source
		self.target = env.src_base + "." + target
		if os.path.exists(self.source):
			self.md5 = md5_file(self.source)
		else:
			self.md5 = None

		self.path = [""]
		if env.src_path != "" and env.src_path != ".":
			self.path.append(env.src_path)
		self.style = None
		self.opts = []

	def command (self, cmd, args):
		if cmd == "order":
			for opt in args:
				if opt == "standard": self.opts = []
				elif opt == "german": self.opts.append("-g")
				elif opt == "letter": self.opts.append("-l")
				else: self.msg(1,
					_("unknown option '%s' for 'makeidx.order'") % opt)
		elif cmd == "path":
			for arg in args:
				self.path.append(os.path.expanduser(arg))
		elif cmd == "style":
			if len(args) > 1:
				self.style = args[0]

	def post_compile (self):
		"""
		Run makeindex if needed, with appropriate options and environment.
		"""
		if not os.path.exists(self.source):
			self.msg(2, _("strange, there is no %s") % self.source)
			return 0
		if not self.run_needed():
			return 0

		self.msg(0, _("processing index %s...") % self.source)
		cmd = ["makeindex", "-o", self.target] + self.opts
		if self.style:
			cmd.extend(["-s", self.style])
		cmd.append(self.pbase)
		if self.path != [""]:
			env = { 'INDEXSTYLE':
				string.join(self.path + [os.getenv("INDEXSTYLE", "")], ":") }
		else:
			env = {}
		if self.env.execute(cmd, env):
			self.env.msg(0, _("the operation failed"))
			return 1

		self.env.must_compile = 1
		return 0

	def run_needed (self):
		"""
		Check if makeindex has to be run. This is the case either if the
		target file does not exist or if the source file has changed.
		"""
		if not os.path.exists(self.target):
			self.md5 = md5_file(self.source)
			return 1
		if not self.md5:
			self.md5 = md5_file(self.source)
			self.msg(2, _("the index file %s is new") % self.source)
			return 1
		new = md5_file(self.source)
		if self.md5 == new:
			self.msg(2, _("the index %s did not change") % self.source)
			return 0
		self.md5 = new
		self.msg(2, _("the index %s has changed") % self.source)
		return 1

	def clean (self):
		"""
		Remove all generated files related to the index.
		"""
		for file in self.source, self.target, self.pbase + ".ilg":
			if exists(file):
				self.env.msg(1, _("removing %s") % file)
				os.unlink(file)

re_newindex = re.compile(" *{(?P<idx>[^{}]*)} *{(?P<ind>[^{}]*)}")
re_optarg = re.compile("\((?P<list>[^()]*)\) *")

class Module (rubber.Module):
	def __init__ (self, env, dict):
		"""
		Initialize the module with no index.
		"""
		self.env = env
		self.indices = {}
		env.add_hook("makeindex", self.makeindex)
		env.add_hook("newindex", self.newindex)

	def makeindex (self, dict):
		"""
		Register the standard index.
		"""
		self.indices["default"] = Index(self.env, "idx", "ind")

	def newindex (self, dict):
		"""
		Register a new index.
		"""
		m = re_newindex.match(dict["line"])
		if not m:
			return
		index = dict["arg"]
		d = m.groupdict()
		self.indices[index] = Index(self.env, d["idx"], d["ind"])
		self.env.msg(1, _("index %s registered") % index)

	def command (self, cmd, args):
		indices = self.indices
		if len(args) > 0:
			m = re_optarg.match(args[0])
			if m:
				for index in m.group("list").split(","):
					if indices.has_key(index):
						indices[index].command(cmd, args[1:])
		else:
			for index in indices.values():
				index.command(cmd, args)

	def post_compile (self):
		for index in self.indices.values():
			if index.post_compile():
				return 1
		return 0

	def clean (self):
		self.env.remove_suffixes([".ilg"])
		for index in self.indices.values():
			index.clean()
		return 0