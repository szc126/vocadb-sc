#!/usr/bin/env python3

"""
TODO:
	- what happens in an edit conflict?
	- 'it is an original pv because vocadb detected the producer after i gave it the link'
		- FALSE, vocadb may also detect Some Producer such as with a bad parsing of '鏡音リン・レン'
	- new flag 'do not ask me if this is a reprint, i told you these are reprints and that will be correct 100% of the time'
	- allow to search by name more than once even if successful (fixing typo, trying with a different form, ...)
	- don't ask if the pv type is right before asking; ask for a choice 1 2 3, with a default
	- "ignore this song permanently. forever."

COLORS:
	- green: Good
	- yellow: Meh
	- red: Bad

	- reset: non-variable text
	- cyan: variable text

	- else arbitrary, whatever creates greatest visual distinction
		- the pretty-printed data is seriously tiring to the eyes when it is all blue
"""

import netrc
import requests # https://stackoverflow.com/questions/2018026/what-are-the-differences-between-the-urllib-urllib2-urllib3-and-requests-modul
import re
import sys
import colorama
import yt_dlp
import argparse
import json
import prompt_toolkit
import math
from diskcache import Cache

# XXX: rename from 'SC'ript to 'song-add' or something idk
# XXX: is this how classes work?
class SCPvTypes:
	ORIGINAL = 'Original'
	REPRINT = 'Reprint'
	OTHER = 'Other'

	@property
	def list(self):
		return [self.ORIGINAL, self.REPRINT, self.OTHER]
class SCUserGroupIds:
	NOTHING = 0
	LIMITED = 1
	REGULAR = 2
	TRUSTED = 3
	MOD = 4
	ADMIN = 5

	def from_str(self, string):
		return {
			'Nothing': self.NOTHING,
			'Limited': self.LIMITED,
			'Regular': self.REGULAR,
			'Trusted': self.TRUSTED,
			'Moderator': self.MOD,
			'Admin': self.ADMIN,
		}[string]
class SC:
	server = 'vocadb.net'
	pv_type = 2

	user_group_id = 0

	pv_types = SCPvTypes()
	user_group_ids = SCUserGroupIds()

	@property
	def h_server(self):
		return 'https://' + self.server

# ?
SC = SC()

session = requests.Session()
session.headers.update({
	'user-agent': 'https://github.com/szc126/vocadb-sc/blob/main/sc_song_add.py',
})

colorama.init(autoreset = True)

ytdl_config = {
	'usenetrc': True,
	'simulate': True,
	'ignoreerrors': True, # as with deleted videos in a YouTube playlist
	#'playliststart': SC.playliststart, # this part is run before main(), so user argument is not (cannot be) used
	#'playlistend': SC.playlistend,
}

# XXX: remove?
def print_e(*args, **kwargs):
	'''Print to standard error.'''

	print(*args, **kwargs, file = sys.stderr)

def print_p(*args, **kwargs):
	'''Pretty print using the pprint module.'''

	import pprint
	pp = pprint.PrettyPrinter(indent = 2)
	pp.pprint(*args, **kwargs)

# ----

def login() -> bool:
	'''Log in to VocaDB.'''

	netrc_auth = netrc.netrc().authenticators(SC.server)
	if not netrc_auth:
		raise LookupError(f'Could not find the {SC.server} machine in .netrc')

	print(f'Logging in to {colorama.Fore.CYAN}{SC.server}')
	_ = session.get(
		f'{SC.h_server}/api/antiforgery/token'
	)
	request = session.post(
		f'{SC.h_server}/api/users/login',
		json = {
			'userName': netrc_auth[0],
			'password': netrc_auth[2],
		},
		headers = {
			'requestVerificationToken': session.cookies.get_dict()['XSRF-TOKEN'],
			'Origin': 'https://vocadb.net', # XXX: hey is it letting me write "origin vocadb" for all domains?
		}
	)

	if request.status_code != 204:
		raise ValueError(
			f'Login failed. HTTP status code {request.status_code}' +
			'\n- ' + '\n- '.join(request.json()['errors'][''])
		)
	print(f'{colorama.Fore.GREEN}Logged in')
	return True

