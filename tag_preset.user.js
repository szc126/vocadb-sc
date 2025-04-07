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

const observer = new MutationObserver(mutations => {
	mutations.forEach(record => {
		record.addedNodes.forEach(node => {
			if (node.id === 'nprogress') {
				try {
					document.getElementById('mytagspreset').remove();
				} catch(error) {
					0;
				}
				if (window.location.pathname.indexOf('/S/') === 0 || window.location.pathname.indexOf('/Song/') === 0) {
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

let sets = [
	['3D原', 'human original', 'original out of scope'],
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
	['vb升', 'upgraded voicebank'],
	['utau配', 'UTAU voicebank release'],
	['mp3配', 'free'],
	['ｵｹ配', 'karaoke available'],
	['ust配', 'UST available'],
	['vsq配', 'VSQ available'],
	['svﾗｲﾄ', 'Synthesizer V lite version voice'],
	['詰合pv', 'multiple song PV'],
	['ai絵', 'AI generated art'],
	['公式絵', 'official art PV'],

	['vb不詳', 'unconfirmed vocalists'],
	['lyrics from poetry'],
	['title pun'],
];
sets.forEach((_, i) => {
	if (sets[i].length === 1) sets[i] = sets[i].concat(sets[i])
});

function main() {
	let div = document.createElement("div");
	div.id = 'mytagspreset'
	div.classList.add("btn-group");
	div.classList.add("navbar-languageBar");
	div.style.display = 'flex';
	div.style.flexWrap = 'wrap';
	div.style.fontSize = '1em'; // goes with the line way down below
	document.getElementsByClassName("sidebar-nav")[0].append(div);

	const song_id = window.location.pathname.split('/').pop();

	fetch(
		'/api/users/current/songTags/' + song_id,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json; charset=utf-8',
			},
		}
	).then(response => response.json()
	).then(data_old => {
		for (let i = 0; i < sets.length; i++) {
			let b = document.createElement("a");
			b.innerHTML = sets[i][0];
			b.addEventListener("click", function(event) {
				let payload = [];
				for (let j = 1; j < sets[i].length; j++) {
					payload.push({
						'name': sets[i][j],
					});
				}
				fetch(
					'/api/users/current/songTags/' + song_id,
					{
						method: 'GET',
						headers: {
							'Content-Type': 'application/json; charset=utf-8',
						},
					}
				).then(response => response.json()
				).then(data => {
					fetch(
						'/api/users/current/songTags/' + song_id,
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
			});
			b.classList.add("btn");
			b.classList.add("btn-default");
			b.style.fontSize = '125%'; // goes with the line way up above

			/* ChatGPT start */
			let tags_added = sets[i].slice(1).every(tag_name =>
				data_old.some(item => item.tag.name === tag_name)
			);
			if (tags_added) {
				b.classList.remove('btn-default');
				b.classList.add('btn-success');
			}
			/* ChatGPT end */

			div.append(b);
		}

	});
}