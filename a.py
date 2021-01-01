#!/usr/bin/env python3

"""
TODO:
	- save cookies to disk?
	- check for editing ability?
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

ROOT = 'vocadb.net'
H_ROOT = f'https://{ROOT}'

session = requests.Session()
session.headers.update({
	'user-agent': '(https://vocadb.net/Profile/u126)',
})

colorama.init(autoreset = True)

def print_e(*args, **kwargs):
	print(*args, **kwargs, file = sys.stderr)

# ----

def login():
	netrc_auth = netrc.netrc().authenticators(ROOT)
	if not netrc_auth:
		raise LookupError(f'Could not find the {ROOT} machine in .netrc')

	print_e('Logging in')
	request = session.post(
		f'{H_ROOT}/User/Login',
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

def verify_login_status(exception = True):
	print_e('Verifying login status')
	request = session.get(
		f'{H_ROOT}/api/users/current',
	)
	if request.status_code != 200:
		if exception:
			raise ValueError('Verification failed')
		else:
			print_e(f'{colorama.Fore.RED}Could not verify login status')
			return False

	print_e(f'{colorama.Fore.GREEN}Logged in{colorama.Fore.RESET} as {colorama.Fore.CYAN}' + request.json()['name'])
	return True

def save_cookies():
	filename = sys.argv[0] + '.cookies.txt'
	with open(filename, 'wb') as file:
		pickle.dump(session.cookies, file)
	print_e(f'Cookies were saved to {colorama.Fore.CYAN}{filename}')
	return True

def load_cookies():
	try:
		filename = sys.argv[0] + '.cookies.txt'
		with open(filename, 'rb') as file:
			session.cookies.update(pickle.load(file))
		return True
	except FileNotFoundError:
		print_e('Cookies not found')

# ----

def collect_urls():
	source = input()

	return True

# ----

def main():
	load_cookies()

	if not verify_login_status(exception = False):
		login()
		verify_login_status(exception = True)
		save_cookies()

	# ----

	collect_urls()

main()
