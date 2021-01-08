#!/usr/bin/env python3

"""
TODO:
	- unintelligent matching of an album to a playlist. the album has 10 tracks, the playlist has 10 tracks, we are golden
	- what happens in an edit conflict?
	- 'it is an original pv because the producer was detected as the uploader'
		- FALSE, it may be a false positive, such as with a bad parsing of '鏡音リン・レン'
	- new flag 'do not ask me if this is a reprint, i told you these are reprints and that will be correct 100% of the time'
	- allow to search by name more than once even if successful (fixing typo, trying with a different form, ...)
	- don't ask if the pv type is right before asking; ask for a choice 1 2 3, with a default
	- add progress indicator (where?)
	- why did i want to print to stderr? i forget

PATH FROM HERE:
	- manual intervention
		- constrain search results to a certain producer
		- apply user-supplied regex to title
		- search using video description links ('本家：sm00000000')
			- look up ~that~ pv, and choose the song entry that comes up a second time
"""

import netrc
import requests # https://stackoverflow.com/questions/2018026/what-are-the-differences-between-the-urllib-urllib2-urllib3-and-requests-modul
import bs4
import re
import sys
import colorama
import pickle
import youtube_dl
import argparse
import json
import prompt_toolkit
from disk_cache_decorator import disk_cache_decorator # cache data to disk
import re

# XXX: what can i call this script? 'SC'ript and 'a.py' are obviously terrible names
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
			'Mod': self.MOD,
			'Admin': self.ADMIN,
		}[string]
class SC:
	server = 'vocadb.net'
	urls = []
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
	'user-agent': 'https://github.com/szc126/vocadb-sc/blob/main/a.py',
})

colorama.init(autoreset = True)

