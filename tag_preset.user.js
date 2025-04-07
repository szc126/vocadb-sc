// ==UserScript==
// @namespace   szc
// @name        VocaDB tag presets
// @version     2025-04-07
// @author      u126
// @description buttons to add tags with one click
// @homepageURL https://github.com/szc126/vocadb-sc
// @icon        https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/1f3f7.png
// @match       https://vocadb.net/*
// @match       https://beta.vocadb.net/*
// ==/UserScript==

'use strict';

let tag_presets = [
	['翻', 'human original', 'original out of scope'],
	['A', 'anime song cover'],
	['G', 'video game song cover'],
	['TV', 'TV show song cover'],
	['M', 'movie song cover'],

	['跨', 'unsupported language'],
	['sv', 'Synthesizer V AI cross-lingual singing synthesis'],
	['換', 'changed language'],
	['填', 'changed lyrics'],
	['ﾊﾟﾛ','parody'],

	['自翻', 'self-cover'],
	['自混', 'self-remix'],
	['ｼｮｰﾄ', 'short version'],
	['ﾌﾙ', 'extended version'],

	['淸', 'a cappella'],
	['晒', 'editor PV'],
	['ﾃﾞﾓ','voicebank demo'],
	['詰合pv', 'multiple song PV'],

	['utau📥️', 'UTAU voicebank release'],
	['mp3📥️', 'free'],
	['ｵｹ📥️', 'karaoke available'],
	['ust📥️', 'UST available'],
	['vsq📥️', 'VSQ available'],
	['svp📥️', 'SVP available'],

	['vb不詳', 'unconfirmed vocalists'],
	['vb升', 'upgraded voicebank'],
	['svﾗｲﾄ', 'Synthesizer V lite version voice'],
	['ai絵', 'AI generated art'],
	['公式絵', 'official art PV'],
	['lyrics from poetry'],
	['title pun'],
];
tag_presets.forEach((_, i) => {
	if (tag_presets[i].length === 1) tag_presets[i] = tag_presets[i].concat(tag_presets[i])
});

const tags_api_path = {
	'Ar': 'artistTags',
	'Artist': 'artistTags',
	'Al': 'albumTags',
	'Album': 'albumTags',
	'S': 'songTags',
	'Song': 'songTags',
}

const entry_type_api_path = {
	'Ar': 'artists',
	'Artist': 'artists',
	'Al': 'albums',
	'Album': 'albums',
	'S': 'songs',
	'Song': 'songs',
}

const observer = new MutationObserver(mutations => {
	mutations.forEach(record => {
		record.addedNodes.forEach(node => {
			if (node.id === 'nprogress') {
				try {
					document.getElementById('mytagspreset').remove();
				} catch(error) {
					0;
				}
				if (tags_api_path[window.location.pathname.split('/')[1]]) {
					main();
					//observer.disconnect();
				}
			}
		});
	});
});
observer.observe(document.body, {
	subtree: true,
	childList: true,
});

async function main() {
	let div = document.createElement("div");
	div.id = 'mytagspreset'
	div.classList.add("btn-group");
	div.classList.add("navbar-languageBar");
	div.style.display = 'flex';
	div.style.flexWrap = 'wrap';
	div.style.fontSize = '1em'; // [a] this line is a pair with line [b]
	div.style.letterSpacing = '-0.1em';
	document.getElementsByClassName("sidebar-nav")[0].append(div);

	const url_split = window.location.pathname.split('/');
	const entry_id = url_split[url_split.length - 1];
	const entry_type = url_split[1];

	const current_tags = await fetch(
		'/api/users/current/' + tags_api_path[entry_type] + '/' + entry_id,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json; charset=utf-8',
			},
		}
	).then(response => response.json());

	const tag_suggestions = await fetch(
		'/api/' + entry_type_api_path[entry_type] + '/' + entry_id + '/tagSuggestions',
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json; charset=utf-8',
			},
		}
	).then(response => response.json());

	tag_presets.concat(tag_suggestions.map(tag => ['💡' + tag.tag.name, tag.tag.name])).forEach(tag_preset => {
		console.log(tag_preset);

		let payload = tag_preset.slice(1).map(tag_name => {
			return {
				'name': tag_name,
			}
		});
		let b = document.createElement("a");
		b.innerText = tag_preset[0];
		b.addEventListener('click', (event) => apply_tag(event, entry_type, entry_id, payload));
		b.classList.add("btn");
		b.classList.add("btn-default");
		b.style.fontSize = '125%'; // [b] this line is a pair with line [a]

		/* ChatGPT start */
		let tags_added = tag_preset.slice(1).every(tag_name =>
			current_tags.some(item => item.tag.name === tag_name)
		);
		if (tags_added) {
			b.classList.remove('btn-default');
			b.classList.add('btn-success');
		}
		/* ChatGPT end */

		div.append(b);
	});
}

function apply_tag(event, entry_type, entry_id, payload) {
	let b = event.target;
	fetch(
		'/api/users/current/' + tags_api_path[entry_type] + '/' + entry_id,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json; charset=utf-8',
			},
		}
	).then(response => response.json()
	).then(data => {
		fetch(
			'/api/users/current/' + tags_api_path[entry_type] + '/' + entry_id,
			{
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json; charset=utf-8',
				},
				body: JSON.stringify(data.filter(tag => tag.selected).map(tag => tag.tag).concat(payload)),
			}
		).then(response => {
			if (response.status >= 200 && response.status < 300) {
				b.classList.remove('btn-default');
				b.classList.add('btn-success');
			}
		})
	});
};