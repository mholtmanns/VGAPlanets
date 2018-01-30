# Copyright 2018 Markus Hoff-Holtmanns
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import sys
import requests as rq

import json
import csv

from operator import itemgetter as iget
from datetime import datetime

BASE='http://api.planets.nu/'
RACES={ 1: 'The Solar Federation',
        2: 'The Lizard Alliance',
        3: 'The Empire of the Birds',
        4: 'The Fascist Empire',
        5: 'The Robotic Imperium',
        6: 'The Rebel Confederation',
        7: 'The Missing Colonies of Man'}

ACCOUNT_CACHE = {}

# Progress bar code copied from:
#     https://gist.github.com/aubricus/f91fb55dc6ba5557fbab06119420dd6a
# Keeping original formatting, just replacing the counting symbol
# Print iterations progress
def print_progress(iteration, total, prefix='', suffix='', decimals=1, bar_length=50):
    """
    Call in a loop to create terminal progress bar

    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        bar_length  - Optional  : character length of bar (Int)
    """
    str_format = "{0:." + str(decimals) + "f}"
    percents = str_format.format(100 * (iteration / float(total)))
    filled_length = int(round(bar_length * iteration / float(total)))
    bar = '#' * filled_length + '-' * (bar_length - filled_length)

    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, bar, percents, '%', suffix)),

    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()


def date_converter(datestr):
    # IN: 2/17/2017 4:43:38 AM - OUT:  2017-02-17 04:43:38 
    return datetime.strptime(datestr, '%m/%d/%Y %I:%M:%S %p')


def get_academy_games(keys_wanted, maxgames=0):
    """
    Read public info on all academy games

    Args:
        keys_wanted (:obj:`list` of :obj:`str`): specify keys we need from the game data
        maxgames (int, optional): How many games to read data of, defaults to all

    Returns:
        dict with specified keys of game data
    """
    url = BASE + 'games/list'
    # Get all Academy games that are Running, Finished or On Hold
    # Other games give incomplete data
    payload = {'type':'7', 'status':'2,3,4', 'limit':maxgames}
    status = {0: 'Interest', 1: 'Joining', 2: 'Running', 3: 'Finished', 4: 'On Hold'}

    # Access the API
    r = rq.get(url, params=payload)
    games_json = r.json()
    gamelist = []
    glen = len(games_json)
    for i, game in enumerate(games_json):
        # Ignore the early test games
        if 'Test' in game['shortdescription']:
            continue
        # filter desired keys
        l = {k: game.get(k, None) for k in keys_wanted}
        l['status'] = status[l['status']]
        gamelist.append(l)
        print_progress(i+1, glen, prefix = 'Getting games:', suffix = 'Done')

    return gamelist


def player_add(all_players, name, gameid, stat, value):
    """Register a certain statistic for a given player name.
    
     Stores statistics for a given player which are of the types:
     * Which game (ID) he played in
     * What race he played
     * If he won/resigned/dropped/joined later
     * The final score details

    Args:
        all_players (:obj:`dict`): Dict containing all player stats
        name (str): Player name
        gameid (str): Game Id as string
        stat (str): Statistic to register for this player, can be one of
            * race: register the race
            * status: did the player finish (rank), resign, drop or die
            * score: stores the score object for this game and player
        value (:obj:): payload for the given stat
    """
    # List of allowed stats
    stats = ['race', 'status', 'score']
    assert stat in stats, 'Unknown argument for stat!'

    if name not in all_players:
        all_players[name] = {}

    if gameid not in all_players[name]:
        all_players[name][gameid] = {}
        # Players can drop, resign, rejoin all in one game,
        # even change Race (in theory)
        all_players[name][gameid]['status'] = []
        all_players[name][gameid]['race'] = []

    player = all_players[name][gameid]
    if stat == 'score':
        player[stat] = value
    else:
        player[stat].append(value)


def crop_scores(player):
    score = {}
    score['rank'] = player['finishrank']
    if player['username'] == 'dead':
        score['finished'] = 0
        return score
    
    keys_wanted = [
        'capitalships',
        'freighters',
        'planets',
        'starbases',
        'militaryscore',
        'percent',
    ]
    score = {k: player['score'].get(k, None) for k in keys_wanted}
    score['finished'] = 1
    return score