def verify_login_status(exception = True) -> bool:
	'''Verify login to VocaDB; record user group ID.'''

	print(f'Verifying login status for {colorama.Fore.CYAN}{SC.server}')
	request = session.get(
		f'{SC.h_server}/api/users/current',
	)
	if request.status_code != 200:
		if exception:
			raise ValueError(f'Login failed. HTTP status code {request.status_code}')
		else:
			print(f'{colorama.Fore.RED}Login failed. HTTP status code {request.status_code}')
			return False

	try:
		SC.user_group_id = SC.user_group_ids.from_str(request.json()['groupId'])
	except requests.exceptions.JSONDecodeError:
		# https://vocadb.net/User/Login?ReturnUrl=%2Fapi%2Fusers%2Fcurrent
		# (200 OK)
		print(f'{colorama.Fore.RED}Login failed. Expired login')
		return False

	print(f'{colorama.Fore.GREEN}Logged in{colorama.Fore.RESET} as {colorama.Fore.CYAN}' + request.json()['name'])
	return True

def save_cookies() -> bool:
	'''Save cookies to disk.'''

	with Cache(sys.argv[0] + '.cache/cookies') as cache:
		cache.set('cookies' + SC.server, session.cookies)
	print(f'{colorama.Fore.GREEN}Saved cookies{colorama.Fore.RESET}')
	return True

def load_cookies() -> bool:
	'''Load cookies from disk.'''

	try:
		with Cache(sys.argv[0] + '.cache/cookies') as cache:
			session.cookies.update(cache.get('cookies' + SC.server))
		print(f'{colorama.Fore.GREEN}Loaded cookies{colorama.Fore.RESET}')
		return True
	except TypeError:
		print(f'{colorama.Fore.RED}Could not find cookies')
		return False

# ----

def collect_urls() -> None:
	'''Collect URLs from standard input.'''

	urls = []
	print('Enter URLs (one per line). Enter "." when done.')
	while True:
		i = input()
		if i == '.':
			break
		if i.strip() == '' or i.startswith('#'):
			continue
		urls.append(i)
	return urls

def load_metadata_ytdl(urls, pattern_select = None, pattern_unselect = None):
	'''Load URL metadata using youtube-dl.'''
	# TODO: pattern_unselect

	print('Downloading URL metadata')
	infos = []
	with yt_dlp.YoutubeDL(ytdl_config) as ytdl:
		for url in urls:
			# ytdl_config differences do not affect the function signature
			# and the function signature is used as the key,
			# so reflect it in the filename instead
			cache = Cache(sys.argv[0] + '.cache/ytdl_extract_info.' + str(ytdl_config.get('playliststart', 0)) + '-' + str(ytdl_config.get('playlistend', 0)))
			info = cache.memoize()(ytdl.extract_info)(url)
			if info:
				infos += load_metadata_ytdl_recursive(info)
			else:
				print(f'{colorama.Fore.RED}URL is unavailable: {colorama.Fore.RESET}{url}')
		print()
	return infos

def load_metadata_ytdl_recursive(info) -> list:
	'''Retrieve videos from within nested youtube-dl playlists.'''
	# example: giving youtube-dl a YouTube channel

	if '_type' in info and info['_type'] == 'playlist':
		ret = []
		for entry in info['entries']:
			if entry is None:
				# as with deleted videos in a YouTube playlist
				continue
			else:
				ret += load_metadata_ytdl_recursive(entry)
		return ret
	else:
		return [info]

