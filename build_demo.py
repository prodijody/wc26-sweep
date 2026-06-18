# Builds data.js (window.DATA) with a clearly-labelled DEMO scenario for design mockups.
# Real team names/badges + the real office sweep list, clock wound to "Final pending".
import json, io

m = json.load(io.open('_m.json', encoding='utf-8'))

# --- team meta from real API data: tla, crest, group ---
meta = {}
for x in m['matches']:
    for side in ('homeTeam', 'awayTeam'):
        t = x[side]
        if t.get('name'):
            meta.setdefault(t['name'], {'name': t['name'], 'tla': t.get('tla'), 'crest': t.get('crest'), 'group': None})
    if x.get('group') and x['stage'] == 'GROUP_STAGE':
        g = x['group'].replace('GROUP_', '')
        for side in ('homeTeam', 'awayTeam'):
            t = x[side]
            if t.get('name'):
                meta[t['name']]['group'] = g

# --- sweep list: player -> list of (display, fd_name) ; None fd_name = unmatched ---
N = {  # sweep spelling -> football-data name
    'Bosnia': 'Bosnia-Herzegovina', 'Germany': 'Germany', 'Sweden': 'Sweden', 'England': 'England',
    'Turkey': 'Turkey', 'Jordan': 'Jordan', 'Mexico': 'Mexico', 'New Zealand': 'New Zealand',
    'Algeria': 'Algeria', 'Cape Verde': 'Cape Verde Islands', 'Portugal': 'Portugal', 'Iran': 'Iran',
    'Uruguay': 'Uruguay', 'Norway': 'Norway', 'America': 'United States', 'Australia': 'Australia',
    'Ecuador': 'Ecuador', 'Ghana': 'Ghana', 'Morocco': 'Morocco', 'Canada': 'Canada', 'Japan': 'Japan',
    'France': 'France', 'Saudi Arabia': 'Saudi Arabia', 'South Africa': 'South Africa',
    'Senegal': 'Senegal', 'Netherlands': 'Netherlands', 'Switzerland': 'Switzerland',
    'Ivory Coast': 'Ivory Coast', 'Qatar': 'Qatar', 'South Korea': 'South Korea', 'Iraq': 'Iraq',
    'Croatia': 'Croatia', 'Argentina': 'Argentina', 'Congo': 'Congo DR', 'Colombia': 'Colombia',
    'Spain': 'Spain', 'Scotland': 'Scotland', 'Czechia': 'Czechia', 'Tunisia': 'Tunisia',
    'Brazil': 'Brazil', 'Austria': 'Austria', 'Egypt': 'Egypt', 'Haiti': 'Haiti', 'Belgium': 'Belgium',
    'Paraguay': 'Paraguay', 'Panama': 'Panama', 'Beckistan': 'Uzbekistan',  # <-- flagged guess
}
SWEEP = [
    ('Finlay', ['Bosnia']), ('Mark', ['Germany', 'Sweden']), ('Lynn', ['England']),
    ('Laura', ['Turkey', 'Jordan']), ('Sharon', ['Mexico']), ('Sammy', ['New Zealand', 'Algeria']),
    ('Louise', ['Cape Verde', 'Portugal', 'Iran']), ('Jack', ['Uruguay', 'Norway']),
    ('Rooney', ['America']), ('Brandon', ['Australia']), ('Ross', ['Ecuador']), ('Blake', ['Ghana']),
    ('David Clarke', ['Morocco', 'Canada']), ('Barry', ['Japan', 'France']),
    ('Cami', ['Saudi Arabia', 'South Africa']), ('Jess', ['Beckistan', 'Senegal']),
    ('Brandon B', ['Netherlands', 'Switzerland']), ('Barry B', ['Ivory Coast', 'Qatar']),
    ('Paul K', ['South Korea', 'Iraq']), ('Laura H', ['Portugal']),
    ('Paul Mc', ['Croatia', 'Argentina']), ('Johnny', ['Croatia', 'Congo']),
    ('Michael', ['Colombia', 'Spain']), ('Shelley', ['Scotland']), ('Tony T', ['Czechia']),
    ('Martin M', ['Tunisia']), ('Nicole', ['Brazil']), ('Edwina', ['Austria']),
    ('Cara McM', ['Egypt']), ('Sambo', ['Haiti', 'Belgium']), ('Thomas', ['Paraguay', 'Panama']),
]

# --- DEMO scenario: furthest stage per fd_name. 'in' teams are the 2 finalists. ---
STAGE_ORDER = ['GROUP', 'LAST_32', 'LAST_16', 'QUARTER_FINALS', 'SEMI_FINALS', 'FINAL']
STAGE_LABEL = {'GROUP': 'Group stage', 'LAST_32': 'Round of 32', 'LAST_16': 'Round of 16',
               'QUARTER_FINALS': 'Quarter-final', 'SEMI_FINALS': 'Semi-final', 'FINAL': 'Final'}
