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
from pathlib import Path

BASE='http://api.planets.nu/'
RACES={ 1: 'The Solar Federation',
        2: 'The Lizard Alliance',
        3: 'The Empire of the Birds',
        4: 'The Fascist Empire',
        5: 'The Robotic Imperium',
        6: 'The Rebel Confederation',
        7: 'The Missing Colonies of Man'}

ACCOUNT_CACHE = {}
DATA_FILE = 'player_data.json'

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
    return str(datetime.strptime(datestr, '%m/%d/%Y %I:%M:%S %p'))


def get_academy_games(keys_wanted, maxgames=0):
    """
    Read public info on all academy games

    Args:
        keys_wanted (:obj:`list` of :obj:`str`): specify keys we need from the game data
        maxgames (int, optional): How many games to read data of, defaults to all

    Returns:
        dict with specified keys of game data or None
    """
    url = BASE + 'games/list'
    # Get all Academy games that are Running, Finished or On Hold
    # Other games give incomplete data
    payload = {'type':'7', 'status':'2,3,4', 'limit':maxgames}
    status = {0: 'Interest', 1: 'Joining', 2: 'Running', 3: 'Finished', 4: 'On Hold'}

    # Access the API
    r = rq.get(url, params=payload)
    games_json = r.json()
    glen = len(games_json)
    gamelist = {}
    for i, game in enumerate(games_json):
        # Ignore the early test games
        if 'Test' in game['shortdescription']:
            continue
        # filter desired keys
        l = {k: game.get(k, None) for k in keys_wanted}
        l['status'] = status[l['status']]
        gamelist[l['id']] = l
        print_progress(i+1, glen, prefix = 'Getting games:', suffix = 'Done')

    if len(gamelist) == 0:
        return None
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
    """Select specific only parts of the full score object

    Args:
        player (dict): player object from which to read the score

    Returns:
        score (dict): filtered scores from the game data
    """
    score = {}
    # if there is no active username, nobody finished, but the
    # last seen player might still get a valid rank
    if player['username'] in ['dead', 'open']:
        score['finished'] = 0
        score['rank'] = player['finishrank']
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
    score['rank'] = player['finishrank']
    return score


def get_game_players(all_players, gameid):
    """
    Add player data to the global playerlist for a given game ID
    based both on event and actual game data.

    Known event ids:
        *  1: Game created
        *  2: Game started
        *  3: <player> joined
        *  4: ??
        *  5: Win condition
        *  6: <player> has won
        *  7: <player> in slot X are now dead
        *  8: <player> has resigned
        *  9: ???
        * 10: <player> has dropped

    Args:
        * all_players  (:obj:`dict`): Dict containing all player stats
        * gameid (int): Game ID
    """

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

    # Dict for the last seen player of a certain race
    last_per_race = {}
    # First we need to go through all normal "joined" Events to fill
    # the ACCOUNT_CACHE; the events are not ordered chronological
    for event in events:
        if event['eventtype'] ==  3:
            text = event['description']
            name = text[:(text.find('has joined')-1)]
            name = (name.rstrip(' +')).replace('+', ' ')
            # playerid is actually the game slot
            if event['playerid'] not in last_per_race:
                last_per_race[event['playerid']] = {}
                last_per_race[event['playerid']]['turn'] = -1
                
            if last_per_race[event['playerid']]['turn'] < event['turn']:
                last_per_race[event['playerid']]['turn'] = event['turn']
                last_per_race[event['playerid']]['name'] = name
            
            ACCOUNT_CACHE[event['accountid']] = name
            # add this game's race to the players list
            # print (name, ' ', gameid, ' ', event['playerid'])
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

    # Add scores for players that were last seen for a race
    for player in player_info:
        if player['username'] != 'dead':
            # Check in the  player that are still living 
            player_add(all_players, last_per_race[player['id']]['name'], gameid, 'status',
                       {0: 'alive', 1: player['score']['turn']})
            # print ('Added status for ',last_per_race[player['id']]['name'])

        score = crop_scores(player)
        # Register the select final score for all players dead or otherwise
        player_add(all_players, last_per_race[player['id']]['name'],
                   gameid, 'score', score)