def load_metadata_ytbulk(filename, pattern_select = None, pattern_unselect = None):
	'''
	Load URL metadata from within a local ZIP file.
	See https://github.com/mattwright324/youtube-metadata.
	'''

	import zipfile

	print('Reading from ' + filename)
	infos = []
	with zipfile.ZipFile(filename, 'r') as myzip:
		with myzip.open('videos.json') as myjson:
			data = json.load(myjson)
	# i hate math i hate computers i hate coding
	data = data[ytdl_config.get('playliststart', 1) - 1 : ytdl_config.get('playlistend')]
	for video in data:
		if pattern_select and not re.search(pattern_select, video['snippet']['title']):
			print('Unselected: ' + video['snippet']['title'])
			continue
		elif pattern_unselect and re.search(pattern_unselect, video['snippet']['title']):
			print('Unselected: ' + video['snippet']['title'])
			continue
		infos.append({
			'title': video['snippet']['title'],
			'uploader': video['snippet']['channelTitle'],
			'upload_date': video['snippet']['publishedAt'],
			'duration': re.sub(
				r'PT(\d+M)?(\d+S)?',
				lambda match: str(  int(match.group(1)[:-1] if match.group(1) else 0) * 60 + int(match.group(2)[:-1] if match.group(2) else 0)  ),
				video['contentDetails']['duration']
			),
			'webpage_url': 'https://www.youtube.com/watch?v=' + video['id'],
			'description': video['snippet']['description'],
		})
	return infos

def load_metadata_album(album_id):
	'''
	From a VocaDB album ID, fetch its Youtube Music playlist.
	'''

	# nah im not splitting this out into a new function. who cares
	request = session.get(
		f'{SC.h_server}/api/albums/{args.album_id}',
		params = {
			'fields': 'WebLinks,Tracks',
			'songFields': 'AdditionalNames', # same as `/api/songs/findDuplicate`
		}
	)
	# XXX: also fetch PVs and eliminate the need for lookup_videos()?
	# or maybe it's fine because there could be a possible mismatch between
	# song entry associated with the PV and
	# song entry listed in the album entry.
	# um.
	# XXX: detect that possible mismatch?

	# locate the youtube music link
	for weblink in request.json()['webLinks']:
		if weblink['url'].startswith('https://music.youtube.com/playlist'):
			# get playlist data
			infos = load_metadata_ytdl([weblink['url']])

	# length mismatch
	# causes:
	# - severely wrong information (wrong album)
	#_- streaming version simply has a different number of tracks
	# - video DVD
	if len(request.json()['tracks']) != len(infos):
		#raise Exception('length mismatch')
		# XXX
		pass

	for i, _ in enumerate(infos):
		# inject the VocaDB album data into the yt-dlp data
		infos[i]['vocadb_album_track'] = request.json()['tracks'][i]

		# why are there so many different keys for "url".
		infos[i]['webpage_url'] = infos[i]['url']

		# dummy description
		# to appease the part of lookup_videos() that rifles through the description for more URLs
		infos[i]['description'] = 'YouTube Music'

		# dummy upload date
		# to appease pretty_ytdl_info()
		infos[i]['upload_date'] = 'YouTube Music'

	return infos

cache_lookup_url = Cache(sys.argv[0] + '.cache/api-lookup-url')
@Cache.memoize(cache_lookup_url)
def lookup_url(info, title = None):
	'''Look up a URL in VocaDB.'''

	# undocumented api
	# https://vocadb.net/Song/Create?pvUrl=$foo
	request = session.get(
		f'{SC.h_server}/api/songs/findDuplicate',
		params = {
			'term[]': (title or ''),
			'pv[]': info['webpage_url'],
			'getPVInfo': True,
		}
	)

	# for debug: dump request
	#print(request.url)
	#print_p(request.json())

	return request

