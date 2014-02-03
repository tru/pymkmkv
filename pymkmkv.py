#!/usr/bin/python

import optparse
import logging, shlex
import asciitree
import subprocess

logging.basicConfig(format="%(asctime)s|%(levelname)s|%(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("pymkmkv")
log.setLevel(logging.INFO)

VIDEO = 6201
AUDIO = 6202
SUBTITLE = 6203

def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

class SourceInfo:
	children = {} # TitleInfos
	titlecount = 0
	name = ""
	primarylang = ""

	def __str__(self):
		return self.name

class TitleInfo:
	def __init__(self, titlenr):
		self.info = {"titlenr": titlenr, "lang":"unknown", "length": "0:00:00", "size":0}
		self.children = {} # StreamInfos

	def __str__(self):
		return "Title %d: %s - %s (%s)"	% (self.info["titlenr"], self.info["lang"], self.info["length"], sizeof_fmt(int(self.info["size"])))

class StreamInfo:
	def __init__(self, streamnr, streamtype):
		self.info = {"streamnr": streamnr, "streamtype": streamtype, "lang": "unknown", "codec": None}
		self.children = {}

	def __str__(self):
		t = None
		if self.info["streamtype"] == VIDEO: t = "Video"
		if self.info["streamtype"] == AUDIO: t = "Audio"
		if self.info["streamtype"] == SUBTITLE: t = "Subtitle"
		return "%s - %s (%s)" % (t, self.info["lang"], self.info["codec"])

g_sourceInfo = SourceInfo()

class BaseParser:
	prefix=""

	def can_handle(self, prefix):
		return prefix == self.prefix

	def do_handle(self, line):
		pass

""" 1005,0,1,"MakeMKV v1.8.7 linux(x64-release) started","%1 started","MakeMKV v1.8.7 linux(x64-release)" """
class MsgParser(BaseParser):
	prefix = "MSG"
	debug_msgs = (3307, 3025)
	def do_handle(self, linearray):
		loglevel = logging.INFO

		if int(linearray[0]) in self.debug_msgs:
			loglevel = logging.DEBUG

		if linearray >= 3:
			msg = linearray[3][1:len(linearray[3])-1]
			log.log(loglevel, msg)

class NullOutputParser(BaseParser):
	prefix = ("DRV", )
	def can_handle(self, prefix):
		return prefix in self.prefix
	def do_handle(self, line):
		pass

class StreamParser(BaseParser):
	prefix = "SINFO"
	mapping = {7:"codec", 30: "lang"}

	def do_handle(self, args):
		titlenr = int(args[0])
		streamnr = int(args[1])
		msgnr = int(args[2])

		if not titlenr in g_sourceInfo.children:
			log.warning("Could not find title %d - needed by stream %d", titlenr, streamnr)
			return

		title = g_sourceInfo.children[titlenr]
		stream = None

		if streamnr in title.children:
			stream = title.children[streamnr]
		else:
			if msgnr == 1:
				stream = StreamInfo(streamnr, int(args[3]))
				title.children[streamnr] = stream
			else:
				log.warning("No stream found, but msgnr was crazy: %d", msgnr)
				return

		if msgnr in self.mapping:
			val = args[4]
			if val[0] == '"': val = val[1:len(val)-1]
			stream.info[self.mapping[msgnr]] = val


class TCountParser(BaseParser):
	prefix = "TCOUNT"

	def do_handle(self, args):
		g_sourceInfo.trackcount = int(args[0])

class TitleParser(BaseParser):
	prefix = "TINFO"
	mapping = {9: "length", 11:"size", 29: "lang"}

	def do_handle(self, args):
		titlenr = int(args[0])
		msgnr = int(args[1])

		title = None

		if titlenr in g_sourceInfo.children:
			title = g_sourceInfo.children[titlenr]
		else:
			title = TitleInfo(titlenr)
			g_sourceInfo.children[titlenr] = title

		if msgnr in self.mapping:
			val = args[3]
			if val[0] == '"': val = val[1:len(val)-1]
			title.info[self.mapping[msgnr]] = val


class ClassParser(BaseParser):
	prefix = "CINFO"

	def do_handle(self, args):
		if args[0] == "2":
			g_sourceInfo.name = args[2][1:len(args[2])-1]

def split_arguments(args):
	lex = shlex.shlex(args)
	lex.whitespace += ","
	lex.whitespace_split = True
	return list(lex)

def get_source(path):
	if path.startswith("disc:"): return path
	if os.exists(path):
		if path.endswith(".iso"): return "iso:" + path
		if os.path.isdir(path): return 

parsers = (MsgParser(), NullOutputParser(), StreamParser(), TitleParser(), ClassParser(), TCountParser())

if __name__ == '__main__':
	parser = optparse.OptionParser()
	parser.add_option("-d", "--debug", dest="debug", default=False, action="store_true")

	(options, args) = parser.parse_args()

	if options.debug:
		log.setLevel(logging.DEBUG)

	data = open("info-planes.txt", "r")
	l = data.readline()
	while l:
		prefix, array = (None, None)
		try: (prefix, array) = l.split(":", 1)
		except: log.warning("Could not split apart %s", l)
		handled = False
		for p in parsers:
			if p.can_handle(prefix):
				p.do_handle(split_arguments(array))
				handled = True
				break

		if not handled:
			log.debug("Did not handle prefix %s", prefix)

		l = data.readline()

	print asciitree.draw_tree(g_sourceInfo, lambda n: n.children.values())
