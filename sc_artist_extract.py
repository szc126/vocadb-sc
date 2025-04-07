#!/usr/bin/env python

import re
import sc_artist_extract.lang

# language data
"""
song type
	str // array-str
	song type // song type that appears in title
artist role
	str // array-str
	artist role // artist role that appears in description
url label
	str // array-str
	other content on another webpage // url label that appears in description
profile label
	str // array-str
	website name // link prefix that appears in description
other label
	str // array-str
	other content // label that appears in description

sentence
	pattern
	free-form sentence that appears in video  description
title
	pattern
	text that appears in title
"""
LANG = sc_artist_extract.lang.load_lang()

# bracket kagi - song title
BKT_KAGI_A = r'[「『\[]'
BKT_KAGI_B = r'[」』\]]'
# bracket maru - parentheses
BKT_MARU_A = r'[（(]'
BKT_MARU_B = r'[）)]'
# bracket sumitsuki - other
BKT_SMTK_A = r'[【]'
BKT_SMTK_B = r'[】]'

# separator
SEP = r'[／/-]'
# separator artist roles
SEP_ARTIST_ROLE = r'[：:　]'
# separator and
SEP_AND = r'(?:・|&|and|と|、|[/])'

# voice synth expand names
VOC_EXPAND = [
	# 鏡音リン・レン
	(r'([㐀-龥]+)([ぁ-ん]+)・([ぁ-ん]+)', r'\1\2、\1\3'),
	(r'([㐀-龥]+)([ァ-ン]+)・([ァ-ン]+)', r'\1\2、\1\3'),
	# Kagamine Rin and Len
	(fr'([A-Z][a-z]+) ([A-Z][a-z]+) {SEP_AND} ([A-Z][a-z]+)', r'\1\2、\1\3'),
]

KW_EXPAND = {
	'Voc': r'(?P<vocal>.+)',
	'Type': r'(?P<song_type>.+)',
	'Title': r'(?P<song_title>.+)',
	'Pro': r'(?P<compose>.+)',
	'Parent': r'(?P<parent>.+)',

	'「': BKT_KAGI_A,
	'」': BKT_KAGI_B,
	'（': BKT_MARU_A,
	'）': BKT_MARU_B,
	'【': BKT_SMTK_A,
	'】': BKT_SMTK_B,

	'／': SEP,
}

# ----

kw_expand_lang = {}

# ----

def re_expand_pattern(pattern, lang = None):
	"""
	Genericize characters, such as brackets and slashes.
	Convert shortcuts such as `Voc` into named groups.
	"""

	for placeholder in KW_EXPAND:
		if placeholder == 'Type':
			try:
				kw_expand_lang[f'Type:{lang}']
			except KeyError:
				list_unflat = LANG[lang].kw_song_type.values()
				list_flat = [item for sublist in list_unflat for item in sublist]
				kw_expand_lang[f'Type:{lang}'] = list_flat
			#pattern = pattern.replace(placeholder, KW_EXPAND[placeholder].replace('.+', '|'.join(kw_expand_lang[f'Type:{lang}']) + '|.+'))
			#pattern = pattern.replace(placeholder, KW_EXPAND[placeholder].replace('.+', '|'.join(kw_expand_lang[f'Type:{lang}'])))
			pattern = pattern.replace(placeholder, KW_EXPAND[placeholder].replace('.+', '.*' + '.*|.*'.join(kw_expand_lang[f'Type:{lang}'])))
		pattern = pattern.replace(placeholder, KW_EXPAND[placeholder])

	# TODO: ja NFD to NFC
	# TODO: zh Hans to Hant

	return pattern

def extract(info):
	"""
	Accepts youtube-dl video info.
	"""

	meta_found = {
		'artists': [],
		'urls': [],
		'other': [],

		'debug': [],
	}

	#meta_found['debug'].append(info['title'])
	#meta_found['debug'].append(info['description'])

	for lang in LANG:
		# XXX: TESTING
		if lang == 'zh':
			continue

		# TODO: detect a block that is obviously credits, and don't give up on unrecognized roles
			# example: 【洛天依/星尘/赤羽/苍穹】陟彼忘川 https://www.bilibili.com/video/av206333970/
		#for artist_role in LANG[lang].kw_artist_role:
		#	for pattern in LANG[lang].kw_artist_role[artist_role]:
		#		for match in re.finditer(fr'(?P<artist_role>{pattern})[^\s]*{SEP_ARTIST_ROLE}(?P<artist_name>.+)', info['description'], flags = re.I):
		#			meta_found['artists'].append((artist_role, match['artist_name']))
		#			break

		for label in LANG[lang].kw_url_label:
			for pattern in LANG[lang].kw_url_label[label]:
				for match in re.finditer(fr'(?P<label>{pattern})(\s+)(?P<text>.+)', info['description'], flags = re.I):
					meta_found['urls'].append((label, match['text']))
					break

		for label in LANG[lang].kw_profile_label:
			for pattern in LANG[lang].kw_profile_label[label]:
				for match in re.finditer(fr'(?P<label>{pattern})(?P<text>.+)', info['description'], flags = re.I):
					meta_found['other'].append((label, match.group(0)))
					break

		for label in LANG[lang].kw_other_label:
			for pattern in LANG[lang].kw_other_label[label]:
				for match in re.finditer(fr'(?P<label>{pattern})(?P<text>.+)', info['description'], flags = re.I):
					meta_found['other'].append((label, match['text']))
					break

		if True:
			for pattern, my_lambda in LANG[lang].kw_sentence:
				for match in re.finditer(pattern, info['description'], flags = re.I | re.M):
					meta_found['artists'] += my_lambda(match)
					pass

		if True:
			for pattern in LANG[lang].kw_title:
				pattern = re_expand_pattern(pattern, lang = lang)
				for match in re.finditer(pattern, info['title'], flags = re.I):
					for item in list(match.groupdict().items()):
						match item[0]:
							case 'vocal' | 'artist name':
								meta_found['artists'].append(item)
							case _:
								#key = next((key for key, values in kw_song_type.items() for value in values if value in search_term), None)
								meta_found['other'].append(item)
					break

	# TODO:
	# 1. in the desc, look for Voc
	# 2. in the title, look for Voc or tags

	# TODO:
	# local cache of keywords that are known to be a producer name/voc name/w.ever

	return meta_found

if __name__ == '__main__':
	# XXX: TESTING
	import pickle
	import pprint
	import colorama
	pp = pprint.PrettyPrinter(indent = 2)

	with open('sc_song_add.py.ytdl_extract_info.0-0.pickle', 'rb') as file:
		data = pickle.load(file)

	for call in data:
		if 'entries' in data[call]:
			for entry in data[call]['entries']:
				print(colorama.Fore.BLUE + entry['title'] + colorama.Fore.RESET)
				print(colorama.Fore.BLUE + entry['description'] + colorama.Fore.RESET)
				print('————————————————————')
				x = extract(entry)
				pp.pprint(x)
				print()
				print('————————————————————')
				print()
		else:
			print(colorama.Fore.BLUE + data[call]['title'] + colorama.Fore.RESET)
			print(colorama.Fore.BLUE + data[call]['description'] + colorama.Fore.RESET)
			print('————————————————————')
			x = extract(data[call])
			pp.pprint(x)
			print()
			print('————————————————————')
			print()