def lookup_videos(infos, pattern_title = None):
	'''Look up videos in VocaDB.'''

	print(f'Looking up in {colorama.Fore.CYAN}{SC.server}')
	infos_working = []
	for i, info in enumerate(infos, start = 1):
		print(f'{colorama.Fore.YELLOW}{i} / {len(infos)}')
		print(colorama.Fore.CYAN + info['title'])
		print(colorama.Fore.BLUE + info['webpage_url'])

		# for debug: we don't need direct download urls
		#info.pop('formats', None)
		#info.pop('requested_formats', None)
		#info.pop('thumbnails', None)

		# for debug: print the info
		#print_p(info)

		found_title = None
		found_title = (re.search(re.compile(pattern_title), info['title']) if pattern_title else found_title)
		found_title = (found_title.group(1) if found_title else found_title)

		pv_added = False

		request = lookup_url(info, title = found_title)
		for entry in request.json()['matches']:
			if entry['matchProperty'] == 'PV':
				pv_added = True
				break

		if pv_added:
			song_id = request.json()['matches'][0]['entry']['id']
			print(f'This PV is {colorama.Fore.GREEN}registered.')
			print('  ' + pretty_pv_match_entry(request.json()['matches'][0]).replace('\n', '\n  '))
			print()
			continue

		# look for additional urls ("original URL:")
		# XXX: maybe the original video is in vocadb but another found video is not in vocadb. always look all of these up?
		# XXX: or the original video link comes after all other links. めんどくせい
		# example: https://vocadb.net/S/11639 (cover) https://vocadb.net/S/580916 (cover)
		# XXX: or the original video description was copy-and-pasted, without a link to the actual original video. めんどくせい
		found_url_infos = []
		# `\b` is not appropriate for CJK like 'ニコ動sm9'
		for match in re.finditer(r'(?P<context>.{,10})(?P<id>https?://(?:www\.|)nicovideo\.jp/watch/[sn]m[0-9]+|\b[sn]m[0-9]+|(?<=[^A-Za-z])[sn]m[0-9]+)', info['description']):
			found_url_info = {
				'title': info['title'],
				'webpage_url': (not match['id'].startswith('http') and 'https://www.nicovideo.jp/watch/' or '') + match['id'],
			}
			if re.search(r'ニコ|転載|より|轉載|出處|bilibili', match.group('context')):
				# prioritize "original URL:" links
				# XXX: https://utaitedb.net/S/2655 reprint where 本家 refers to VOCALOID original upload instead of utaite original upload
				# for debug:
				#print('Context: ' + match['context'])
				found_url_infos.insert(0, found_url_info)
			else:
				found_url_infos.append(found_url_info)
		for match in re.finditer(r'(?P<context>.{,10})(?P<id>https?://(?:www\.|)bilibili\.(?:com|tv)/video/(av[0-9]+|BV[A-Za-z0-9]+)|\bav[0-9]+|BV[A-Za-z0-9]{12})', info['description']):
			found_url_info = {
				'title': info['title'],
				'webpage_url': (not match['id'].startswith('http') and 'https://www.bilibili.com/video/' or '') + match['id'].replace('bilibili.tv', 'bilibili.com'),
			}
			if re.search(r'bilibili|轉載|出處', match.group('context')):
				# prioritize "original URL:" links
				# for debug:
				#print('Context: ' + match['context'])
				found_url_infos.insert(0, found_url_info)
			else:
				found_url_infos.append(found_url_info)

		try:
			for found_url_info in found_url_infos:
				found_url_request = lookup_url(found_url_info, title = found_title)
				for entry in found_url_request.json()['matches']:
					if entry['matchProperty'] == 'PV':
						pv_added = True
						# https://stackoverflow.com/a/11944179
						# `break` does not stop outer loops,
						# so `found_url_request` will be overwritten with later url lookups
						raise StopIteration()
				# delete failed lookup from cache: re-lookup URL on next launch
				# 本家 was not in VocaDB
				cache_lookup_url.pop(lookup_url.__cache_key__(found_url_info, title = found_title))
		except StopIteration:
			pass

		if pv_added:
			infos_working.append((info, request, found_title, found_url_info, found_url_request))
			print(f'This PV {colorama.Fore.RED}is not registered.')
			print(f'A PV in the video description {colorama.Fore.YELLOW}is registered.')
			print()

			# delete failed lookup from cache: re-lookup URL on next launch
			cache_lookup_url.pop(lookup_url.__cache_key__(info, title = found_title))
		else:
			infos_working.append((info, request, found_title, False, False))
			print(f'This PV {colorama.Fore.RED}is not registered.')
			print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
			if found_url_infos:
				print(f'A PV in the video description {colorama.Fore.RED}is not registered.')
				print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={found_url_info["webpage_url"]}')
			print()

			# delete failed lookup from cache: re-lookup URL on next launch
			cache_lookup_url.pop(lookup_url.__cache_key__(info, title = found_title))
			if found_url_infos:
				cache_lookup_url.pop(lookup_url.__cache_key__(found_url_info, title = found_title))

	return infos_working

