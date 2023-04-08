#!/usr/bin/env python3

"""
TODO:
	- unintelligent matching of an album to a playlist. the album has 10 tracks, the playlist has 10 tracks, we are golden
	- what happens in an edit conflict?
	- 'it is an original pv because the producer was detected as the uploader'
		- FALSE, it may be a false positive, such as with a bad parsing of '鏡音リン・レン'
		- 2023/04/07: ?? what does this mean.
	- new flag 'do not ask me if this is a reprint, i told you these are reprints and that will be correct 100% of the time'
	- allow to search by name more than once even if successful (fixing typo, trying with a different form, ...)
	- don't ask if the pv type is right before asking; ask for a choice 1 2 3, with a default
	- add progress indicator (where?)
	- why did i want to print to stderr? i forget
	- (maybe?) regex with named groups for vocalist too
	- check against video length instead of / in addition to entry recorded length?
	- check if reprint/other is earlier than entry recorded publish date (automatic ng)
	- "ignore this song permanently. forever."

PATH FROM HERE:
	- manual intervention
		- constrain search results to a certain producer
		- apply user-supplied regex to title
		- search using video description links ('本家：sm00000000')
			- look up ~that~ pv, and choose the song entry that comes up a second time
		- manually give song ID
			- bc the web interface is kinda bothersome tbh

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
import pickle
import yt_dlp
import argparse
import json
import prompt_toolkit
import math

from disk_cache_decorator import disk_cache_decorator # local module

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

def print_e(*args, **kwargs):
	'''Print to standard error.'''

	print(*args, **kwargs, file = sys.stderr)

def print_p(*args, **kwargs):
	'''Pretty print using the pprint module.'''

	import pprint
	pp = pprint.PrettyPrinter(indent=2)
	pp.pprint(*args, **kwargs)

# ----

def login() -> bool:
	'''Log in to *DB.'''

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
	'''Check if we are logged in to **DB.

	Record user group ID.'''

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

	SC.user_group_id = SC.user_group_ids.from_str(request.json()['groupId'])

	print(f'{colorama.Fore.GREEN}Logged in{colorama.Fore.RESET} as {colorama.Fore.CYAN}' + request.json()['name'])
	return True

def save_cookies() -> bool:
	'''Save cookies to disk.'''

	filename = sys.argv[0] + '.cookies' + '.' + SC.server + '.pickle'
	with open(filename, 'wb') as file:
		pickle.dump(session.cookies, file)
	print(f'{colorama.Fore.GREEN}Saved cookies{colorama.Fore.RESET} to {colorama.Fore.CYAN}{filename}')
	return True

def load_cookies() -> bool:
	'''Load cookies from disk.'''

	try:
		filename = sys.argv[0] + '.cookies' + '.' + SC.server + '.pickle'
		with open(filename, 'rb') as file:
			session.cookies.update(pickle.load(file))
		print(f'{colorama.Fore.GREEN}Loaded cookies{colorama.Fore.RESET} from {colorama.Fore.CYAN}{filename}')
		return True
	except FileNotFoundError:
		print(f'{colorama.Fore.RED}Could not find cookies')
		return False
	except pickle.UnpicklingError:
		print(f'{colorama.Fore.RED}Could not read cookies')
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

def get_ytdl_info(urls):
	''''''

	infos = []
	print('Downloading URL metadata')
	with yt_dlp.YoutubeDL(ytdl_config) as ytdl:
		for url in urls:
			filename_pickle = sys.argv[0] + '.ytdl_extract_info.' + (str('playliststart' in ytdl_config and ytdl_config['playliststart'] or '')) + '-' + (str('playlistend' in ytdl_config and ytdl_config['playlistend'] or '')) + '.pickle' # ytdl_config differences are invisible to disk_cache_decorator()
			info = disk_cache_decorator(filename_pickle)(ytdl.extract_info)(url)
			infos += recursive_get_ytdl_individual_info(info)
		print()
	return infos

def process_ytbulk(filename):
	''''''

	infos = []
	with open(filename, 'r') as file:
		data = json.load(file)
		data = data['playliststart' in ytdl_config and ytdl_config['playliststart'] or None : 'playlistend' in ytdl_config and ytdl_config['playlistend'] or None]
		for video in data:
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

def lookup_url(info, title = None):
	''''''

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

def process_urls(infos, regex = None) -> None:
	''''''

	print(f'Looking up in {colorama.Fore.CYAN}{SC.server}')
	infos_working = []
	for i, info in enumerate(infos):
		print(f'{colorama.Fore.YELLOW}{i + 1} / {len(infos)}')
		print(colorama.Fore.CYAN + info['title'])
		print(colorama.Fore.BLUE + info['webpage_url'])

		# for debug: we don't need direct download urls
		#info.pop('formats', None)
		#info.pop('requested_formats', None)
		#info.pop('thumbnails', None)

		# for debug: print the info
		#print_p(info)

		found_title = None
		found_title = (re.search(re.compile(regex), info['title']) if regex else found_title)
		found_title = (found_title.group(1) if found_title else found_title)

		pv_added = False
		filename_pickle = sys.argv[0] + '.api-song-lookup.pickle'

		request = disk_cache_decorator(filename_pickle)(lookup_url)(info, title = found_title)
		if request.json()['matches']:
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

		# look for additional urls (「○○より転載」)
		# XXX: maybe the original video is in vocadb but the found video is not in vocadb. always look all of these up?
		found_url_infos = []
		for match in re.finditer(r'https?://(?:www\.|)nicovideo\.jp/watch/[sn]m[0-9]+|\b[sn]m[0-9]+', info['description']):
			found_url_infos.append({
				'title': info['title'],
				'webpage_url': (not match.group(0).startswith('http') and 'https://www.nicovideo.jp/watch/' or '') + match.group(0),
			})

		for found_url_info in found_url_infos:
			found_url_request = disk_cache_decorator(filename_pickle)(lookup_url)(found_url_info, title = found_title)
			if found_url_request.json()['matches']:
				for entry in found_url_request.json()['matches']:
					if entry['matchProperty'] == 'PV':
						pv_added = True
						break

		if pv_added:
			infos_working.append((info, request, found_title, found_url_request))
			print(f'This PV {colorama.Fore.RED}is not registered.')
			print(f'A PV in the video description {colorama.Fore.YELLOW}is registered.')
			print()

			# delete failed lookup from cache
			disk_cache_decorator(filename_pickle, delete_cache = True)(lookup_url)(info, title = found_title)
			disk_cache_decorator(filename_pickle, delete_cache = True)(lookup_url)(found_url_info, title = found_title)
		else:
			infos_working.append((info, request, found_title, False))
			print(f'This PV {colorama.Fore.RED}is not registered.')
			print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
			print()

			# delete failed lookup from cache
			disk_cache_decorator(filename_pickle, delete_cache = True)(lookup_url)(info, title = found_title)

	print('----')

	i_infos = 1
	for info, request, found_title, found_url_request in infos_working:
		print()
		print(f'{colorama.Fore.YELLOW}{i_infos} / {len(infos_working)}')
		print(pretty_youtubedl_info(info))

		if found_url_request:
			request = found_url_request

		while True:
			for i, match in enumerate(request.json()['matches']):
				print(colorama.Fore.YELLOW + str(i + 1).ljust(3) + pretty_pv_match_entry(match).replace('\n', '\n   '))
			print()

			# TODO:
			# - get upset if a match is a PV match (which happens when I manually add a PV behind the script's back)

			if request.json()['matches']:
				if found_url_request:
					print(f'{colorama.Fore.YELLOW}Found matches, {colorama.Fore.CYAN}using video description')
				else:
					print(f'{colorama.Fore.YELLOW}Found matches')

				match_n = 1
				while True:
					i = input('Choose match [1/...], or enter "s<song ID>", or enter "." to skip this URL: ')
					if i == '':
						break
					elif i[0] == 's':
						try:
							match_n = int(i[1:]) * -1 # ID as a negative integer
							break
						except ValueError:
							print(f'{colorama.Fore.RED}Invalid choice')
					elif i == '.':
						match_n = 0
						break
					else:
						try:
							match_n = int(i)
							print('  ' + pretty_pv_match_entry(request.json()['matches'][match_n - 1]).replace('\n', '\n  '))
							if input('Is this correct? [Y/n] ').casefold() != 'n':
								break
						except ValueError:
							print(f'{colorama.Fore.RED}Invalid choice')
						except IndexError:
							print(f'{colorama.Fore.RED}Invalid choice')
				if match_n == 0:
					print(f'{colorama.Fore.RED}Skipped')
					print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
					break
				if match_n < 0:
					song_id = match_n * -1
				else:
					song_id = request.json()['matches'][match_n - 1]['entry']['id']

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
				# - <s>video length</s>

				if request_entry_data.json()['lengthSeconds'] > 0 and not math.isclose(request_pv_data.json()['length'], request_entry_data.json()['lengthSeconds'], abs_tol = 2):
					if input(
							f'{colorama.Fore.YELLOW}Track length does not match.' +
							f'{colorama.Fore.RESET} (PV: ' +
							colorama.Fore.CYAN + pretty_duration(request_pv_data.json()['length']) +
							f'{colorama.Fore.RESET}, entry:' +
							colorama.Fore.CYAN + pretty_duration(request_entry_data.json()['lengthSeconds']) +
							f'{colorama.Fore.RESET}) Skip this entry? [y/N] '
					).casefold() != 'n':
						print(f'{colorama.Fore.RED}Skipped')
						break

				entry_data_modified = request_entry_data.json()
				entry_data_modified['pvs'].append(request_pv_data.json())
				entry_data_modified['updateNotes'] = f'[assisted] Add {pv_type}: {info["title"]}'

				_ = session.get(
					f'{SC.h_server}/api/antiforgery/token'
				)
				# undocumented not-api
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
				print(f'{colorama.Fore.YELLOW}No matches' + (f'{colorama.Fore.RESET} for {colorama.Fore.CYAN}{found_title}.' if found_title else ''))
				i = prompt_toolkit.prompt('Search by name, or add "." to skip this entry: ', default = found_title or request.json()['title'])
				if i == (found_title or request.json()['title']) + '.' or i == '':
					print(f'{colorama.Fore.RED}Skipped')
					print(f'Create a new entry? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?pvUrl={info["webpage_url"]}')
					break
				request = lookup_url(info, title = i)
				# found_title is no longer relevant. don't print it a second time
				found_title = i
		i_infos += 1
	print()
	print(f'All URLs have been {colorama.Fore.GREEN}processed.')

def recursive_get_ytdl_individual_info(info) -> list:
	'''Helper for flattening nested youtube-dl playlists.'''
	# example: giving youtube-dl a YouTube channel

	if '_type' in info and info['_type'] == 'playlist':
		ret = []
		for entry in info['entries']:
			if entry is None:
				# as with deleted videos in a YouTube playlist
				continue
			else:
				ret += recursive_get_ytdl_individual_info(entry)
		return ret
	else:
		return [info]

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

	return '\n'.join(filter(None, [
		colorama.Fore.CYAN + display_name + (colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + additional_names if additional_names else '') + colorama.Fore.RESET,
		artist_string + colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + entry_type_name,
		colorama.Fore.BLUE + url_db_s + colorama.Fore.MAGENTA + ' // ' + colorama.Fore.RESET + match_property,
	]))

def pretty_youtubedl_info(info):
	'''Format the info extracted by youtube-dl.'''

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

	if not (load_cookies() and verify_login_status(exception = False)):
		login()
		verify_login_status(exception = True)
		save_cookies()
	print()

	# ----

	urls = args.urls
	info = None

	if args.ytbulk:
		info = process_ytbulk(args.ytbulk)
	else:
		if not urls:
			urls = collect_urls()
		info = get_ytdl_info(urls)
	process_urls(info, regex = args.regex)

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
		help = 'start from video N of a playlist (or channel)',
	)
	parser.add_argument(
		'--to',
		'-t',
		dest = 'list_to',
		type = int,
		help = 'stop before video N of a playlist (or channel)',
	)
	parser.add_argument(
		'--regex',
		help = 'regular expression to parse a video title. accepts one capture group, which will be the title',
	)
	parser.add_argument(
		'urls',
		nargs = '*',
		metavar = 'URL',
		help = 'URL(s) to process'
		# use '--' before an URL that begins with a hyphen
		# https://docs.python.org/dev/library/argparse.html#arguments-containing
	)
	parser.add_argument(
		'--ytbulk',
		#type = argparse.FileType('r'),
		help = 'videos.json to process, from https://mattw.io/youtube-metadata/bulk',
	)
	args = parser.parse_args()

	main(args)
