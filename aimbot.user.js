// ==UserScript==
// @namespace   szc
// @name        VocaDB aimbot 2024
// @version     2025-04-07
// @author      u126
// @description for extreme gamers only
// @homepageURL https://github.com/szc126/vocadb-sc
// @icon        https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/1faf5.png
// @match       https://www.nicovideo.jp/user/*
// @match       https://www.nicovideo.jp/mylist/*
// @match       https://www.nicovideo.jp/search/*
// @match       https://www.nicovideo.jp/tag/*
// @match       https://www.nicolog.jp/user/*
// @match       https://www.youtube.com/*/videos
// @match       https://www.youtube.com/*/search
// @match       https://www.youtube.com/hashtag/*
// @match       https://www.youtube.com/watch?*
// @match       https://www.youtube.com/results?*
// @match       https://space.bilibili.com/*
// @match       https://search.bilibili.com/*
// @grant       GM.setValue
// @grant       GM.getValue
// @grant       GM.registerMenuCommand
// ==/UserScript==

'use strict';

// see also: https://gitlab.com/Hans5958-MWS/vocadb-docs/-/snippets/4801219

// shoutout to ChatGPT for figuring out where to put the darned async/await keywords
// also. does the timeout cancel out the benefit (async) of using fetch(). lol.

// domains:
	// domains corresponding to each set of instructions (the stuff below)
// a_query_selectors:
	// CSS selectors for PV links
// button_parent:
	// the element that will contain the link to the VocaDB entry, defined relative to a PV link
// nav_query_selectors:
	// CSS selectors for the elements that will contain the link to start this script

let server = false;
(async () => {
	server = await GM.getValue('server', 'vocadb.net');
})();

let running = false;

var services = {
	'NicoNicoDouga': {
		'domains': ['www.nicovideo.jp'],
		'a_query_selectors': [
			'a.NC-MediaObject-contents', // user
			'.itemTitle a', // search & tag
			//'a[data-decoration-video-id]', // watch. NG (all the `<a>`s are in one big container, so all the VocaDB links pile up at the end of the page)
		],
		'button_parent': function(a) {
			return a.classList.contains('NC-Link') ? a.parentNode : a.parentNode.parentNode;
		},
		'nav_query_selectors': [
			//'.NC-Tabs', // user
			'.nico-CommonHeaderRoot > div:first-child > div:first-child > div:first-child',
		],
	},
	'NicoNicoDouga-Nicolog': {
		'domains': ['www.nicolog.jp'],
		'a_query_selectors': [
			'table .text-center a',
		],
		'button_parent': function(a) {
			return a.parentNode.parentNode.nextElementSibling;
		},
		'nav_query_selectors': [
			'th:first-of-type',
		],
	},
	'Youtube': {
		// if you spam this on lists of non-vocaloid videos
		// i explode you with hammers
		// TODO: refuse to process further after N unregistered videos

		'domains': ['www.youtube.com'],
		'a_query_selectors': [
			'h3.ytd-rich-grid-media a', // channel and hashtag; the .ytd-rich-grid-media is necessary; user comments are h3.ytd-comment-view-model
			'a.ytd-compact-video-renderer', // recommended sidebar
			'a#video-title', // channel search
		],
		'button_parent': function(a) {
			return a.parentNode;
		},
		'nav_query_selectors': [
			//'#chips-content', // channel, "sort by" menu // channels with few videos do not have the "sort by" menu
			'.yt-tab-group-shape-wiz__tabs', // channel, "home" "videos" "shorts" tab bar
			'#offer-module', // recommended sidebar
			'#center', // /results
		],
	},
	'Bilibili': {
		'domains': ['bilibili.com'],
		'a_query_selectors': [
			'.bili-video-card__title a', // space.bilibili.com
			'.bili-video-card__info--right > a', // search.bilibili.com
		],
		'button_parent': function(a) {
			return a.parentNode;
		},
		'nav_query_selectors': [
			'.nav-bar__main-left', // space.bilibili.com 投稿
			'.vui_tabs--nav', // search.bilibili.com
		],
	},
}