def register_videos(infos_working) -> None:
	'''Register videos in VocaDB.'''

	infos_skipped = []
	for i_infos, (info, request, found_title, found_url_info, found_url_request) in enumerate(infos_working, start = 1):
		print()
		print(f'{colorama.Fore.YELLOW}{i_infos} / {len(infos_working)}')
		if found_url_info:
			print(pretty_ytdl_info(info)
				.replace(found_url_info['webpage_url'], colorama.Fore.GREEN + found_url_info['webpage_url'] + ' \U0001f517' + colorama.Fore.BLUE)
			)
		else:
			print(pretty_ytdl_info(info))

		found_title_by_vocadb = request.json()['title']
		matches = request.json()['matches']

		if found_url_request:
			found_url_matches = found_url_request.json()['matches']

			if False:
				# some nested loop abomination courtesy of chatgpt
				# equivalent to a for-loop inside a for-loop
				# keep `fu_match` instead of `match` for the `match_property`
				matches_intersection = [fu_match for fu_match in found_url_matches for match in matches if fu_match['entry']['id'] == match['entry']['id']]
				if len(matches_intersection) > 0:
					matches = matches_intersection
				else:
					# if there is 0 overlap,
					# reject most of `found_url_matches`,
					# because it could be a PV match for
					# some other video in the description, like "新作→"
					matches = [fu_match for fu_match in found_url_matches if fu_match['matchProperty'] == 'PV'] + matches

			# 20240201: ignore the above.
			# example: https://vocadb.net/S/497078 cover of a popular song
			# original PV is registered; reprint is not registered
			# when looking up the reprint, the original is not among the "possible matches"
			# when looking up the original (URL found in description), the original is among the "possible matches", and so are the other wrong matches
			# and the intersection of those 2 excludes what we want
			# ----
			# in most situations, we still will have intersection, so let us take PV match and move it to the front
			found_url_matches = [fu_match for fu_match in found_url_matches if fu_match['matchProperty'] == 'PV']
			matches = found_url_matches + [match for match in matches if match['entry']['id'] != found_url_matches[0]['entry']['id']]

		if info['vocadb_album_track']:
			reformed = {
				'entry': info['vocadb_album_track']['song'],
			}
			# to appease pretty_pv_match_entry()
			reformed['entry']['name'] = {
				'additionalNames': info['vocadb_album_track']['song']['additionalNames'],
				'displayName': info['vocadb_album_track']['song']['defaultName'],
			}
			reformed['entry']['entryTypeName'] = info['vocadb_album_track']['song']['songType']
			reformed['matchProperty'] = 'YouTube Music'
			matches = [reformed] + matches

		while True:
			for i, match in enumerate(matches):
				print(colorama.Fore.YELLOW + str(i + 1).ljust(3) + pretty_pv_match_entry(match).replace('\n', '\n   '))
			print()

			# TODO:
			# - get upset if a match is a PV match (which happens when I manually add a PV behind the script's back)

			if matches:
				#if found_url_request:
				#	print(f'{colorama.Fore.YELLOW}Found matches, {colorama.Fore.CYAN}using video description')
				#else:
				#	print(f'{colorama.Fore.YELLOW}Found matches')
				print(f'{colorama.Fore.YELLOW}Found matches')

				match_n = 1
				while True:
					i = input(f'Choose match [1/...], or enter "https://{SC.server}/S/<song ID>", or enter "." to skip this URL: ')
					if i == '':
						break
					elif i.startswith(f'https://{SC.server}/S/'):
						try:
							match_n = int(i.removeprefix(f'https://{SC.server}/S/')) * -1 # ID as a negative integer
							break
						except ValueError:
							print(f'{colorama.Fore.RED}Invalid choice')
					elif i == '.':
						match_n = 0
						break
					else:
						try:
							match_n = int(i)
							print('  ' + pretty_pv_match_entry(matches[match_n - 1]).replace('\n', '\n  '))
							if input('Is this correct? [Y/n] ').casefold() != 'n':
								break
						except ValueError:
							print(f'{colorama.Fore.RED}Invalid choice')
						except IndexError:
							print(f'{colorama.Fore.RED}Invalid choice')
				if match_n == 0:
					print(f'{colorama.Fore.RED}Skipped')
					print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
					infos_skipped.append(info)
					break
				if match_n < 0:
					song_id = match_n * -1
					match_property = 'SC:manual'
				else:
					song_id = matches[match_n - 1]['entry']['id']
					match_property = matches[match_n - 1]['matchProperty']

				pv_type = SC.pv_types.list[SC.pv_type - 1]
				while True:
					i = input(f'PV type {colorama.Fore.CYAN}{pv_type}{colorama.Fore.RESET}. [continue/Original/Reprint/otHer] ').casefold()
					if i == '':
						break
					else:
						try:
							pv_type = {
								'o': SC.pv_types.ORIGINAL,
								'r': SC.pv_types.REPRINT,
								'h': SC.pv_types.OTHER,
							}[i]
							if input(f'{colorama.Fore.CYAN}{pv_type}{colorama.Fore.RESET}. Is this correct? [Y/n] ').casefold() != 'n':
								break
						except ValueError:
							print(f'{colorama.Fore.RED}Invalid choice')

				# undocumented api
				request_entry_data = session.get(
					f'{SC.h_server}/api/songs/{song_id}/for-edit'
				)

				if request_entry_data.json()['status'] == 'Approved':
					if SC.user_group_id < SC.user_group_ids.TRUSTED:
						input(f'{colorama.Fore.YELLOW}This entry is approved. You do not have the permissions to edit it. {colorama.Fore.RESET}Press enter to continue.')
						print(f'{colorama.Fore.RED}Skipped')
						infos_skipped.append(info)
						break

				# example: https://vocadb.net/S/8572
				if request_entry_data.json()['status'] == 'Locked':
					if SC.user_group_id < SC.user_group_ids.MOD:
						input(f'{colorama.Fore.YELLOW}This entry is locked. You do not have the permissions to edit it. {colorama.Fore.RESET}Press enter to continue.')
						print(f'{colorama.Fore.RED}Skipped')
						infos_skipped.append(info)
						break

				# undocumented api
				request_pv_data = session.get(
					f'{SC.h_server}/api/pvs',
					params = {
						'pvUrl': info['webpage_url'],
						'type': pv_type,
					}
				)

				# TODO:
				# we have the entry data. compare:
				# - video titles
				# - all video lengths
				# - video date

				if request_entry_data.json()['lengthSeconds'] > 0 and not math.isclose(request_pv_data.json()['length'], request_entry_data.json()['lengthSeconds'], abs_tol = 2):
					if input(
							f'{colorama.Fore.YELLOW}Track length does not match.' +
							f'{colorama.Fore.RESET} (PV: ' +
							colorama.Fore.CYAN + pretty_duration(request_pv_data.json()['length']) +
							f'{colorama.Fore.RESET}, entry: ' +
							colorama.Fore.CYAN + pretty_duration(request_entry_data.json()['lengthSeconds']) +
							f'{colorama.Fore.RESET}) Skip this entry? [Y/n] '
					).casefold() != 'n':
						print(f'{colorama.Fore.RED}Skipped')
						infos_skipped.append(info)
						break

				entry_data_modified = request_entry_data.json()
				entry_data_modified['pvs'].append(request_pv_data.json())

				if match_property == 'PV':
					entry_data_modified['updateNotes'] = f'[sc] (ID match) Add {pv_type}: {info["title"]}'
				elif match_property == 'YouTube Music':
					entry_data_modified['updateNotes'] = f'[sc] (YouTube Music) Add {pv_type}: {info["title"]}'
				elif match_property == 'SC:manual':
					entry_data_modified['updateNotes'] = f'[sc] (manual) Add {pv_type}: {info["title"]}'
				else:
					entry_data_modified['updateNotes'] = f'[sc] Add {pv_type}: {info["title"]}'

				_ = session.get(
					f'{SC.h_server}/api/antiforgery/token'
				)
				# undocumented api
				request_save = session.post(
					f'{SC.h_server}/api/songs/{song_id}',
					headers = {
						'requestVerificationToken': session.cookies.get_dict()['XSRF-TOKEN'],
					},
					files = {
						'contract': (None, json.dumps(entry_data_modified))
					},
				)

				if request_save.status_code == 200:
					print(f'{colorama.Fore.GREEN}Saved{colorama.Fore.RESET}: {colorama.Fore.CYAN}{SC.h_server}/S/{song_id}')
				else:
					print_p(entry_data_modified)
					raise ValueError(f'Save failed. HTTP status code {request_save.status_code}')

				break
			else:
				print(f'{colorama.Fore.YELLOW}No matches' + (f'{colorama.Fore.RESET} for {colorama.Fore.CYAN}{found_title}{colorama.Fore.RESET}.' if found_title else ''))
				i = prompt_toolkit.prompt('Search by name, or add "." to skip this entry: ', default = found_title or found_title_by_vocadb)
				if i == (found_title or found_title_by_vocadb) + '.' or i == '':
					print(f'{colorama.Fore.RED}Skipped')
					print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
					infos_skipped.append(info)
					break
				request = lookup_url(info, title = i)
				# found_title is no longer relevant. don't print it a second time
				found_title = i
				matches = request.json()['matches']
	if len(infos_skipped) > 0:
		print('----')
		print(f'{colorama.Fore.RED}Skipped URLs:')
		for info in infos_skipped:
			print(info['webpage_url'] + ' # ' + info['title'])
			# TODO: option to restart immediately but with utaitedb?
	print('----')
	print(f'All URLs have been {colorama.Fore.GREEN}processed.')

