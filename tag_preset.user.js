// ==UserScript==
// @namespace   szc
// @name        VocaDB tag presets
// @version     2025-06-09
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
	['耳ｺ', '耳コピ'],

	['跨', 'unsupported language'],
	['譯', 'changed language'],
	['改', 'changed lyrics'],
	['增', 'additional lyrics'],
	['ﾊﾟﾛ', 'parody'],

	['淸', 'a cappella'], // 清唱
	['純', 'no lyrics'], // 純音樂
	['喋', 'speech vocals'],
	['詠', 'poemloid'],
	['拾', 'lyrics from poetry'],

	['晒', 'editor PV'],
	['utau📥️', 'UTAU voicebank release'],
	['ﾃﾞﾓ', 'voicebank demo'],
	['β', 'beta voicebank'],
	['升', 'upgraded voicebank'],
	['tri', 'trial voicebank'],
	['煎', 'remastered cover'], // 二番煎じ
	['unc', 'unconfirmed vocalists'],
	['c', 'confirmed original bank'],

	['mp3📥️', 'free'],
	['ｵｹ', 'karaoke available'],
	['ust', 'UST available'],
	['vsq', 'VSQ available'],

	['svp📥️', 'SVP available'],
	['svﾗｲﾄ', 'Synthesizer V lite version voice'],
	['sv跨語言', 'Synthesizer V AI cross-lingual singing synthesis'],

	['似', 'original art imitation'],
	['官方', 'official art PV'],
	['AI', 'AI generated art'],
	['拾', 'uncredited art PV'],

	['MMD'],
	['手書', '手書きPV'],
	['ｱﾆ', '2D animated PV'],
	['文字', '文字PV'],

	['🏫', '兒歌'],
	['🪖', '軍歌'],
	['講', '講座'],
	['詰', 'multiple song PV'],
	['調', 'good tuning'],
	['雙', 'bilingual'],
	['多', 'polylingual'],
	['饒', 'rapping'],

	['ﾋﾟｱﾉ', 'piano'],
	['ｱｺｷﾞ', 'acoustic guitar'],
	['ｴﾚｷ', 'electric guitar'],
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
