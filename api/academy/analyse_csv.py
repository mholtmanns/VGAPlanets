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

import json
import csv

import apiaccess as aa
from operator import itemgetter as iget

from constants import BASE, SHORTRACES


def get_winner_race(data, gameid, playername):
    if  type(gameid) is int:
        gameid = str(gameid)
    if data['games'][gameid]['status'] == 'Finished':
        return data['players'][playername][gameid]['race'][0]
    return 'No Race'


def write_games_csv(data, fieldnames, filename='game_stats.csv'):
    """Write out the game overview dict to a CSV file
    """
    gamelist = []
    for game, gamedata in data['games'].items():
        gamelist.append(gamedata)
    # print (gamelist)
    gamelist.sort(key=iget('datecreated'))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for game in gamelist:
            game['race'] = get_winner_race(data, game['id'], game['winner'])
            writer.writerow(game)


def write_per_player_stats(data, filename='player_stats.csv'):
    playerkeys = ['name']
    statlist = []
    for key, race in SHORTRACES.items():
        statlist.append(race + ' finished')
        statlist.append(race + ' won')
        statlist.append(race + ' dropped')
        statlist.append(race + ' resigned')
        statlist.append(race + ' died')
    playerkeys += statlist

    players = data['players']
    allstats = {}
    i = 0
    for player, playerdata in players.items():
        allstats[player] = {}
        playerstat = allstats[player]
        playerstat['name'] = player
        # Initialize all entries first!
        for stat in statlist:
            playerstat[stat] = 0
        for game, stats in playerdata.items():
            # ASSUMPTION! We only use the first race we find
            if game == 'accountid':
                continue

            race = SHORTRACES[stats['race'][0]]
            if 'score' in stats.keys() and stats['score']['finished'] == 1:
                if stats['score']['rank'] == 1:
                    playerstat[race + ' won'] += 1
                playerstat[race + ' finished'] += 1
            for s in stats['status']:
                if s['what'] == 'dead':
                    playerstat[race + ' died'] += 1
                elif s['what'] == 'dropped':
                    playerstat[race + ' dropped'] += 1
                elif s['what'] == 'resigned':
                    playerstat[race + ' resigned'] += 1
        aa.print_progress(i+1, len(players), prefix = 'Gather player stats:', suffix = 'Done')
        i += 1
    
    # print (allstats)
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=playerkeys)
        
        writer.writeheader()
        for player, stats in allstats.items():
            writer.writerow(stats)
            
    

# Wrappers for the different data filter tools
# [TODO markus] Make these into a class!
def game_writer(gamedata):
    gamekeys = ['id', 'name', 'status', 'datecreated', 'dateended', 'turn', 'winner', 'race']

    write_games_csv(gamedata, gamekeys)
    

if __name__ == "__main__":
    gamedata = aa.load_gamedata()
    
    game_writer(gamedata)
    write_per_player_stats(gamedata)