def pretty_pv_match_entry(match):
	'''Format the data returned by /api/songs/findDuplicate.'''
	# saner than a print() (unless you like keys ordered alphabetically)
	# and add a link to *db.net/S/ as well

	display_name = match['entry']['name']['displayName']
	additional_names = match['entry']['name']['additionalNames']
	artist_string = match['entry']['artistString']
	url_db_s = SC.h_server + '/S/' + str(match['entry']['id'])
	entry_type_name = match['entry']['entryTypeName']
	match_property = match['matchProperty']

	if match_property == 'PV':
		match_property = colorama.Fore.GREEN + match_property + ' \U0001f517' + colorama.Fore.RESET
	elif match_property == 'YouTube Music':
		match_property = colorama.Fore.GREEN + match_property + ' \U0001f534' + colorama.Fore.RESET
	else:
		match_property = colorama.Fore.MAGENTA + match_property

	return '\n'.join(filter(None, [
		colorama.Fore.CYAN + display_name + (colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + additional_names if additional_names else '') + colorama.Fore.RESET,
		artist_string + colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + entry_type_name,
		colorama.Fore.BLUE + url_db_s + colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + match_property,
	]))

def pretty_ytdl_info(info):
	'''Format the data returned by youtube-dl.'''

	title = info['title']
	uploader = info['uploader']
	upload_date = info['upload_date']
	duration = pretty_duration(info['duration'])
	webpage_url = info['webpage_url']
	description = info['description'] if 'description' in info else None

	return '\n'.join(filter(None, [
		colorama.Fore.CYAN + title + (colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + duration if duration else ''),
		colorama.Fore.RESET + uploader + (colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + upload_date if upload_date else ''),
		colorama.Fore.BLUE + webpage_url,
		(
			colorama.Fore.RESET + '  ----' + '\n' +
			colorama.Fore.BLUE + '  ' + description.replace('\n', '\n  ')
		) if description else (
			''
		),
	]))

