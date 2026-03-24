// ==UserScript==
// @namespace   szc
// @name        VocaDB aimbot 2024
// @version     2026-03-24
// @author      u126
// @description for extreme gamers only
// @homepageURL https://github.com/szc126/vocadb-sc
// @icon        https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/1faf5.png
// @match       https://www.nicovideo.jp/*
// @match       https://www.nicolog.jp/user/*
// @match       https://www.youtube.com/*
// @match       https://*.bilibili.com/*
// @grant       GM.setValue
// @grant       GM.getValue
// @grant       GM.registerMenuCommand
// @grant       GM.notification
// @top-level-await
// ==/UserScript==

'use strict';

// see also: https://gitlab.com/Hans5958-MWS/vocadb/-/blob/master/userscripts/aimbot/aimbot.user.js

let server = await GM.getValue('server', 'vocadb.net');
let running = false;

// domains:
	// domains to apply the following data to
// aSelectors:
	// CSS selectors for PV links
// aParent:
	// the element that will contain the link to the VocaDB entry, defined relative to a PV link

const services = {
	'NicoNicoDouga': {
		domains: ['www.nicovideo.jp'],
		aSelectors: [
			'a.NC-MediaObject-contents', // user
			'.itemTitle a', // search, tag
			'a[data-decoration-video-id]', // watch recommended sidebar
		],
		aParent: function(a) {
			if (a.classList.contains('NC-MediaObject-contents')) return a.parentNode;
			if (a.hasAttribute('data-decoration-video-id')) return a;
			return a.parentNode.parentNode;
		},
	},
	'NicoNicoDouga-Nicolog': {
		domains: ['www.nicolog.jp'],
		aSelectors: [
			'table .text-center a',
		],
		aParent: function(a) {
			return a.parentNode.parentNode.nextElementSibling;
		},
	},
	'Youtube': {
		// if you spam this on lists of non-vocaloid videos
		// i explode you with hammers
		// TODO: refuse to process further after N unregistered videos

		domains: ['www.youtube.com'],
		aSelectors: [
			'h3.ytd-rich-grid-media a', // channel, hashtag; `.ytd-rich-grid-media` is necessary (user comments are `h3.ytd-comment-view-model`)
			'a.ytd-compact-video-renderer', // watch recommended sidebar
			'a#video-title', // channel search

			'h3.yt-lockup-title a', // VORAPIS: channel, hashtag, results, channel search
			'a#related-video', // VORAPIS: watch recommended sidebar
		],
		aParent: function(a) {
			return a.parentNode;
		},
	},
	'Bilibili': {
		domains: ['bilibili.com'],
		aSelectors: [
			'.bili-video-card__title a', // space.bilibili.com
			'.bili-video-card__info--right > a', // search.bilibili.com
		],
		aParent: function(a) {
			return a.parentNode;
		},
	},
}

async function process_urls(service) {
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

	const as = document.querySelectorAll(services[service].aSelectors);
	for (const a of as) {
		if (!running) {
			scan_stop();
			return;
		}

		let url = a.href;

		// when running the script multiple times in one session
		// do not look up our own links
		if (url.indexOf(server) > 0) {
			continue;
		};

		// when running the script multiple times in one session
		// skip songs that we have already found
		if ('vocadbSongEntryId' in a.dataset) {
			continue;
		}

		// skip NND ad links. the video ID is not embedded in the link
		if (url.indexOf('api.nicoad.nicovideo.jp') > 0) {
			continue;
		};

		// TODO: destroy the old "create an entry link" when running the script again?

		// normalize
		url = url.replace('nicolog.jp', 'nicovideo.jp');
		// remove tracking garbage
		// to aid caching
		url = url.replace(/\?spm_id=.+$/, ''); // bilibili
		url = url.replace(/&pp=.+$/, ''); // YouTube

		const song_entry = await get_song_entry(url);
		const button = create_song_button(url, song_entry);
		services[service].aParent(a).appendChild(button);
		if (song_entry) {
			a.dataset.vocadbSongEntryId = song_entry.id;
		}
	}
	scan_stop();
}

async function get_song_entry(url) {
	const data_cached = await GM.getValue(url);
	if (data_cached) {
		return data_cached;
	}

	await new Promise(resolve => setTimeout(resolve, 2000));

	return fetch('https://' + server + '/api/songs?' + new URLSearchParams({
		'query': url,
		'fields': 'Tags',
	})).then(response => response.json()
	).then(data => {
		if (data.items.length > 1) {
			prompt('Notice: Found multiple song entries for:', url);
		} else if (data.items.length > 0) {
			GM.setValue(url, data.items[0]);

			return data.items[0];
		}
	});
}

function create_song_button(url, song_entry) {
	// using <a> instead of <button>,
	// so that i can open multiple links at once
	// using extensions like Snap Links
	const a = document.createElement('a');
	a.style.background = song_entry ? 'lime' : 'magenta';
	a.style.padding = '0.5em';
	a.href = song_entry ?
		'https://' + server + '/S/' + song_entry.id :
		'https://' + server + '/Song/Create?' + new URLSearchParams({
			'pvUrl': url,
		});
	a.title = song_entry ?
		[song_entry.name, song_entry.songType, song_entry.artistString, song_entry.tags.map(tag => tag.tag.name).join(', ')].join('\n') :
		'';
	a.target = '_blank'; // TODO: also make the video <a> open in a new tab?

	const text = document.createTextNode(server);
	a.appendChild(text);

	return a;
}

function scan_start(service) {
	if (running) {
		GM.notification({
			text: 'Scanning is already in progress.',
		});
		return;
	}

	GM.notification({
		text: 'Scanning…',
	});
	running = true;
	process_urls(service);
}

function scan_stop() {
	GM.notification({
		text: 'Done scanning.',
	});
	running = false;
}

GM.registerMenuCommand('Change server…', function() {
	server = prompt('Change server from ' + server + ' to:', server);
	GM.setValue('server', server);
});

GM.registerMenuCommand('Start scanning', function() {
	for (const service in services) {
		const domains = services[service].domains;
		if (domains.some(domain => window.location.href.includes(domain))) {
			scan_start(service);
		}
	}
});

GM.registerMenuCommand('Stop scanning', function() {
	scan_stop();
});