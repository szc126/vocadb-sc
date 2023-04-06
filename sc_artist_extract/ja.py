#!/usr/bin/env python

kw_song_type = {
	'original': ['オリジナル', 'オリジナル曲', 'オリジナルソング', 'short ver'],
	'remaster': ['修正版'],
	'remix': ['remix', 're-mix', 'mix', 'long ver', '周年', 'anniversary'],
	'ver': ['再うｐ', '再うp', 'ver', '版'],
	'cover': ['カバー', 'カバー曲'],
	'arrangement': ['アレンジ', 'arrange'],
	'medley': ['メドレー'],
	'pv': ['mv', 'pv付', 'pv'],
	'pv-fan': ['勝手に', '付けてみた', 'つけてみた'],
}

kw_artist_role = {
	'compose': ['作曲', '曲', 'music'],
	'arrange': ['編曲', 'アレンジ', 'arrangement', 'arrange'],
	'lyric': ['作詞', '歌詞', 'words', 'lyric', 'lyrics'],
	'inst': ['ピアノ', 'ギター', 'ドラム'],
	'tune': ['調教', '調声'],
	'vocal': ['歌', '唄', 'うた', 'ボーカル'],
	'chorus': ['コーラス'],
	'mix': ['ミックス', 'mix'],
	'master': ['マスタリング', 'master'],

	'illust': ['イラスト', '絵', 'illust'],
	'video': ['動画', 'video', 'movie'],
	'encode': ['エンコ'],
	'vsq': ['vsq', 'vsqx', 'ust'],

	'other': ['special thanks'],
	'parent': ['原曲', '本家'],
}

kw_url_label = {
	'parent': ['本家'],
	'inst': ['カラオケ', 'オケ', 'インスト', 'オフボーカル', 'コーラス', 'inst', 'oke', 'offvocal', 'offvo', 'off vocal', 'off vo'],
	'lyric': ['歌詞'],
	'dl': ['mp3'],
	'pv': ['youtube'],

	'illust': ['イラスト', '絵', 'illust'],
	'vsq': ['vsq', 'vsqx', 'ust'],

	'website': ['website', 'hp', 'blog', 'ブログ'],
	'profile': ['twitter', 'ツイッター'],
	'other': ['音源', '動画', '素材', 'blog'],
}

kw_profile_label = {
	'twitter': ['@', 'twitter.com'],
	'niconico': ['user/', 'mylist/', 'nicovideo.jp'],
}

kw_other_label = {
	# いまだに長い動画説明文に見慣れてないワイ
	'lyric': ['歌詞'],
}

kw_sentence = [
	r'(?:こんにちは|こんばんは)、?([^。]+)です。',
	r'([^\n]+)からお?借り',
	# ▼movie (etc)
	r'(?P<bullet>.).+\n.+(\n+(?P=bullet).+\n.+)+',
]

kw_title = [
	# 【VocType】Title
	r'【VocType】Title',
		# 【初音ミクオリジナル】link
		# https://www.nicovideo.jp/watch/sm8090624
	# 【Vocに】Title【歌わせてみた】
	r'【Vocに】Title【.+た】',
	# 【Voc】Title【Type】
	r'【Voc】Title【Type】',
	# 【Voc】Title／Parent【カバー】
	r'【Voc】Title／Parent【.*(?P<song_type>カバー)】',
	# 【MV】Title
	r'【Type】Title',

	# 「Voc」Title「Type」
	r'「Voc」Title「Type」',
		# 『初音ミク』千本桜『オリジナル曲PV』
		# https://www.nicovideo.jp/watch/sm15630734
		# 「flower」意味は無い「オリジナル曲」
		# https://www.nicovideo.jp/watch/sm41965838

	# Title／Voc（Type）
	r'Title／Voc（Type）',
	# Title／Pro feat. Voc
	r'Title／Pro feat. Voc',
	# Title／Pro with Voc
	r'Title／Pro with Voc',
	# Title／Voc
	r'Title／Voc',
	# Title feat. VOC
	r'Title feat. VOC',

	# Pro - Title feat. Voc
	r'Pro - Title feat. Voc'
		# DECO*27 - 二息歩行 (Reloaded) feat. 初音ミク
		# https://www.youtube.com/watch?v=iM8d0SzJTIU
	# Pro - Title
	r'Pro - Title',
		# Kikuo - 君はできない子
		# https://www.youtube.com/watch?v=nPF7lit7Z00
		# BUT:
		# 初音ミクの消失(THE END OF HATSUNE MIKU) - cosMo＠暴走P
		# https://www.youtube.com/watch?v=VWVtIg5cdDU

	# Vocにオリジナル曲「Title」を歌わせてみた
	r'VocにType「Title」',
		# 【LONG ver.】初音ミクにオリジナルソング「SING＆SMILE」を歌わせてみた。
		# https://www.nicovideo.jp/watch/sm1697854
	# VocType「Title」
	r'VocType「Title」',
		# 初音ミクオリジナル曲 「ハジメテノオト（Fullバージョン）」
		# https://www.nicovideo.jp/watch/sm1274898
		# 初音ミクオリジナル曲 「Calc.」
		# https://www.nicovideo.jp/watch/sm12050471

	# .*「Title」（Type）.*
	r'.*「Title」（Type）.*',
	# .*「Title」Type.*
	r'.*「Title」Type.*',
		# 雪歌ユフによる「ハローストロボ」itikura_Remix
		# http://www.nicovideo.jp/watch/sm16592999

	# Title
	r'Title',

	# ----
	# twitter 漁ったら→
	# https://twitter.com/midluster/status/1601516351331266562
]