def get_game_players(all_players, gameid):
    url = BASE + 'game/loadevents'
    payload = {'gameid': gameid}
    response = rq.get(url, params=payload)

    json_data = response.json()
    events = json_data["events"]

    url = BASE + 'game/loadinfo'
    payload = {'gameid': gameid}
    response = rq.get(url, params=payload)

    json_data = response.json()
    player_info = json_data["players"]

    # Eventtypes:
    # 1: Game created
    # 2: Game started
    # 3: <player> joined
    # 4: ??
    # 5: Win condition
    # 6: <player> has won
    # 7: <player> in slot X are now dead
    # 8: <player> has resigned
    # 9: ???
    # 10:<player> has dropped
    last_per_race = {}
    # First we need to go through all normal "joined" Events to fill the ACCOUNT_CACHE
    for event in events:
        t = event['eventtype']
        if t == 3:
            text = event['description']
            name = text[:(text.find('has joined')-1)]
            name = (name.rstrip(' +')).replace('+', ' ')
            if event['playerid'] not in last_per_race:
                last_per_race[event['playerid']] = {}
                last_per_race[event['playerid']]['turn'] = -1
                
            if last_per_race[event['playerid']]['turn'] < event['turn']:
                last_per_race[event['playerid']]['turn'] = event['turn']
                last_per_race[event['playerid']]['name'] = name
            
            ACCOUNT_CACHE[event['accountid']] = name

            player_add(all_players, name, gameid, 'race',
                       RACES[event['playerid']])

    for event in events:
        t = event['eventtype']
        # If a player resigned or dropped just add that stat
        if t in [7, 8, 10]:
            text = event['description']
            if t == 8:
                name = text[:(text.find('has resigned')-1)]
                stat = 'resigned'
            elif t == 10:
                name = text[:(text.find('has been dropped')-1)]
                stat = 'dropped'
            else:
                name = ACCOUNT_CACHE[event['accountid']]
                stat = 'dead'
            name = (name.rstrip(' +')).replace('+', ' ')
            player_add(all_players, name, gameid, 'status',
                       {0: stat, 1: event['turn']})

        # Just in case we see unknown events in the future
        if t in [4, 9] or t > 10:
            print('========>>>>> ' + str(event['eventtype']) + ': ' + event['description'])

    # Add scores for final players
    for player in player_info:
        score = crop_scores(player)
        if player['username'] != 'dead':
            player_add(all_players, last_per_race[player['id']]['name'], gameid, 'status',
                       {0: 'alive', 1: player['score']['turn']})
            # print ('Added status for ',last_per_race[player['id']]['name'])
            
        player_add(all_players, last_per_race[player['id']]['name'],
                   gameid, 'score', score)


def create_player_stats(players):
    # Count total wins per player, automatically gives unique winners
    plen = len(players)
    winner = {}
    for i, player in enumerate(players):
        name = player['Winner']
        print_progress(i+1, plen, prefix = 'Winner stats:', suffix = 'Done')
        if name == 'n/a':
            continue
        for key, value in player.items():
            if key == 'Winner' or key == 'Id':
                continue
            if value == name:
                race = key
                break
        if name in winner:
            if race in winner[name]:
                winner[name][race] += 1
            else:
                winner[name][race] = 1
        else:
            winner[name] = {}
            winner[name][race] = 1

        # Differentiate per race wins per player - harder
    for n in winner:
        if n == 'n/a':
            continue
        print (winner[n])
        
def write_games_csv(games, fieldnames, filename='academygames.csv'):
    
    with open('academygames.csv', 'w', newline='') as csvfile:
        fieldnames = gamekeys
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for game in games:
            writer.writerow(game)


def main():
    gamekeys = ['id', 'name', 'status', 'datecreated', 'dateended', 'turn']
    games = get_academy_games(gamekeys)
    gameplayers = {}
    glen = len(games)
    print ('number of games:', glen)
    for i, game in enumerate(games):
        game['datecreated'] = date_converter(game['datecreated'])
        game['dateended'] = date_converter(game['dateended'])
        # Get the players of each game
        get_game_players(gameplayers, game['id'])
        print_progress(i+1, glen, prefix = 'Getting player stats:', suffix = 'Done')

    games.sort(key=iget('datecreated'))


    # Dump player dict as JSON for debugging
    # gp = json.dumps(gameplayers)
            
if __name__ == "__main__":
    main()