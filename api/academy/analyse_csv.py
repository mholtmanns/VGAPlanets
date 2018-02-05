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


def get_winner_race(data, gameid, playername):
    if  type(gameid) is int:
        gameid = str(gameid)
    if data['games'][gameid]['status'] == 'Finished':
        return data['players'][playername][gameid]['race'][0]
    return 'No Race'


def write_games_csv(data, fieldnames, filename='academygames.csv'):
    """Write out the game overview dict to a CSV file
    """
    gamelist = []
    for game, gamedata in data['games'].items():
        gamelist.append(gamedata)
    print (gamelist)
    gamelist.sort(key=iget('datecreated'))

    with open('academygames.csv', 'w', newline='') as csvfile:
        fieldnames = gamekeys
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for game in gamelist:
            game['race'] = get_winner_race(data, game['id'], game['winner'])
            writer.writerow(game)


if __name__ == "__main__":
    gamedata = aa.load_gamedata()
    gamekeys = ['id', 'name', 'status', 'datecreated', 'dateended', 'turn', 'winner', 'race']

    write_games_csv(gamedata, gamekeys)
