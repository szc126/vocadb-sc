// ==UserScript==
// @namespace   szc
// @name        VocaDB tag presets
// @version     2026-07-20
// @author      u126
// @description buttons to add tags with one click
// @homepageURL https://github.com/szc126/vocadb-sc
// @icon        https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/1f3f7.png
// @match       https://vocadb.net/*
// @match       https://beta.vocadb.net/*
// @grant       GM.setValue
// @grant       GM.getValue
// @grant       GM.registerMenuCommand
// ==/UserScript==

'use strict';

let tag_presets = [
	['人', 'human original'],
	['ｱﾆ', 'anime song cover'],
	['🎮', 'video game song cover'],
	['📺', 'TV show song cover'],
	['🎬', 'movie song cover'],

	['翻', 'self-cover'],
	['混', 'self-remix'],
	['短', 'short version'],
	['增', 'extended version'],
	['重', 'remastered cover'], // 重製

	['跨', 'unsupported language'],
	['譯', 'changed language'],
	['改', 'changed lyrics'],
	['增', 'additional lyrics'],
	['パ', 'parody'],

	['喋', 'speech vocals'],
	['詠', 'poemloid'],
	['清', 'a cappella'], // 清唱

	['詰', 'multiple song PV'],
	['晒', 'editor PV'],

	['u📥️', 'UTAU voicebank release'],
	['ﾃﾞﾓ', 'voicebank demo'],
	['β', 'beta voicebank'],
	['升', 'upgraded voicebank cover'],
	['驗', 'trial voicebank'], // 體驗版

	['mp3📥️', 'free'],
	['ｵｹ', 'karaoke available'],
	['ust', 'UST available'],
	['vsq', 'VSQ available'],

	['似🖼️', 'original art imitation'],
	['官', 'official art PV'],
	['AI', 'AI-generated art'],
	['拾', 'uncredited art PV'],
	['👥', 'multiple illustrators'],

	['mmd'],
	['手書', '手書きPV'],
	['2d', '2D animated PV'],
	['文', '文字PV'],

	['双', 'bilingual'],
	['多', 'polylingual'],
	['饒', 'rapping'],
	['双人', 'duet'],
	['樂曲', 'no lyrics'],

	['🎹', 'piano'],
	['ｱｺｷﾞ', 'acoustic guitar'],
	['🎸', 'electric guitar'],

	['耳ｺ', '耳コピ'],
	['arr.OoS', 'instrumental from out of scope'],
	['orig.unk', 'original version unknown'],

	['unk.voc', 'unconfirmed vocalists'],
	['旧', 'confirmed original bank'],
	['🕴️', 'limited artist information'],
	['🌧️', 'failing to add embed'],
];
GM.getValue('additional_tag_presets', []).then((value) => {
	tag_presets = tag_presets.concat(value);

	tag_presets.forEach((_, i) => {
		if (tag_presets[i].length === 1) tag_presets[i] = tag_presets[i].concat(tag_presets[i])
	});
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
	let div = document.createElement('div');
	div.id = 'mytagspreset'
	div.classList.add('btn-group');
	div.classList.add('navbar-languageBar');
	div.style.display = 'flex';
	div.style.flexWrap = 'wrap';
	div.style.fontSize = '1em'; // [a] this line is a pair with line [b]
	div.style.letterSpacing = '-0.1em';
	document.getElementsByClassName('sidebar-nav')[0].append(div);

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
	const current_tags_flat = current_tags.flatMap(({ tag }) => [tag.name, ...tag.additionalNames.split(', ')]);

	const tag_suggestions = await fetch(
		'/api/' + entry_type_api_path[entry_type] + '/' + entry_id + '/tagSuggestions',
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json; charset=utf-8',
			},
		}
	).then(response => response.json());

	[...tag_presets, ...tag_suggestions.map(({ tag }) => ['💡' + tag.name, tag.name])].forEach(tag_preset => {
		let payload = tag_preset.slice(1).map(tag_name => {
			return {
				'name': tag_name,
			}
		});
		let b = document.createElement('a');
		b.innerText = tag_preset[0];
		b.addEventListener('click', (event) => apply_tag(event, entry_type, entry_id, payload));
		b.classList.add('btn');
		b.classList.add('btn-default');
		b.style.fontSize = '125%'; // [b] this line is a pair with line [a]
		b.title = tag_preset.slice(1).join('\n');

		if (tag_preset.slice(1).every(tag_name => current_tags_flat.includes(tag_name))) {
			b.classList.remove('btn-default');
			b.classList.add('btn-success');
		}

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

GM.registerMenuCommand('Add a tag preset', function() {
	const tag_name = prompt('Tag name (will take effect on next tab reload):');
	if (!tag_name) return;
	GM.getValue('additional_tag_presets', []).then((value) => {
		GM.setValue('additional_tag_presets', value.concat([[tag_name]]));
	});
});