ALIVE = {'Brazil', 'France'}  # final still to be played
SCENARIO = {
    'Brazil': 'FINAL', 'France': 'FINAL',
    'England': 'SEMI_FINALS', 'Argentina': 'SEMI_FINALS',
    'Portugal': 'QUARTER_FINALS', 'Spain': 'QUARTER_FINALS', 'Netherlands': 'QUARTER_FINALS', 'Morocco': 'QUARTER_FINALS',
    'Germany': 'LAST_16', 'Croatia': 'LAST_16', 'Mexico': 'LAST_16', 'United States': 'LAST_16',
    'Uruguay': 'LAST_16', 'Switzerland': 'LAST_16', 'Colombia': 'LAST_16', 'Senegal': 'LAST_16',
    'Bosnia-Herzegovina': 'LAST_32', 'Sweden': 'LAST_32', 'Turkey': 'LAST_32', 'Norway': 'LAST_32',
    'Australia': 'LAST_32', 'Ecuador': 'LAST_32', 'Ghana': 'LAST_32', 'Saudi Arabia': 'LAST_32',
    'Uzbekistan': 'LAST_32', 'Ivory Coast': 'LAST_32', 'Czechia': 'LAST_32', 'Egypt': 'LAST_32',
    'Belgium': 'LAST_32', 'Japan': 'LAST_32', 'Cape Verde Islands': 'LAST_32', 'Canada': 'LAST_32',
}
# everything else -> GROUP (eliminated in group stage)

def team_obj(display):
    fd = N.get(display)
    if not fd or fd not in meta:
        return {'display': display, 'name': fd or display, 'matched': False,
                'tla': None, 'crest': None, 'group': None, 'stage': None, 'stageLabel': 'Not in tournament', 'in': False}
    mt = meta[fd]
    stage = SCENARIO.get(fd, 'GROUP')
    alive = fd in ALIVE
    return {'display': display, 'name': fd, 'matched': True, 'tla': mt['tla'], 'crest': mt['crest'],
            'group': mt['group'], 'stage': stage, 'stageLabel': STAGE_LABEL[stage], 'in': alive}

players = []
for name, teams in SWEEP:
    tobjs = [team_obj(t) for t in teams]
    valid = [t for t in tobjs if t['stage']]
    best = max((STAGE_ORDER.index(t['stage']) for t in valid), default=-1)
    players.append({
        'name': name, 'teams': tobjs,
        'in': any(t['in'] for t in tobjs),
        'bestStage': STAGE_ORDER[best] if best >= 0 else None,
        'bestStageLabel': STAGE_LABEL[STAGE_ORDER[best]] if best >= 0 else '—',
        'bestRank': best, 'aliveCount': sum(1 for t in tobjs if t['in']),
    })

# leaderboard: alive first, then by best stage, then alive count, then name
leaderboard = sorted(players, key=lambda p: (-int(p['in']), -p['bestRank'], -p['aliveCount'], p['name']))

def mini(fd):
    mt = meta[fd]; return {'name': fd, 'tla': mt['tla'], 'crest': mt['crest']}

recent = [
    {'stage': 'Semi-final', 'home': mini('Brazil'), 'away': mini('England'), 'hs': 2, 'as': 1, 'note': 'FT'},
    {'stage': 'Semi-final', 'home': mini('France'), 'away': mini('Argentina'), 'hs': 1, 'as': 0, 'note': 'FT'},
    {'stage': 'Quarter-final', 'home': mini('Brazil'), 'away': mini('Morocco'), 'hs': 3, 'as': 1, 'note': 'FT'},
    {'stage': 'Quarter-final', 'home': mini('France'), 'away': mini('Portugal'), 'hs': 2, 'as': 0, 'note': 'FT'},
    {'stage': 'Quarter-final', 'home': mini('England'), 'away': mini('Spain'), 'hs': 1, 'as': 0, 'note': 'FT'},
    {'stage': 'Quarter-final', 'home': mini('Argentina'), 'away': mini('Netherlands'), 'hs': 2, 'as': 1, 'note': 'AET'},
]
fixtures = [
    {'stage': 'Final', 'home': mini('Brazil'), 'away': mini('France'), 'date': '2026-07-19', 'time': '20:00'},
    {'stage': 'Third place', 'home': mini('England'), 'away': mini('Argentina'), 'date': '2026-07-18', 'time': '20:00'},
]

DATA = {
    'demo': True, 'title': 'WC 2026 Office Sweep', 'updated': '2026-07-17T18:30:00',
    'phase': 'Final pending', 'playersIn': sum(1 for p in players if p['in']), 'playersTotal': len(players),
    'players': players, 'leaderboard': leaderboard, 'recent': recent, 'fixtures': fixtures,
    'stageOrder': STAGE_ORDER, 'stageLabel': STAGE_LABEL,
    'flags': {
        'Beckistan(?) → Uzbekistan': 'Guessed; confirm in sweep.json',
        'Portugal': 'Owned by both Louise and Laura H',
        'Croatia': 'Owned by both Paul Mc and Johnny',
        'Two Brandons': 'Listed as Brandon (Australia) and Brandon B (Netherlands, Switzerland)',
    },
}

with io.open('data.js', 'w', encoding='utf-8') as f:
    f.write('window.DATA = ' + json.dumps(DATA, ensure_ascii=False, indent=1) + ';\n')
print('wrote data.js |', len(players), 'players |', DATA['playersIn'], 'still in')
print('leaderboard top5:', [(p['name'], p['bestStageLabel'], 'IN' if p['in'] else 'out') for p in leaderboard[:5]])