def pretty_duration(seconds):
	'''Reformat a duration (seconds) as M:SS.'''

	return str(int(seconds) // 60) + ':' + str(int(seconds) % 60).zfill(2)

# ----

def main(args):
	SC.server = args.server or SC.server
	SC.pv_type = args.pv_type or SC.pv_type

	# youtube-dl won't accept None or False :(
	if args.list_from:
		ytdl_config['playliststart'] = args.list_from
	if args.list_to:
		ytdl_config['playlistend'] = args.list_to

	if args.album_id:
		# only get playlist information, not video information
		ytdl_config['extract_flat'] = True
		# designate as official upload
		SC.pv_type = 1

		# reduce an URL to just the ID
		if 'https://' in args.album_id:
			args.album_id = args.album_id.split('/')[-1]

	if not (load_cookies() and verify_login_status(exception = False)):
		login()
		verify_login_status(exception = True)
		save_cookies()
	print()

	# ----

	urls = args.urls
	infos = None

	if args.ytbulk:
		infos = load_metadata_ytbulk(args.ytbulk, pattern_select = args.pattern_select, pattern_unselect = args.pattern_unselect)
	elif args.album_id:
		infos = load_metadata_album(args.album_id)
	else:
		if not urls:
			urls = collect_urls()
		infos = load_metadata_ytdl(urls, pattern_select = args.pattern_select, pattern_unselect = args.pattern_unselect)
	infos = lookup_videos(infos, pattern_title = args.pattern_title)
	print('----')
	register_videos(infos)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		description = '',
	)
	parser.add_argument(
		'--server',
		help = 'server to connect to. default: ' + SC.server,
	)
	parser.add_argument(
		'--pv-type',
		dest = 'pv_type',
		type = int,
		choices = range(1, len(SC.pv_types.list) + 1),
		help = 'default PV type. ' + str(list(enumerate(SC.pv_types.list, start = 1))),
	)
	parser.add_argument(
		'--from',
		'-f',
		# https://stackoverflow.com/q/9746838
		dest = 'list_from',
		type = int,
		help = 'start from (inclusive) video N of a playlist (or channel)',
	)
	parser.add_argument(
		'--to',
		'-t',
		dest = 'list_to',
		type = int,
		help = 'stop on (inclusive) video N of a playlist (or channel)',
	)
	parser.add_argument(
		'--parse',
		'--title',
		dest = 'pattern_title',
		help = 'regular expression to parse a video title. accepts one capture group, which will be the title. example: /初音ミク　(.+)/ (without slash)',
	)
	parser.add_argument(
		'--select',
		dest = 'pattern_select',
		help = 'regular expression to select by video title. --select has precedence over --unselect. example: /歌ってみた/ (without slash)',
	)
	parser.add_argument(
		'--unselect',
		'--deselect',
		dest = 'pattern_unselect',
		help = 'regular expression to unselect by video title. example: /(?i)mmd|mikumikudance|実況プレイ/ (without slash)',
	)
	parser.add_argument(
		'urls',
		nargs = '*',
		metavar = 'URL',
		help = 'URL(s) to process',
		# use '--' before an URL that begins with a hyphen
		# https://docs.python.org/dev/library/argparse.html#arguments-containing
	)
	parser.add_argument(
		'--ytbulk',
		#type = argparse.FileType('r'),
		help = 'bulk_metadata.zip to process, from https://github.com/mattwright324/youtube-metadata',
	)
	parser.add_argument(
		'--albumid',
		'--alid',
		dest = 'album_id',
		metavar = 'albumID',
		help = 'VocaDB album ID (or URL); a YouTube Music URL will be located on its entry for usage',
	)
	args = parser.parse_args()

	main(args)
