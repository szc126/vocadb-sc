#!/usr/bin/env python3

"""
TODO:
	- check for editing ability?
	- catch error of broken cookies?
	- unintelligent matching of an album to a playlist. the album has 10 tracks, the playlist has 10 tracks, we are golden

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

# XXX: what can i call this script? 'SC'ript and 'a.py' are obviously terrible names
# XXX: is this how classes work?
class SCPvTypes:
	ORIGINAL = 'Original'
	REPRINT = 'Reprint'
	OTHER = 'Other'

	@property
	def list(self):
		return [self.ORIGINAL, self.REPRINT, self.OTHER]
class SC:
	server = 'vocadb.net'
	urls = []
	pv_types = SCPvTypes()

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

ytdl = youtube_dl.YoutubeDL({
	'usenetrc': True,
	'simulate': True,
})

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
	'''Check if we are logged in to **DB.'''

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

	print_e(f'{colorama.Fore.GREEN}Logged in{colorama.Fore.RESET} as {colorama.Fore.CYAN}' + request.json()['name'])
	return True

def save_cookies() -> bool:
	'''Save cookies to disk.'''

	filename = sys.argv[0] + '.cookies.txt'
	with open(filename, 'wb') as file:
		pickle.dump(session.cookies, file)
	print_e(f'{colorama.Fore.GREEN}Cookies saved{colorama.Fore.RESET} to {colorama.Fore.CYAN}{filename}')
	return True

def load_cookies() -> bool:
	'''Load cookies from disk.'''

	try:
		filename = sys.argv[0] + '.cookies.txt'
		with open(filename, 'rb') as file:
			session.cookies.update(pickle.load(file))
		print_e(f'{colorama.Fore.GREEN}Cookies loaded{colorama.Fore.RESET} from {colorama.Fore.CYAN}{filename}')
		return True
	except FileNotFoundError:
		print_e(f'{colorama.Fore.RED}Cookies not found')

# ----

def collect_urls() -> None:
	'''Collect URLS from standard input.'''

	print_e('Enter URLs, one per line. Enter "." when done.')
	while True:
		i = input()
		if i == '.':
			break
		SC.urls.append(i)

def process_urls() -> None:
	''''''

	infos = []
	print('Fetching video information')
	for url in SC.urls:
		info = ytdl.extract_info(url)
		infos = infos + recursive_get_ytdl_individual_info(info)
	print()

	# for debug: dump the info of a selected item
	#print_p(infos[int(input())])

	infos_working = []
	for info in infos:
		print(info['title'])
		print(info['webpage_url'])

		# for debug: we don't need direct download urls
		info.pop('formats', None)
		info.pop('requested_formats', None)
		info.pop('thumbnails', None)

		# undocumented api
		# https://vocadb.net/Song/Create?PVUrl=$foo
		request = session.get(
			f'{SC.h_server}/api/songs/findDuplicate',
			params = {
				'term': {}, # names
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
				print(f'{colorama.Fore.GREEN}This PV has already been added to the database.')
				print()
		else:
			infos_working.append((info, request))
			print(f'{colorama.Fore.RED}This PV has not been added to the database yet.')
			print()

	print()
	print('----')
	print()

	for info, request in infos_working:
		while True:
			print(info['title'])
			print(info['uploader'])
			print(info['webpage_url'])
			
			print_p(request.json()['matches'])

			if request.json()['matches'] and input('Is the first match correct? [Y/n]').casefold() != 'n':
				song_id = request.json()['matches'][0]['entry']['id']
				pv_type = SC.pv_types.REPRINT

				if request.json()['artists']:
					for entry in request.json()['artists']:
						if entry['artistType'] == 'Producer':
							pv_type = SC.pv_types.ORIGINAL

				if input(f'Is the PV type {pv_type}? [Y/n]').casefold() != 'n':
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
				entry_data_modified['updatenotes'] = f'Batch addition of PV: {pv_type}, {info["webpage_url"]}'

				# undocumented not-api
				request_save = session.post(
					f'{SC.h_server}/Song/Edit/{song_id}',
					{
						'EditedSong': json.dumps(entry_data_modified),
					}
				)

				if request_save.status_code == 200:
					print(f'{colorama.Fore.GREEN}Success')

				break
			else:
				print(f'{colorama.Fore.RED}TODO: ask again') # TODO
				break

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

def main(server = None, urls = None):
	SC.server = server or SC.server
	SC.urls = urls or SC.urls

	load_cookies()

	if not verify_login_status(exception = False):
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
		'urls',
		nargs = argparse.REMAINDER, # for yt links that begin with hyphens
		metavar = 'URL',
		help = 'A URL(s) to process. If not given here, you will be prompted for a list.',
	)
	args = parser.parse_args()

	main(
		server = args.server,
		urls = args.urls,
	)