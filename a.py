#!/usr/bin/env python3

"""
TODO:
	- check for editing ability?
	- catch error of broken cookies?
	- unintelligent matching of an album to a playlist. the album has 10 tracks, the playlist has 10 tracks, we are golden
	- cache 'already added pv'

PATH FROM HERE:
	- check if the url was already registered in the database
	- do the same stuff the 'add new song' page does: automatically guess info
	- 'possible matching entries' <- work off of this
	- manual intervention
		- constrain search results to a certain producer
		- apply user-supplied regex to title
"""

# https://docs.python.org/3/howto/curses.html

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
from disk_cache_decorator import disk_cache_decorator

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
	'user-agent': '(https://vocadb.net/Profile/u126)',
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
		print(colorama.Fore.CYAN + info['title'])
		print(colorama.Fore.CYAN + info['webpage_url'])

		# for debug: we don't need direct download urls
		info.pop('formats', None)
		info.pop('requested_formats', None)
		info.pop('thumbnails', None)

		# for debug: print the info
		#print_p(info)

		# undocumented api
		# https://vocadb.net/Song/Create?PVUrl=$foo
		request = session.get(
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
			print(f'This PV {colorama.Fore.RED}has not been added {colorama.Fore.RESET}to the database yet.')
			print(f'Add it? {colorama.Fore.CYAN}{SC.h_server}/Song/Create?PVUrl={info["webpage_url"]}')
			print()

	print('----')

	for info, request in infos_working:
		while True:
			print()
			print(colorama.Fore.CYAN + info['title'])
			print(colorama.Fore.CYAN + info['uploader'])
			print(colorama.Fore.CYAN + info['webpage_url'])
			print('----')
			print(colorama.Fore.CYAN + (info['description'] or {colorama.Fore.RESET} + '<no description>'))

			for i in range(len(request.json()['matches'])):
				print(f'{colorama.Fore.YELLOW}{i + 1}')
				print_p(request.json()['matches'][i]['entry'])
			print()

			if request.json()['matches']:
				print(f'{colorama.Fore.YELLOW}Match potentially found')

				match_n = '1'
				while True:
					i = input('Choose match [1/...], or enter "." to abort: ')
					if i == '':
						break
					elif i == '.':
						match_n = '.'
						break
					else:
						print_p(request.json()['matches'][int(i) - 1]['entry'])
						if input('Is this correct? [Y/n] ').casefold() != 'n':
							match_n = int(i)
							break
				if match_n == '.':
					break

				song_id = request.json()['matches'][int(match_n) - 1]['entry']['id']
				pv_type = SC.pv_types.list[SC.pv_type - 1]

				# it is an original pv because the producer was detected as the uploader
				if request.json()['artists']:
					for entry in request.json()['artists']:
						if entry['artistType'] == 'Producer':
							pv_type = SC.pv_types.ORIGINAL

				
				if input(f'Is the PV type {pv_type}? [Y/n] ').casefold() != 'n':
					pass
				else:
					try:
						pv_type = SC.pv_types.list[int(input(str(SC.pv_types.list) + ' [1/2/3]: ')) - 1]
					except:
						print(f'{colorama.Fore.RED}Not a valid answer;{colorama.Fore.RESET} continuing as before')

				# undocumented api
				request_entry_data = session.get(
					f'{SC.h_server}/api/songs/{song_id}/for-edit'
				)

				if request_entry_data.json()['status'] == 'Approved':
					if SC.user_group_id < SC.user_group_ids.TRUSTED:
						print(f'{colorama.Fore.YELLOW}This entry is approved. You do not have the permissions to edit it.')
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
				entry_data_modified['updateNotes'] = f'Batch addition of PV: {pv_type}, {info["webpage_url"]}'

				# undocumented not-api
				request_save = session.post(
					f'{SC.h_server}/Song/Edit/{song_id}',
					{
						'EditedSong': json.dumps(entry_data_modified),
					}
				)

				if request_save.status_code == 200:
					print(f'{colorama.Fore.GREEN}Success; {colorama.Fore.CYAN}{SC.h_server}/S/{song_id}')
				else:
					print_p(entry_data_modified)
					raise ValueError(f'Failed to save. HTTP status code {request_save.status_code}')

				break
			else:
				print(f'{colorama.Fore.YELLOW}Match not found')
				# undocumented api
				# https://vocadb.net/Song/Create?PVUrl=$foo
				i = prompt_toolkit.prompt('Search by name, or enter "." to abort: ', default = request.json()['title'])
				if i == '.':
					print(f'{colorama.Fore.RED}Aborted')
					break
				request = session.get(
					f'{SC.h_server}/api/songs/findDuplicate',
					params = {
						'term': i,
						'pv': info['webpage_url'],
						'getPVInfo': True,
					}
				)

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