async function process_urls(service) { // ASYNC
	// message on YouTube channels
	if (typeof ytInitialData !== 'undefined' && ytInitialData?.metadata?.channelMetadataRenderer?.externalId) {
		prompt('For a faster option, consider instead:', 'https://' + server + '/SongList/Import');
		prompt('Featured videos:', 'https://www.youtube.com/playlist?list=UULF' + ytInitialData.metadata.channelMetadataRenderer.externalId.slice(2));
		prompt('Popular videos:', 'https://www.youtube.com/playlist?list=UULP' + ytInitialData.metadata.channelMetadataRenderer.externalId.slice(2));

		if (confirm('Continue scanning?')) {
			//
		} else {
			scan_stop();
			return;
		}
	}

	let as = document.querySelectorAll(services[service].a_query_selectors);
	for (let a of as) {
		if (!running) {
			scan_stop();
			return;
		}

		let url = a.href;

		// allow running the script multiple times in one session.
		// but do not look up our own links ofc
		if (url.indexOf(server) > 0) {
			continue;
		};

		// allow running the script multiple times in one session.
		// skip songs that we have already found
		if ('vocadbSongEntryId' in a.dataset) {
			continue;
		}

		// skip NND ad links (the video ID is not embedded in the link)
		if (url.indexOf('api.nicoad.nicovideo.jp') > 0) {
			continue;
		};

		// remove tracking garbage from URLs
		// to aid caching
		url = url.replace(/\?spm_id=.+$/, ''); // bilibili
		url = url.replace(/&pp=.+$/, ''); // YouTube

		// TODO: destroy the old "create an entry link" when running the script again?

		// normalize nicolog
		url = url.replace('nicolog.jp', 'nicovideo.jp');

		let song_entry = await get_song_entry(url); // AWAIT
		let button = create_song_button(url, song_entry);
		services[service].button_parent(a).appendChild(button);
		if (song_entry) {
			a.dataset.vocadbSongEntryId = song_entry.id;
		}
	}
	scan_stop();
}

async function get_song_entry(url) { // ASYNC
	let data_cached = await GM.getValue(url);
	if (data_cached) {
		return data_cached;
	}

	await new Promise(resolve => setTimeout(resolve, 2000)); // AWAIT

	return fetch('https://' + server + '/api/songs?' + new URLSearchParams({
		'query': url,
		'fields': 'Tags',
	})).then(response => response.json()
	).then(data => {
		if (data.items.length > 1) {
			prompt('Notice: Found multiple song entries for:', url);
		}
		if (data.items.length > 0) {
			GM.setValue(url, data.items[0]);

			return data.items[0];
		}
	});

	return false;
}

function create_song_button(url, song_entry) {
	// using <a> instead of <button>,
	// so that i can open multiple links at once
	// using extensions like Snap Links
	let a = document.createElement('a');
	a.style.background = song_entry ? 'lime' : 'magenta';
	a.style.padding = '0.5em';
	a.href = song_entry ? 'https://' + server + '/S/' + song_entry.id : 'https://' + server + '/Song/Create?' + new URLSearchParams({
		'pvUrl': url,
	});
	a.title = song_entry ? [song_entry.name, song_entry.songType, song_entry.artistString, song_entry.tags.map(tag => tag.tag.name).join(', ')].join('\n') : '';
	a.target = '_blank'; // TODO: also make the video <a> open in a new tab?

	let text = document.createTextNode(server);
	a.appendChild(text);

	return a;
}

function scan_start(service) {
	if (running) {
		// do not allow concurrent scanning of the same list of videos
		return;
	}

	running = true;
	document.getElementById('aimbot-style').innerText = '.aimbot-button-start { display: none; }';
	process_urls(service);
}

function scan_stop() {
	running = false;
	document.getElementById('aimbot-style').innerText = '.aimbot-button-stop { display: none; }';
}

function add_main_button(service) {
	let style = document.createElement('style');
	style.id = 'aimbot-style';
	style.innerText = '.aimbot-button-stop { display: none; }';
	document.head.appendChild(style);

	let navs = document.querySelectorAll(services[service].nav_query_selectors);
	for (let nav of navs) {
		// have to construct a new `button` every time. sad

		// IIFE so that I can restate `let button` instead of making copy-and-paste mistakes related to variable names
		(function() {
			let button = document.createElement('button');
			button.addEventListener('click', () => scan_start(service));
			button.style.background = 'cyan';
			button.classList.add('aimbot-button-start');

			button.appendChild(document.createTextNode('Scan for ' + server));

			nav.appendChild(button);
		})();

		(function() {
			let button = document.createElement('button');
			button.addEventListener('click', scan_stop);
			button.style.background = 'magenta';
			button.classList.add('aimbot-button-stop');

			button.appendChild(document.createTextNode('Stop scanning for ' + server));

			nav.appendChild(button);
		})();
	}
}

function main() {
	GM.registerMenuCommand('Change server from ' + server, function() {
		GM.setValue('server', prompt('Change server from ' + server + ' to:', server));
		server = server;
	});

	for (let service in services) {
		let domains = services[service].domains;
		if (domains.some(domain => window.location.href.includes(domain))) {
			add_main_button(service);
		}
	}
}

// add 2-second delay to let whatever fancy javascript framework finish rendering
setTimeout(function() {
	//alert('vocadb song add script is ready');
	main();
}, 2000);