ytdl_config = {
	'usenetrc': True,
	'simulate': True,
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

	print_e(f'Logging in to {colorama.Fore.CYAN}{SC.server}')
	request = session.post(
		f'{SC.h_server}/User/Login',
		{
			'UserName': netrc_auth[0],
			'Password': netrc_auth[2],
		}
	)
	if 'Unable to log in' in request.text:
		raise ValueError(
			'\n' +
			bs4.BeautifulSoup(request.text, features = 'html5lib')
				.find(string = re.compile('Unable to log in'))
				.parent
				.parent
				.prettify()
		)
	print_e(f'{colorama.Fore.GREEN}Login successful')
	return True

def verify_login_status(exception = True) -> bool:
	'''Check if we are logged in to **DB.

	Record user group ID.'''

	print_e(f'Verifying login status for {colorama.Fore.CYAN}{SC.server}')
	request = session.get(
		f'{SC.h_server}/api/users/current',
	)
	if request.status_code != 200:
		if exception:
			raise ValueError(f'Verification failed')
		else:
			print_e(f'{colorama.Fore.RED}Verification failed')
			return False

	SC.user_group_id = SC.user_group_ids.from_str(request.json()['groupId'])

	print_e(f'{colorama.Fore.GREEN}Logged in{colorama.Fore.RESET} as {colorama.Fore.CYAN}' + request.json()['name'])
	return True

def save_cookies() -> bool:
	'''Save cookies to disk.'''

	filename = sys.argv[0] + '.cookies.pickle'
	with open(filename, 'wb') as file:
		pickle.dump(session.cookies, file)
	print_e(f'{colorama.Fore.GREEN}Cookies saved{colorama.Fore.RESET} to {colorama.Fore.CYAN}{filename}')
	return True

def load_cookies() -> bool:
	'''Load cookies from disk.'''

	try:
		filename = sys.argv[0] + '.cookies.pickle'
		with open(filename, 'rb') as file:
			session.cookies.update(pickle.load(file))
		print_e(f'{colorama.Fore.GREEN}Cookies loaded{colorama.Fore.RESET} from {colorama.Fore.CYAN}{filename}')
		return True
	except FileNotFoundError:
		print_e(f'{colorama.Fore.RED}Cookies not found')
		return False
	except pickle.UnpicklingError:
		print_e(f'{colorama.Fore.RED}Failed to decode cookies')
		return False

# ----

def collect_urls() -> None:
	'''Collect URLS from standard input.'''

	print_e('Enter URLs, one per line. Enter "." when done.')
	while True:
		i = input()
		if i == '.':
			break
		if i.strip() == '' or i.startswith('#'):
			continue
		SC.urls.append(i)

def process_urls() -> None:
	''''''

	infos = []
	print_e('Fetching video information')
	with youtube_dl.YoutubeDL(ytdl_config) as ytdl:
		for url in SC.urls:
			filename_pickle = sys.argv[0] + '.ytdl_extract_info.' + (str('playliststart' in ytdl_config and ytdl_config['playliststart'] or '')) + '-' + (str('playlistend' in ytdl_config and ytdl_config['playlistend'] or '')) + '.pickle' # ytdl_config differences are invisible to disk_cache_decorator()
			info = disk_cache_decorator(filename_pickle)(ytdl.extract_info)(url)
			infos = infos + recursive_get_ytdl_individual_info(info)
		print()

	infos_working = []
	for info in infos:
		print(colorama.Back.BLUE + colorama.Fore.WHITE + info['title'])
		print(colorama.Back.BLUE + colorama.Fore.WHITE + info['webpage_url'])

		# for debug: we don't need direct download urls
		info.pop('formats', None)
		info.pop('requested_formats', None)
		info.pop('thumbnails', None)

		# for debug: print the info
		#print_p(info)

		filename_pickle = sys.argv[0] + '.api-songs-findDuplicate.pickle'
		# undocumented api
		# https://vocadb.net/Song/Create?PVUrl=$foo
		request = disk_cache_decorator(filename_pickle)(session.get)(
			f'{SC.h_server}/api/songs/findDuplicate',
			params = {
				'term': None, # names
				'pv': info['webpage_url'],
				'getPVInfo': True,
			}
		)

		# for debug: dump request
		#print(request.url)
		#print_p(request.json())

		pv_added = False
		if request.json()['matches']:
			for entry in request.json()['matches']:
				if entry['matchProperty'] == 'PV':
					pv_added = True
		if pv_added:
				song_id = request.json()['matches'][0]['entry']['id']
				print(f'This PV {colorama.Fore.GREEN}has already been added {colorama.Fore.RESET}to the database. {colorama.Fore.CYAN}{SC.h_server}/S/{song_id}')
				print()
		else:
			infos_working.append((info, request))
			print(f'This PV {colorama.Fore.RED}has not been added {colorama.Fore.RESET}to the database yet')
			print(f'Add it? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?PVUrl={info["webpage_url"]}')
			print()

			# for the purpose of delete_cache; this should not be an actual request
			_ = disk_cache_decorator(filename_pickle, delete_cache = True)(session.get)(
				f'{SC.h_server}/api/songs/findDuplicate',
				params = {
					'term': None, # names
					'pv': info['webpage_url'],
					'getPVInfo': True,
				}
			)

	print('----')

	i_infos = 1
	for info, request in infos_working:
		while True:
			print()
			print(f'{colorama.Fore.YELLOW}{i_infos} / {len(infos_working)}')
			print(colorama.Fore.BLUE + info['title'])
			print(colorama.Fore.BLUE + info['uploader'])
			print(colorama.Fore.BLUE + info['webpage_url'])
			print('----')
			print(colorama.Fore.BLUE + (info['description'] or colorama.Fore.RESET + '<no description>'))

			for i in range(len(request.json()['matches'])):
				print(f'{colorama.Fore.YELLOW}{i + 1}')
				print(
					re.sub(
						r'(^|\n)',
						r'\1  ',
						pretty_pv_match_entry(request.json()['matches'][i]['entry'])
					)
				)
			print()

			if request.json()['matches']:
				print(f'{colorama.Fore.YELLOW}Match potentially found')

				match_n = '1'
				while True:
					i = input('Choose match [1/...], or enter "." to skip this entry: ')
					if i == '':
						break
					elif i == '.':
						print(f'{colorama.Fore.RED}Skipped')
						match_n = '.'
						break
					else:
						try:
							match_n = int(i)
							print(
								re.sub(
									r'(^|\n)',
									r'\1  ',
									pretty_pv_match_entry(request.json()['matches'][match_n - 1]['entry'])
								)
							)
							if input('Is this correct? [Y/n] ').casefold() != 'n':
								break
						except ValueError:
							print_e(f'{colorama.Fore.RED}Not a valid choice')
						except IndexError:
							print_e(f'{colorama.Fore.RED}Not a valid choice')
				if match_n == '.':
					break

				song_id = request.json()['matches'][int(match_n) - 1]['entry']['id']
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
							print_e(f'{colorama.Fore.RED}Not a valid choice')

				# undocumented api
				request_entry_data = session.get(
					f'{SC.h_server}/api/songs/{song_id}/for-edit'
				)

				if request_entry_data.json()['status'] == 'Approved':
					if SC.user_group_id < SC.user_group_ids.TRUSTED:
						print(f'{colorama.Fore.YELLOW}This entry is approved. You do not have the permissions to edit it.')
						input('Press enter to continue.')
						break

				# undocumented api
				request_pv_data = session.get(
					f'{SC.h_server}/api/pvs',
					params = {
						'pvUrl': info['webpage_url'],
						'type': pv_type,
					}
				)

				entry_data_modified = request_entry_data.json()
				entry_data_modified['pvs'].append(request_pv_data.json())
				entry_data_modified['updateNotes'] = f'[assisted] Add {pv_type}: {info["title"]}'

				# TODO:
				# we have the entry data. compare:
				# - video titles
				# - video length

				# undocumented not-api
				request_save = session.post(
					f'{SC.h_server}/Song/Edit/{song_id}',
					{
						'EditedSong': json.dumps(entry_data_modified),
					}
				)

				if request_save.status_code == 200:
					print(f'{colorama.Fore.GREEN}Success{colorama.Fore.RESET}; {colorama.Fore.CYAN}{SC.h_server}/S/{song_id}')
				else:
					print_p(entry_data_modified)
					raise ValueError(f'Failed to save. HTTP status code {request_save.status_code}')

				break
			else:
				print(f'{colorama.Fore.YELLOW}Match not found')
				# undocumented api
				# https://vocadb.net/Song/Create?PVUrl=$foo
				i = prompt_toolkit.prompt('Search by name, or enter "." to skip this entry: ', default = request.json()['title'])
				if i == '.':
					print(f'{colorama.Fore.RED}Skipped')
					break
				request = session.get(
					f'{SC.h_server}/api/songs/findDuplicate',
					params = {
						'term': i,
						'pv': info['webpage_url'],
						'getPVInfo': True,
					}
				)
		i_infos += 1
	print()
	print(f'{colorama.Fore.GREEN}Batch complete')

def recursive_get_ytdl_individual_info(info) -> list:
	'''Helper for flattening nested youtube-dl playlists.'''
	# example: giving youtube-dl a YouTube channel

	if '_type' in info and info['_type'] == 'playlist':
		ret = []
		for entry in info['entries']:
			ret = ret + recursive_get_ytdl_individual_info(entry)
		return ret
	else:
		return [info]

def pretty_pv_match_entry(entry):
	'''Format the data returned by /api/songs/findDuplicate.'''
	# saner than a print() (unless you like keys ordered alphabetically)
	# and add a link to *db.net/S/ as well

	return (
		colorama.Fore.CYAN + entry['name']['displayName'] + colorama.Fore.RESET + (' // ' + entry['name']['additionalNames'] if entry['name']['additionalNames'] else '') + '\n' +
		colorama.Fore.CYAN + entry['artistString'] + '\n' +
		colorama.Fore.CYAN + SC.h_server + '/S/' + str(entry['id']) + colorama.Fore.RESET + ' // ' + entry['entryTypeName']
	)

# ----

def main(server = None, urls = None, pv_type = None, playliststart = None, playlistend = None):
	SC.server = server or SC.server
	SC.urls = urls or SC.urls
	SC.pv_type = pv_type or SC.pv_type

	# youtube-dl won't accept None or False, complicating everything
	if playliststart:
		ytdl_config['playliststart'] = playliststart
	if playlistend:
		ytdl_config['playlistend'] = playlistend

	if load_cookies():
		verify_login_status(exception = True)
	else:
		login()
		verify_login_status(exception = True)
		save_cookies()

	# ----

	print()
	if not SC.urls:
		collect_urls()
	process_urls()

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		description = '',
	)
	parser.add_argument(
		'--server',
		dest = 'server',
		help = '',
	)
	parser.add_argument(
		'--pvtype',
		dest = 'pv_type',
		type = int,
		help = 'Default PV type. ' + str(SC.pv_types.list) + ': 1, 2, 3',
	)
	parser.add_argument(
		'--playliststart',
		dest = 'playliststart',
		type = int,
		help = 'youtube-dl: playliststart',
	)
	parser.add_argument(
		'--playlistend',
		dest = 'playlistend',
		type = int,
		help = 'youtube-dl: playlistend',
	)
	parser.add_argument(
		'urls',
		nargs = '*',
		metavar = 'URL',
		help = 'A URL(s) to process. If not given here, you will be prompted for a list.',
		# use '--' before an URL that begins with a hyphen
		# https://docs.python.org/dev/library/argparse.html#arguments-containing
	)
	args = parser.parse_args()

	main(
		server = args.server,
		urls = args.urls,
		pv_type = args.pv_type,
		playliststart = args.playliststart,
		playlistend = args.playlistend,
	)