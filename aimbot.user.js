// ==UserScript==
// @name        VocaDB aimbot 2024
// @homepageURL https://github.com/szc126/vocadb-sc
// @downloadURL https://raw.githubusercontent.com/szc126/vocadb-sc/main/aimbot.user.js
// @namespace   szc
// @match       *://www.nicovideo.jp/user/*
// @match       *://www.nicovideo.jp/mylist/*
// @match       *://www.nicovideo.jp/search/*
// @match       *://www.nicovideo.jp/tag/*
// @match       *://www.nicolog.jp/user/*
// @match       *://www.youtube.com/*/videos
// @match       *://www.youtube.com/*/search
// @match       *://www.youtube.com/hashtag/*
// @match       *://www.youtube.com/watch?*
// @match       *://www.youtube.com/results?*
// @match       *://space.bilibili.com/*
// @match       *://search.bilibili.com/*
// @grant       GM.setValue
// @grant       GM.getValue
// @description for extreme gamers only
// ==/UserScript==

// shoutout to ChatGPT. i do not understand async/await
// also. does the timeout cancel out the benefit (async) of using fetch(). lol.

// domains: domains corresponding to each set of instructions (the stuff below)
// a_query_selectors: CSS selectors for PV links
// button_parent: the element that will contain the link to the VocaDB entry, defined relative to a PV link
// nav_query_selectors: CSS selectors for the elements that will contain the link to start this script

var server = false;
(async () => {
	server = await GM.getValue('server', 'vocadb.net');
})();

var services = {
	'NicoNicoDouga': {
		'domains': ['www.nicovideo.jp'],
		'a_query_selectors': [
			'a.NC-MediaObject-contents', // user
			'.itemTitle a', // search & tag
		],
		'button_parent': function(a) {
			return a.classList.contains('NC-Link') ? a.parentNode : a.parentNode.parentNode;
		},
		'nav_query_selectors': [
			'.VideoContainer-headerTotalCount', // user
			'.MylistHeader-name', // mylist
			'.contentsBox[data-search-option] .toolbar', // search & tag
		],
	},
	'NicoNicoDouga-Nicolog': {
		'domains': ['www.nicolog.jp'],
		'a_query_selectors': [
			'.text-center a',
		],
		'button_parent': function(a) {
			return a.parentNode.parentNode.nextElementSibling;
		},
		'nav_query_selectors': [
			'th:first-of-type',
		],
	},
	'Youtube': {
		// NOTE:
		// For channels,
		// giving the all videos "Videos" playlist to https://vocadb.net/SongList/Import
		// is faster;
		// however, that will always be "newest"-first

		// also if you spam this on lists of non-vocaloid videos
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
			'.cube-list a.title', // space.bilibili.com
			'.bili-video-card__info--right > a', // search.bilibili.com
			'a.cover-normal', // space.bilibili.com collectiondetail
		],
		'button_parent': function(a) {
			return a.parentNode;
		},
		'nav_query_selectors': [
			'.contribution-list', // space.bilibili.com 投稿
			'.search-nav', // space.bilibili.com 搜索
			'.page-head', // space.bilibili.com collectiondetail
			'.vui_tabs--nav', // search.bilibili.com
		],
	},
}

async function process_urls(service) { // ASYNC
	let as = document.querySelectorAll(services[service].a_query_selectors);
	for (let a of as) {
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

		// skip ad links (the video ID is not embedded in the link)
		if (url.indexOf('api.nicoad.nicovideo.jp') > 0) {
			continue;
		};

		// TODO: destroy the old "create an entry link" when running the script again?

		url = url.replace('nicolog.jp', 'nicovideo.jp');

		let song_entry = await get_song_entry(url); // AWAIT
		let button = create_button(url, song_entry);
		services[service].button_parent(a).appendChild(button);
		if (song_entry) {
			a.dataset.vocadbSongEntryId = song_entry.id;
		}
	}
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

function create_button(url, song_entry) {
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

function add_main_button(service) {
	let navs = document.querySelectorAll(services[service].nav_query_selectors);
	for (let nav of navs) {
		// need to make a new button each time, yes

		let button = document.createElement('button');
		button.addEventListener('click', function(event) {
			process_urls(service);
		});
		button.style.background = 'cyan';

		let text = document.createTextNode('Scan for ' + server);
		button.appendChild(text);

		nav.appendChild(button);
	}
	// TODO: stop the script if clicked while running
	// TODO: what happens if you click it while it's running, anyway
}

function main() {
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