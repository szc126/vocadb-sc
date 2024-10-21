// ==UserScript==
// @name VocaDB tag presets
// @homepageURL https://github.com/szc126/vocadb-sc
// @downloadURL https://raw.githubusercontent.com/szc126/vocadb-sc/main/tag_preset.user.js
// @namespace szc
// @match https://vocadb.net/*
// @match https://beta.vocadb.net/*
// @grant none
// ==/UserScript==

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

function main() {
	let div = document.createElement("div");
	div.id = 'mytagspreset'
	div.classList.add("btn-group");
	div.classList.add("navbar-languageBar");
	div.style.display = 'flex';
	div.style.flexWrap = 'wrap';
	div.style.fontSize = '1em'; // goes with the line way down below
	document.getElementsByClassName("sidebar-nav")[0].append(div);

	const sets = [
		["3D原", 3193, 3282],
		["A", 22], // anime
		["G", 455], // video game
		["TV", 6715], // television
		["M", 4677], // movie

		["跨", 7059],
		["sv", 8639], // synthv translingual
		["換", 6224],
		["填", 2866],
		["ﾊﾟﾛ", 330], // parody

		["自翻", 391],
		["自混", 392],
		["ｼｮｰﾄ", 4717],
		["ﾌﾙ", 3068],

		["淸", 7],
		["晒", 6302],
		["ﾃﾞﾓ", 89],
		["vb升", 6333],
		["utau配", 5027],
		["mp3配", 160],
		["ｵｹ配", 3113],
		["ust配", 3153],
		["vsq配", 3122],
		["svﾗｲﾄ", 8044],
		["詰合pv", 6769],
		["ai絵", 9119],
		["公式絵", 6495],
		["言葉遊", 6856],
	];

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
				for (let j = 0; j < sets[i].slice(1).length; j++) {
					payload.push({
						"id": sets[i].slice(1)[j],
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
			let tags_added = sets[i].slice(1).every(tag_id =>
				data_old.some(item => item.tag.id === tag_id)
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