def check_load_data(games_actual, gcount, filename):
    """Check if we have old data and compare the game count to actual
    
    Args:
        games_actual (int): number of games from live API data
        filename (str): File name to load data from

    Returns:
        data (dict): Either stored data if it exists or None
        games (list): If live data has more entries than the stored data
            return the missing game IDs
    """
    try:
        f = open(filename,'r')
    except FileNotFoundError:
        return None, None
    except IOError as e:
        print ("I/O error({0}): {1}".format(e.errno, e.strerror))
    except: #handle other exceptions such as attribute errors
        print ("Unexpected error:", sys.exc_info()[0])
    else:
        try:
            data = json.load(f)
        except:
            print ("Unexpected error:", sys.exc_info()[0])
            data = {}
            data['players'] = None
            all_gameids = None
        else:
            if data['gamecount'] == gcount:
                all_gameids = None
            elif data['gamecount'] > gcount:
                assert 0, 'Stored data corrupted! Remove file {} and re-run!'.format(filename)
            else:
                # Need to find the missing IDs
                stored_gameids = set()
                for game, fields in data['games'].items():
                    stored_gameids.add(fields['id'])
                print (stored_gameids)
                all_gameids = set()
                for game in games_actual:
                    all_gameids.add(game)
                print (all_gameids)
                all_gameids.difference_update(stored_gameids)
                print (all_gameids)

                assert len(all_gameids) > 0, 'Gamecount should differ, still no new game IDs found!'
                print ('{0} new game(s) found, IDs are: {1}'.format(len(all_gameids), all_gameids))

        f.close()
        return data, all_gameids

def add_winning_player(games, players, new_gameids=None):
    # Add the winning player (rank 1) to the games list
    i = 0
    for playername, player in players.items():
        # print (playername)
        for gameid, playerdata in player.items():
            # print (gamedata['players'][player][gameid])
            check = False
            if new_gameids is None:
                check = True
            elif gameid in new_gameids:
                check = True
            if check and 'score' in playerdata.keys():
                gdata = playerdata['score']
                if gdata['rank'] == 1:
                    # print (playername, ' has won Game ',gameid)
                    assert games[gameid], 'For some reason GameID {} is not registered yet!'.format(gameid)
                    games[gameid]['winner'] = playername
        print_progress(i+1, len(players), prefix = 'Getting game winner:', suffix = 'Done')
        i += 1
    
def load_gamedata():
    # define desired keys to load for every academy games
    gamekeys = ['id', 'name', 'status', 'datecreated', 'dateended', 'turn', 'winner']
    games = get_academy_games(gamekeys, maxgames = 16)
    # First check if we even read any games from the API
    if games is None:
        return None

    glen = len(games)
    mark_for_save = False
    stored_data, gameids = check_load_data(games, glen, DATA_FILE)
    if stored_data is None:
        # First time storing or re-reading data
        gameplayers = {}
        mark_for_save = True
        i = 0
        for gameid, game in games.items():
            game['datecreated'] = date_converter(game['datecreated'])
            game['dateended'] = date_converter(game['dateended'])
            # Get the players of each game
            get_game_players(gameplayers, gameid)
            print_progress(i+1, glen, prefix = 'Getting player stats:', suffix = 'Done')
            i += 1
        add_winning_player(games, gameplayers)
        stored_data = {'games': games, 'players': gameplayers, 'gamecount': glen}
    elif gameids is not None:
        storedgames = stored_data['games']
        gameplayers = stored_data['players']
        mark_for_save = True
        # We need to read data for the new gameids
        for i, gameid in enumerate(gameids):
            newgame = games[gameid]
            newgame['datecreated'] = date_converter(newgame['datecreated'])
            newgame['dateended'] = date_converter(newgame['dateended'])
            storedgames[gameid] = games[gameid]
            get_game_players(gameplayers, gameid)
            print_progress(i+1, len(gameids), prefix = 'Updating games and players:', suffix = 'Done')
        add_winning_player(storedgames, gameplayers, gameids)
        stored_data['gamecount'] += len(gameids)

    if mark_for_save:
        try:
            f = open(DATA_FILE, 'w')
        except IOError as e:
            print ("I/O error({0}): {1}".format(e.errno, e.strerror))
        except: #handle other exceptions such as attribute errors
            print ("Unexpected error:", sys.exc_info()[0])
        else:
            json.dump(stored_data, f)
            f.close()
    else:
        print('No new games found.')

    return stored_data
            
if __name__ == "__main__":
    _ = load_gamedata()
